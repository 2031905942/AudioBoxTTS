"""
IndexTTS2 模型下载工具类

使用 huggingface_hub 下载模型文件，支持进度回调。
"""
import os
import sys
import subprocess
import json
import time
from typing import Optional, Callable, List

from PySide6.QtCore import QObject, Signal, Slot

from Source.Utility.indextts_runtime_utility import get_runtime_paths

# 默认模型仓库
DEFAULT_REPO_ID = "IndexTeam/IndexTTS-2"

# 必需文件及其大致大小（MB，用于进度估算）
# 注意: pinyin.vocab 是源码自带的参考文件，不在 HuggingFace 仓库中
REQUIRED_FILES = {
    "bpe.model": 0.5,
    "config.yaml": 0.01,
    "gpt.pth": 3400,
    "s2mel.pth": 1150,
    "wav2vec2bert_stats.pt": 0.01,
    "feat1.pt": 0.06,
    "feat2.pt": 0.4,
    # Qwen 情感分析模型（用于情感文本分析）
    "qwen0.6bemo4-merge/config.json": 0.01,
    "qwen0.6bemo4-merge/model.safetensors": 1300,
    "qwen0.6bemo4-merge/generation_config.json": 0.01,
    "qwen0.6bemo4-merge/tokenizer.json": 7,
    "qwen0.6bemo4-merge/tokenizer_config.json": 0.01,
    "qwen0.6bemo4-merge/merges.txt": 1.7,
    "qwen0.6bemo4-merge/vocab.json": 2.7,
}

# 外部依赖模型 (repo_id, filename, size_mb, local_subpath)
EXTERNAL_FILES = [
    ("facebook/w2v-bert-2.0", "config.json", 0.01, "facebook/w2v-bert-2.0"),
    ("facebook/w2v-bert-2.0", "preprocessor_config.json", 0.01, "facebook/w2v-bert-2.0"),
    ("facebook/w2v-bert-2.0", "model.safetensors", 2300, "facebook/w2v-bert-2.0"),
    ("amphion/MaskGCT", "semantic_codec/model.safetensors", 50, "amphion/MaskGCT"),
]

# 可选文件（已移至 REQUIRED_FILES）
OPTIONAL_FILES = {
    # Qwen 模型现在是必需的
}


