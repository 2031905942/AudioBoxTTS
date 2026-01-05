"""IndexTTS2 独立环境安装/卸载工具。

目标：
- GUI 主环境不安装任何 IndexTTS2 重依赖；
- IndexTTS2 依赖安装在 Runtime/IndexTTS2/.venv；
- 安装使用 uv（更稳定）；
- 卸载为删除整个 venv 目录。
"""

import os
import shutil
import subprocess
import sys
import time
from typing import Optional, List, Tuple
import re

from PySide6.QtCore import QObject, Signal, Slot

from Source.Utility.indextts_runtime_utility import ensure_runtime_pyproject, get_runtime_paths


PYPI_MIRRORS = {
    "aliyun": "https://mirrors.aliyun.com/pypi/simple",
    "tsinghua": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "default": "https://pypi.org/simple",
}


_CHECK_IMPORTS = [
    ("torch", "torch"),
    ("torchaudio", "torchaudio"),
    ("transformers", "transformers"),
    ("accelerate", "accelerate"),
    ("librosa", "librosa"),
    ("omegaconf", "omegaconf"),
    ("sentencepiece", "sentencepiece"),
    ("safetensors", "safetensors"),
    ("huggingface_hub", "huggingface_hub"),
    ("modelscope", "modelscope"),
]