class IndexTTSDownloadUtility(QObject):
    """IndexTTS2 模型下载 Worker（运行在子线程）

    信号：
        progress_signal(float, str): 进度更新 (0.0-1.0, 描述)
        error_signal(str): 错误消息
        finished_signal(str): 下载完成，返回模型目录路径
        file_downloaded_signal(str): 单个文件下载完成
    """

    progress_signal = Signal(float, str)
    error_signal = Signal(str)
    finished_signal = Signal(str)
    file_downloaded_signal = Signal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._is_cancelled: bool = False

    def cancel(self):
        """取消下载"""
        self._is_cancelled = True

    def _download_via_runtime_venv(
        self,
        *,
        local_dir: str,
        repo_id: str,
        use_mirror: bool,
    ) -> bool:
        """在 Runtime/IndexTTS2/.venv 中执行下载。

        目的：GUI 主环境保持轻量，不要求安装 huggingface_hub。
        """
        paths = get_runtime_paths()
        if not os.path.exists(paths.venv_python):
            self.error_signal.emit("未发现 IndexTTS2 独立环境，请先执行：下载依赖和模型 → 安装并下载")
            return False

        os.makedirs(local_dir, exist_ok=True)

        total_size = float(sum(REQUIRED_FILES.values()) + sum(f[2] for f in EXTERNAL_FILES))
        downloaded_size = 0.0
        inflight_mb = 0.0

        # 终端日志节流（避免刷屏）
        last_print_ts = 0.0
        last_print_key = ""

        # 子进程脚本：逐个文件下载，并输出 JSON 行协议。
        # 输出格式：
        #   {"event": "skip|done|start|progress|error|all_done", "name": "...", "size": 1.23, ...}
        # 其中 progress 事件额外包含：downloaded_bytes / total_bytes。
        script_payload = {
            "repo_id": repo_id,
            "local_dir": local_dir,
            "required_files": list(REQUIRED_FILES.items()),
            "external_files": EXTERNAL_FILES,
        }

        child_code = r"""
import os, json, sys, time

payload = json.loads(sys.argv[1])
repo_id = payload["repo_id"]
local_dir = payload["local_dir"]
required_files = payload["required_files"]
external_files = payload["external_files"]

try:
    import requests
except Exception as e:
    print(json.dumps({"event": "error", "message": f"requests 导入失败: {e}"}, ensure_ascii=False), flush=True)
    raise

os.makedirs(local_dir, exist_ok=True)

def emit(event, **kw):
    kw["event"] = event
    print(json.dumps(kw, ensure_ascii=False), flush=True)

def _head_size(url: str) -> int:
    try:
        resp = requests.head(url, allow_redirects=True, timeout=30)
        if resp.status_code >= 400:
            return 0
        val = resp.headers.get("Content-Length")
        return int(val) if val and val.isdigit() else 0
    except Exception:
        return 0

def _download(url: str, dest_path: str, size_mb_hint: float, display_name: str) -> None:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    total_bytes = _head_size(url)
    existing = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0

    if total_bytes and existing >= total_bytes:
        emit("skip", name=display_name, size=float(size_mb_hint))
        return

    emit("start", name=display_name, size=float(size_mb_hint), total_bytes=int(total_bytes))

    headers = {}
    mode = "wb"
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"
        mode = "ab"

    resp = requests.get(url, stream=True, allow_redirects=True, timeout=60, headers=headers)

    # HTTP 416: requested range not satisfiable (常见于本地文件大小异常/服务器不接受该 Range)
    # 处理策略：删除本地文件，从头重新下载。
    if resp.status_code == 416 and existing > 0:
        try:
            resp.close()
        except Exception:
            pass
        try:
            os.remove(dest_path)
        except Exception:
            pass
        existing = 0
        headers.pop("Range", None)
        mode = "wb"
        resp = requests.get(url, stream=True, allow_redirects=True, timeout=60, headers=headers)

    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}")

    # 若 Range 被忽略，重新从头写
    if existing > 0 and resp.status_code == 200:
        existing = 0
        mode = "wb"

    downloaded = existing
    last_emit = 0.0
    with open(dest_path, mode) as f:
        for chunk in resp.iter_content(chunk_size=4 * 1024 * 1024):
            if not chunk:
                continue
            f.write(chunk)
            downloaded += len(chunk)
            now = time.time()
            if now - last_emit >= 0.5:
                emit(
                    "progress",
                    name=display_name,
                    size=float(size_mb_hint),
                    downloaded_bytes=int(downloaded),
                    total_bytes=int(total_bytes),
                )
                last_emit = now

    emit(
        "progress",
        name=display_name,
        size=float(size_mb_hint),
        downloaded_bytes=int(downloaded),
        total_bytes=int(total_bytes),
    )

    if total_bytes and downloaded < total_bytes:
        raise RuntimeError(f"下载不完整: {downloaded}/{total_bytes} bytes")

    emit("done", name=display_name, size=float(size_mb_hint))

def _resolve_url(base: str, repo: str, filename: str) -> str:
    # HuggingFace resolve URL (supports large LFS files via redirects)
    # Example: https://huggingface.co/<repo>/resolve/main/<path>
    # Mirror:  https://hf-mirror.com/<repo>/resolve/main/<path>
    return f"{base}/{repo}/resolve/main/{filename}"

hf_base = os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")

for filename, size_mb in required_files:
    dest = os.path.join(local_dir, filename)
    url = _resolve_url(hf_base, repo_id, filename)
    display = filename
    try:
        _download(url, dest, float(size_mb), display)
    except Exception as e:
        emit("error", message=f"下载 {display} 失败: {e}")
        raise

for ext_repo_id, filename, size_mb, local_subpath in external_files:
    target_dir = os.path.join(local_dir, local_subpath)
    dest = os.path.join(target_dir, filename)
    url = _resolve_url(hf_base, ext_repo_id, filename)
    display = f"{ext_repo_id}:{filename}"
    try:
        _download(url, dest, float(size_mb), display)
    except Exception as e:
        emit("error", message=f"下载 {display} 失败: {e}")
        raise

emit("all_done")
"""

        env = os.environ.copy()
        if use_mirror:
            env["HF_ENDPOINT"] = "https://hf-mirror.com"
        else:
            env.pop("HF_ENDPOINT", None)

        creation_flags = 0x08000000 if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            [paths.venv_python, "-c", child_code, json.dumps(script_payload, ensure_ascii=False)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=creation_flags,
        )

        assert proc.stdout is not None
        for raw in proc.stdout:
            if self._is_cancelled:
                try:
                    proc.terminate()
                except Exception:
                    pass
                self.error_signal.emit("下载已取消")
                return False

            line = (raw or "").strip()
            if not line:
                continue

            # 非 JSON 输出直接透传（便于诊断）
            try:
                evt = json.loads(line)
            except Exception:
                # 兼容子进程偶发的普通输出：显示在进度区域，同时也打印到终端
                self.progress_signal.emit(0.0, line)
                print(f"[IndexTTSDownload] {line}")
                continue

            event = evt.get("event")
            name = evt.get("name", "")
            size_mb = float(evt.get("size") or 0.0)

            if event == "error":
                self.error_signal.emit(str(evt.get("message", "下载失败")))
                print(f"[IndexTTSDownload] ERROR: {evt.get('message', '下载失败')}")
                try:
                    proc.terminate()
                except Exception:
                    pass
                return False

            if event in ("skip", "done"):
                inflight_mb = 0.0
                downloaded_size += size_mb
                frac = 0.05 + 0.9 * (downloaded_size / total_size if total_size > 0 else 1.0)
                msg = ("跳过已存在" if event == "skip" else "已下载") + f": {name}"
                self.progress_signal.emit(min(frac, 0.95), msg)

                now = time.time()
                if now - last_print_ts >= 1.0 or last_print_key != name:
                    print(f"[IndexTTSDownload] {msg}")
                    last_print_ts = now
                    last_print_key = name

                if event == "done":
                    # 对主仓库文件，尽量仅回传文件名
                    self.file_downloaded_signal.emit(name.split(":", 1)[-1])
                continue

            if event == "progress":
                # 单个大文件下载中：平滑更新进度条
                total_bytes = int(evt.get("total_bytes") or 0)
                downloaded_bytes = int(evt.get("downloaded_bytes") or 0)

                if total_bytes > 0:
                    inflight_mb = size_mb * (downloaded_bytes / total_bytes)
                    percent = 100.0 * (downloaded_bytes / total_bytes)
                else:
                    inflight_mb = downloaded_bytes / (1024 * 1024)
                    percent = 0.0

                overall = downloaded_size + inflight_mb
                frac = 0.05 + 0.9 * (overall / total_size if total_size > 0 else 0.0)
                detail = f"{name}"
                if percent > 0:
                    detail += f" ({percent:.1f}%)"
                self.progress_signal.emit(min(frac, 0.95), f"下载中: {detail}")

                # 终端输出节流
                now = time.time()
                if now - last_print_ts >= 2.0:
                    if total_bytes > 0:
                        mb_done = downloaded_bytes / (1024 * 1024)
                        mb_total = total_bytes / (1024 * 1024)
                        print(f"[IndexTTSDownload] {name}: {mb_done:.0f}/{mb_total:.0f} MB ({percent:.1f}%)")
                    else:
                        mb_done = downloaded_bytes / (1024 * 1024)
                        print(f"[IndexTTSDownload] {name}: {mb_done:.0f} MB")
                    last_print_ts = now
                continue

            if event == "start":
                inflight_mb = 0.0
                frac = 0.05 + 0.9 * (downloaded_size / total_size if total_size > 0 else 0.0)
                self.progress_signal.emit(min(frac, 0.95), f"下载中: {name} ({size_mb:.1f} MB)")

                now = time.time()
                if now - last_print_ts >= 1.0 or last_print_key != name:
                    print(f"[IndexTTSDownload] 下载开始: {name} ({size_mb:.1f} MB)")
                    last_print_ts = now
                    last_print_key = name
                continue

            if event == "all_done":
                break

        rc = proc.wait()
        if rc != 0:
            self.error_signal.emit(f"下载子进程失败 (exit={rc})，请查看安装日志或重试")
            return False

        return True

    @Slot(str, str, bool)
    def download(self, local_dir: str, repo_id: str = DEFAULT_REPO_ID,
                 use_mirror: bool = False):
        """下载模型到指定目录

        Args:
            local_dir: 本地保存目录
            repo_id: HuggingFace 仓库 ID
            use_mirror: 是否使用镜像源（hf-mirror.com）
        """
        self._is_cancelled = False

        try:
            self.progress_signal.emit(0.0, "准备下载环境...")

            # 设置镜像
            if use_mirror:
                os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
            elif "HF_ENDPOINT" in os.environ:
                del os.environ["HF_ENDPOINT"]

            # 关键：模型下载放到 Runtime/IndexTTS2/.venv 里执行，避免要求 GUI 主环境安装 huggingface_hub。
            # 若独立环境不存在/不完整，会给出明确提示。
            os.makedirs(local_dir, exist_ok=True)
            ok = self._download_via_runtime_venv(local_dir=local_dir, repo_id=repo_id, use_mirror=use_mirror)
            if not ok:
                return

            # 子进程下载完成后，继续进行本地验证与完成信号。

            # 这里不再在主环境中逐个下载文件（由独立 venv 子进程完成）。

            self.progress_signal.emit(0.95, "验证文件完整性...")

            # 验证必需文件
            missing = []
            for filename in REQUIRED_FILES:
                if not os.path.exists(os.path.join(local_dir, filename)):
                    missing.append(filename)

            if missing:
                self.error_signal.emit(f"文件验证失败，缺少: {', '.join(missing)}")
                return

            self.progress_signal.emit(1.0, "下载完成！")
            self.finished_signal.emit(local_dir)

        except Exception as e:
            import traceback
            self.error_signal.emit(f"下载失败: {e}\n{traceback.format_exc()}")

    @staticmethod
    def get_model_size_estimate() -> str:
        """获取模型总大小估算"""
        total = sum(REQUIRED_FILES.values())
        return f"约 {total / 1024:.1f} GB"

    @staticmethod
    def check_disk_space(path: str, required_mb: float = 5000) -> tuple[bool, str]:
        """检查磁盘空间

        Returns:
            (是否足够, 描述信息)
        """
        import shutil
        try:
            total, used, free = shutil.disk_usage(path)
            free_mb = free / (1024 * 1024)
            if free_mb < required_mb:
                return False, f"磁盘空间不足: 需要 {required_mb / 1024:.1f} GB，可用 {free_mb / 1024:.1f} GB"
            return True, f"可用空间: {free_mb / 1024:.1f} GB"
        except Exception as e:
            return False, f"无法检查磁盘空间: {e}"