class IndexTTSEnvUtility(QObject):
    """IndexTTS2 环境依赖安装 Worker"""

    progress_signal = Signal(float, str)  # 进度, 描述
    error_signal = Signal(str)
    finished_signal = Signal(bool)  # 是否成功
    log_signal = Signal(str)  # 安装日志

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._is_cancelled = False
        self._python_path: str = sys.executable

    def cancel(self):
        """取消安装"""
        self._is_cancelled = True

    def _ensure_uv_installed(self) -> None:
        """确保 GUI 主环境里可用 uv（仅工具本身，非 torch 等重依赖）。"""
        if self._is_cancelled:
            raise RuntimeError("安装已取消")

        creation_flags = 0x08000000 if sys.platform == "win32" else 0
        check = subprocess.run(
            [self._python_path, "-m", "uv", "--version"],
            capture_output=True,
            text=True,
            creationflags=creation_flags,
        )

        if check.returncode == 0:
            ver = (check.stdout or "").strip()
            if ver:
                self.log_signal.emit(f"uv: {ver}")
            return

        self.log_signal.emit("未检测到 uv，开始安装 uv（仅工具，不含 torch 等）...")
        self._run_cmd_stream([self._python_path, "-m", "pip", "install", "-U", "uv"])

    @staticmethod
    def get_python_path() -> str:
        """获取当前 Python 解释器路径"""
        return sys.executable

    @staticmethod
    def check_full_env_status() -> Tuple[bool, str, List[str]]:
        """检查 IndexTTS2 独立 venv 是否就绪（子进程安全检测）。"""
        import json

        paths = get_runtime_paths()
        if not os.path.exists(paths.venv_python):
            missing = [pkg_name for _, pkg_name in _CHECK_IMPORTS]
            return False, "未安装 IndexTTS2 独立环境", missing

        check_script = """
import importlib.util
import json

deps = %s
missing = []

for import_name, pkg_name in deps:
    try:
        if importlib.util.find_spec(import_name) is None:
            missing.append(pkg_name)
    except Exception:
        missing.append(pkg_name)

result = {"missing": missing, "cuda_available": False, "cuda_name": ""}

if not missing:
    try:
        import torch
        if torch.cuda.is_available():
            result["cuda_available"] = True
            result["cuda_name"] = torch.cuda.get_device_name(0)
    except Exception:
        pass

print(json.dumps(result, ensure_ascii=False))
""" % (repr(_CHECK_IMPORTS))

        try:
            creation_flags = 0x08000000 if sys.platform == "win32" else 0
            proc = subprocess.run(
                [paths.venv_python, "-c", check_script],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=creation_flags,
            )

            if proc.returncode != 0:
                return False, "独立环境检测失败（Python/依赖异常）", []

            data = json.loads((proc.stdout or "").strip() or "{}")
            missing = data.get("missing", [])

            if missing:
                return False, f"缺少依赖: {', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}", missing

            cuda_msg = (
                f"CUDA 可用: {data.get('cuda_name', 'Unknown')}"
                if data.get("cuda_available")
                else "CUDA 不可用"
            )
            return True, f"环境就绪（独立 venv；{cuda_msg}）", []

        except subprocess.TimeoutExpired:
            return False, "独立环境检测超时", []
        except Exception as e:
            return False, f"独立环境检测异常: {str(e)}", []

    @staticmethod
    def check_full_env_status_fast() -> Tuple[bool, str, List[str]]:
        """快速检查 IndexTTS2 独立 venv 是否就绪（子进程）。

        与 `check_full_env_status()` 的区别：
        - 不 import torch / 不探测 CUDA
        - 只检查 venv 是否存在、依赖模块是否可 find_spec

        该方法适合在 UI 线程调用，用来避免 Windows 上 import torch 带来的 1-2s 卡顿。
        """
        import json

        paths = get_runtime_paths()
        if not os.path.exists(paths.venv_python):
            missing = [pkg_name for _, pkg_name in _CHECK_IMPORTS]
            return False, "未安装 IndexTTS2 独立环境", missing

        check_script = """
import importlib.util
import json

deps = %s
missing = []

for import_name, pkg_name in deps:
    try:
        if importlib.util.find_spec(import_name) is None:
            missing.append(pkg_name)
    except Exception:
        missing.append(pkg_name)

print(json.dumps({"missing": missing}, ensure_ascii=False))
""" % (repr(_CHECK_IMPORTS))

        try:
            creation_flags = 0x08000000 if sys.platform == "win32" else 0
            proc = subprocess.run(
                [paths.venv_python, "-c", check_script],
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=creation_flags,
            )

            if proc.returncode != 0:
                return False, "独立环境检测失败（Python/依赖异常）", []

            data = json.loads((proc.stdout or "").strip() or "{}")
            missing = data.get("missing", [])
            if missing:
                return False, f"缺少依赖: {', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}", missing
            return True, "环境就绪（独立 venv）", []

        except subprocess.TimeoutExpired:
            return False, "独立环境检测超时", []
        except Exception as e:
            return False, f"独立环境检测异常: {str(e)}", []

    @staticmethod
    def check_cuda_available() -> Tuple[bool, str]:
        """检查独立 venv 中 CUDA 是否可用（子进程）。"""
        import re

        paths = get_runtime_paths()
        if not os.path.exists(paths.venv_python):
            return False, "未安装 IndexTTS2 独立环境"

        check_script = (
            "import torch; "
            "print('CUDA_AVAILABLE:', torch.cuda.is_available()); "
            "print('DEVICE_NAME:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
        )

        try:
            creation_flags = 0x08000000 if sys.platform == "win32" else 0
            result = subprocess.run(
                [paths.venv_python, "-c", check_script],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=creation_flags,
            )

            if result.returncode != 0:
                return False, "独立环境 PyTorch 异常（无法加载）"

            output = result.stdout or ""
            if "CUDA_AVAILABLE: True" in output:
                match = re.search(r"DEVICE_NAME: (.+)", output)
                device_name = match.group(1).strip() if match else "Unknown GPU"
                return True, f"CUDA 可用: {device_name}"

            return False, "CUDA 不可用，将使用 CPU 模式"

        except subprocess.TimeoutExpired:
            return False, "环境检测超时（PyTorch 加载过慢）"
        except Exception as e:
            return False, f"环境检测失败: {str(e)}"

    @staticmethod
    def check_dependencies_installed() -> Tuple[bool, List[str]]:
        """检查独立 venv 是否安装完毕（通过子进程）。"""
        is_ready, _, missing = IndexTTSEnvUtility.check_full_env_status()
        return is_ready, missing

    @Slot(bool, str)
    def install_dependencies(self, use_cuda: bool = True, mirror: str = "default"):
        """安装 IndexTTS2 独立环境（Runtime/IndexTTS2/.venv）。"""
        self._is_cancelled = False

        try:
            self._ensure_uv_installed()
            ensure_runtime_pyproject()
            paths = get_runtime_paths()

            self.progress_signal.emit(0.02, "准备独立环境...")
            self.log_signal.emit(f"GUI Python: {self._python_path}")
            self.log_signal.emit(f"Runtime: {paths.runtime_root}")

            pypi_index = PYPI_MIRRORS.get(mirror, PYPI_MIRRORS["default"])
            torch_backend = "cu128" if use_cuda else "cpu"
            self.log_signal.emit(f"PyPI 源: {pypi_index}")
            self.log_signal.emit(f"PyTorch 后端: {torch_backend}")

            # IMPORTANT:
            # - `uv pip sync` is designed for `requirements.txt`/`uv.lock` workflows and will
            #   typically install packages without resolving transitive dependencies when fed
            #   only a `pyproject.toml`.
            # - The upstream IndexTTS2 README uses `uv sync`; we follow that so dependencies
            #   like `huggingface_hub` (required by transformers) are installed correctly.
            # - Our Runtime folder is not a full, buildable project; use `--no-install-project`.
            self.progress_signal.emit(0.08, "使用 uv 同步依赖（生成 lockfile；可能需要较长时间）...")

            cmd = [
                self._python_path,
                "-m",
                "uv",
                "sync",
                "--project",
                paths.runtime_root,
                "--no-install-project",
                "--no-dev",
                "--python",
                self._python_path,
                "--no-python-downloads",
                "--default-index",
                pypi_index,
                "--color",
                "never",
            ]
            # CPU 模式：忽略 `tool.uv.sources`（即忽略 PyTorch CUDA 专用 index），让 torch 从默认源安装。
            if not use_cuda:
                cmd.append("--no-sources")

            self._run_uv_sync_with_smooth_progress(
                cmd,
                base_progress=0.08,
                end_progress=0.90,
                title="同步依赖",
            )

            self.progress_signal.emit(0.95, "验证独立环境...")
            is_ok, missing = self.check_dependencies_installed()
            if is_ok:
                self.progress_signal.emit(1.0, "独立环境安装完成")
                self.finished_signal.emit(True)
            else:
                self.error_signal.emit(f"部分依赖缺失: {', '.join(missing)}")
                self.finished_signal.emit(False)

        except Exception as e:
            import traceback

            self.error_signal.emit(f"安装失败: {e}\n{traceback.format_exc()}")
            self.finished_signal.emit(False)

    @Slot()
    def uninstall_dependencies(self):
        """卸载 IndexTTS2：删除 Runtime/IndexTTS2/.venv。"""
        self._is_cancelled = False

        try:
            paths = get_runtime_paths()
            if not os.path.exists(paths.venv_dir):
                self.progress_signal.emit(1.0, "未发现独立 venv，无需卸载")
                self.finished_signal.emit(True)
                return

            self.progress_signal.emit(0.1, "正在删除独立 venv...")
            self._safe_rmtree(paths.venv_dir)
            self.progress_signal.emit(1.0, "卸载完成（已删除独立 venv）")
            self.finished_signal.emit(True)

        except Exception as e:
            import traceback

            self.error_signal.emit(f"卸载失败: {e}\n{traceback.format_exc()}")
            self.finished_signal.emit(False)

    def _run_cmd_stream(self, cmd: List[str]) -> None:
        """运行命令并实时回传输出；支持取消。"""
        self.log_signal.emit(f"执行: {' '.join(cmd)}")

        creation_flags = 0x08000000 if sys.platform == "win32" else 0
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )

        assert process.stdout is not None
        last_lines: List[str] = []
        for line in process.stdout:
            if self._is_cancelled:
                try:
                    process.terminate()
                except Exception:
                    pass
                raise RuntimeError("操作已取消")

            line = line.rstrip("\n")
            if line.strip():
                self.log_signal.emit(line)
                last_lines.append(line)
                if len(last_lines) > 80:
                    last_lines.pop(0)

        rc = process.wait()
        if rc != 0:
            tail = "\n".join(last_lines[-30:])
            if tail.strip():
                raise RuntimeError(f"命令执行失败 (exit={rc})\n\n--- last output ---\n{tail}")
            raise RuntimeError(f"命令执行失败 (exit={rc})")

    @staticmethod
    def _bytes_to_gb(num_bytes: int) -> float:
        return max(0.0, float(num_bytes) / (1024.0 ** 3))

    @staticmethod
    def _parse_size_to_bytes(size_text: str) -> int:
        """解析 uv 输出里的大小文本，如 4.5MiB / 3.2GiB。"""
        m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([KMG]iB)\s*$", size_text)
        if not m:
            return 0
        num = float(m.group(1))
        unit = m.group(2)
        factor = {"KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}.get(unit, 0)
        return int(num * factor)

    def _run_uv_sync_with_smooth_progress(
        self,
        cmd: List[str],
        *,
        base_progress: float,
        end_progress: float,
        title: str,
    ) -> None:
        """运行 uv sync，并基于 stdout 文本输出估算“总体百分比/已下载 GB”。

        说明：uv 在非 TTY 下不会提供逐字节进度。之前通过遍历 cache 目录体积来估算，
        在 Windows 上可能导致 uv 临时文件重命名时出现“拒绝访问 (os error 5)”。
        这里改成只解析 `Downloading xxx (10.0MiB)` / `Downloaded xxx` 行，
        并用“历史平均下载速率 + 时间插值”让单个依赖下载期间进度条持续滑动。
        """
        import queue
        import threading

        self.log_signal.emit(f"执行: {' '.join(cmd)}")

        creation_flags = 0x08000000 if sys.platform == "win32" else 0
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )

        assert process.stdout is not None
        q: "queue.Queue[str]" = queue.Queue()
        last_lines: List[str] = []
        last_activity_text = ""

        def _reader():
            try:
                for raw in process.stdout:
                    q.put(raw)
            finally:
                try:
                    process.stdout.close()
                except Exception:
                    pass

        t = threading.Thread(target=_reader, daemon=True)
        t.start()

        # download accounting
        total_known_bytes = 0
        downloaded_done_bytes = 0
        current_pkg = ""
        current_pkg_size = 0
        current_pkg_start_ts: float | None = None
        avg_rate_bps = 0.0  # moving average bytes/sec

        last_tick = 0.0
        last_emit = 0.0

        downloading_re = re.compile(r"^Downloading\s+(.+?)\s+\(([^)]+)\)\s*$")
        downloaded_re = re.compile(r"^Downloaded\s+(.+?)\s*$")

        def _estimate_current_bytes(now: float) -> int:
            if not current_pkg or current_pkg_size <= 0 or current_pkg_start_ts is None:
                return 0
            # 如果没有历史速率，给一个保守默认值（不会太快也不会卡住）
            rate = avg_rate_bps if avg_rate_bps > 0 else 12 * 1024 * 1024
            est = int((now - current_pkg_start_ts) * rate)
            # 不要超过 95%，等待真正的 Downloaded 行来“结算”
            return min(int(current_pkg_size * 0.95), max(0, est))

        def _emit_progress(force: bool = False):
            nonlocal last_emit
            now = time.time()
            if not force and (now - last_emit) < 0.25:
                return
            last_emit = now

            est_current = _estimate_current_bytes(now)
            denom = max(1, total_known_bytes if total_known_bytes > 0 else (downloaded_done_bytes + max(1, current_pkg_size)))
            ratio = min(1.0, float(downloaded_done_bytes + est_current) / float(denom))
            progress = base_progress + (end_progress - base_progress) * ratio

            downloaded_gb = self._bytes_to_gb(downloaded_done_bytes + est_current)
            total_gb = self._bytes_to_gb(denom)
            pct = min(99.9, max(0.0, ratio * 100.0))

            line1 = title
            if last_activity_text:
                line1 = f"{title}: {last_activity_text}"
            line2 = f"{pct:.1f}% | 已下载 {downloaded_gb:.2f} / ~{total_gb:.2f} GB"
            self.progress_signal.emit(progress, f"{line1}\n{line2}")

        _emit_progress(force=True)

        while True:
            if self._is_cancelled:
                try:
                    process.terminate()
                except Exception:
                    pass
                raise RuntimeError("操作已取消")

            try:
                raw = q.get(timeout=0.15)
            except queue.Empty:
                raw = None

            if raw is not None:
                line = raw.rstrip("\n")
                if line.strip():
                    self.log_signal.emit(line)
                    last_lines.append(line)
                    if len(last_lines) > 120:
                        last_lines.pop(0)

                    # 试图从输出中提取“当前包/动作”，用于第一行展示
                    s = line.strip()
                    # 常见模式："Downloaded numpy" / "Downloading numpy" / "Installing ..."
                    for prefix in ("Downloading ", "Downloaded ", "Installing ", "Installed "):
                        if s.startswith(prefix):
                            last_activity_text = s[len(prefix):].strip()
                            break

                    m1 = downloading_re.match(s)
                    if m1:
                        current_pkg = m1.group(1).strip()
                        size_bytes = self._parse_size_to_bytes(m1.group(2).strip())
                        current_pkg_size = size_bytes
                        current_pkg_start_ts = time.time()
                        if size_bytes > 0:
                            total_known_bytes += size_bytes

                    m2 = downloaded_re.match(s)
                    if m2 and current_pkg:
                        # 结算当前包
                        now2 = time.time()
                        if current_pkg_start_ts is not None and current_pkg_size > 0:
                            dt = max(0.05, now2 - current_pkg_start_ts)
                            inst_rate = float(current_pkg_size) / dt
                            # 指数滑动平均，避免抖动
                            avg_rate_bps = inst_rate if avg_rate_bps <= 0 else (avg_rate_bps * 0.7 + inst_rate * 0.3)
                            downloaded_done_bytes += current_pkg_size

                        current_pkg = ""
                        current_pkg_size = 0
                        current_pkg_start_ts = None

                _emit_progress(force=True)

            rc = process.poll()
            now = time.time()
            if (now - last_tick) >= 0.5:
                last_tick = now
                _emit_progress(force=False)

            if rc is not None and q.empty():
                break

        rc = process.wait()
        _emit_progress(force=True)
        if rc != 0:
            tail = "\n".join(last_lines[-30:])
            if tail.strip():
                raise RuntimeError(f"命令执行失败 (exit={rc})\n\n--- last output ---\n{tail}")
            raise RuntimeError(f"命令执行失败 (exit={rc})")

    def _safe_rmtree(self, path: str) -> None:
        if not os.path.exists(path):
            return

        def _onerror(func, p, exc_info):
            try:
                os.chmod(p, 0o777)
            except Exception:
                pass
            try:
                func(p)
            except Exception:
                pass

        last_err: Optional[Exception] = None
        for _ in range(5):
            try:
                shutil.rmtree(path, onerror=_onerror)
                return
            except Exception as e:
                last_err = e
                time.sleep(0.5)

        if last_err:
            raise last_err

    @staticmethod
    def get_install_size_estimate() -> str:
        """获取安装大小估算"""
        return "约 3-5 GB（含 PyTorch CUDA）"
