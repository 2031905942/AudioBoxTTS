"""IndexTTS2 推理控制器（GUI 安全隔离版）。

设计目标：
- GUI 主进程不 import torch/transformers/indextts；
- 推理、模型加载都在独立 venv 的子进程中执行；
- 子进程崩溃/显存泄漏不拖死 GUI。

该类仍保留原有信号/槽接口，以适配现有 UI/Job 映射。
"""

import json
import os
import subprocess
import sys
import threading
import time
from typing import Optional, List

from PySide6.QtCore import QObject, Signal, Slot, QMutex, QMutexLocker

from Source.Utility.indextts_runtime_utility import get_runtime_paths


class IndexTTSUtility(QObject):
    """IndexTTS2 推理 Worker（运行在子线程）。

    信号：
        update_progress_signal(float, str): 进度更新 (0.0-1.0, 描述)
        error_signal(str): 错误消息
        generated_signal(str, int): 生成完成 (wav路径, 采样率)
        model_loaded_signal(): 模型加载完成
    """

    update_progress_signal = Signal(float, str)
    error_signal = Signal(str)
    generated_signal = Signal(str, int)
    model_loaded_signal = Signal()

    # 情感控制模式常量
    EMO_MODE_SAME_AS_SPEAKER = 0  # 与音色参考音频相同
    EMO_MODE_VECTOR = 2           # 使用情感向量控制

    # 情感向量标签（8维）
    EMO_LABELS = ["喜", "怒", "哀", "惧", "厌恶", "低落", "惊喜", "平静"]

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._model_dir: str = ""
        self._is_loading: bool = False

        self._engine_proc: Optional[subprocess.Popen] = None
        self._engine_stderr_thread: Optional[threading.Thread] = None
        self._engine_stderr_tail: List[str] = []
        self._device: str = "未加载"

    @property
    def is_model_loaded(self) -> bool:
        """模型是否已加载"""
        proc = self._engine_proc
        return proc is not None and proc.poll() is None and bool(self._model_dir)

    @property
    def model_dir(self) -> str:
        """当前模型目录"""
        return self._model_dir

    @property
    def device(self) -> str:
        """当前设备"""
        return self._device

    @staticmethod
    def get_default_model_dir() -> str:
        """获取默认模型目录
        
        优先使用 AudioBox/checkpoints，若不存在则尝试 index-tts/checkpoints
        """
        # AudioBox 根目录
        audiobox_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        audiobox_ckpt = os.path.join(audiobox_root, "checkpoints")
        return audiobox_ckpt

    @staticmethod
    def get_required_files() -> List[str]:
        """获取必需的模型文件列表"""
        return [
            "bpe.model",
            "config.yaml",
            "gpt.pth",
            "s2mel.pth",
            "wav2vec2bert_stats.pt",
        ]

    @staticmethod
    def check_model_files(model_dir: str) -> tuple[bool, List[str]]:
        """检查模型文件是否完整

        Returns:
            (是否完整, 缺失文件列表)
        """
        missing = []
        for f in IndexTTSUtility.get_required_files():
            fp = os.path.join(model_dir, f)
            if not os.path.exists(fp):
                missing.append(f)
                continue
            # 轻量完整性：避免空文件/截断文件被当作“存在即可”。
            try:
                if os.path.getsize(fp) <= 0:
                    missing.append(f)
            except Exception:
                missing.append(f)
        return len(missing) == 0, missing

    @Slot(str, bool, bool, bool)
    def load_model(self, model_dir: str, use_fp16: bool = False,
                   use_cuda_kernel: bool = False, use_deepspeed: bool = False):
        """加载模型（在工作线程调用）

        Args:
            model_dir: 模型目录路径
            use_fp16: 是否使用半精度
            use_cuda_kernel: 是否使用 CUDA kernel
            use_deepspeed: 是否使用 DeepSpeed
        """
        with QMutexLocker(self._mutex):
            if self._is_loading:
                self.error_signal.emit("模型正在加载中，请稍候")
                return

            self._is_loading = True

        try:
            self.update_progress_signal.emit(0.05, "检查模型文件...")

            is_complete, missing = self.check_model_files(model_dir)
            if not is_complete:
                self.error_signal.emit(f"模型文件不完整，缺少: {', '.join(missing)}")
                return

            paths = get_runtime_paths()
            if not os.path.exists(paths.venv_python):
                self.error_signal.emit("未安装 IndexTTS2 独立环境，请先安装环境依赖")
                return

            self.update_progress_signal.emit(0.12, "启动独立推理引擎...")
            self._ensure_engine_started()

            self.update_progress_signal.emit(0.18, "加载模型（独立子进程）...")
            cfg_path = os.path.join(model_dir, "config.yaml")
            self._send_cmd(
                "load_model",
                {
                    "model_dir": model_dir,
                    "cfg_path": cfg_path,
                    "use_fp16": use_fp16,
                    "use_cuda_kernel": use_cuda_kernel,
                    "use_deepspeed": use_deepspeed,
                },
            )

            resp = self._wait_for_result({"loaded"}, timeout=180)
            self._device = resp.get("device") or "Unknown"
            self._model_dir = model_dir

            self.update_progress_signal.emit(1.0, "模型加载完成（独立子进程）")
            self.model_loaded_signal.emit()

        except Exception as e:
            import traceback

            self.error_signal.emit(f"模型加载失败: {e}\n{traceback.format_exc()}")
        finally:
            with QMutexLocker(self._mutex):
                self._is_loading = False

    @Slot(str, str, str, int, list, float)
    def synthesize(self, spk_audio_path: str, text: str, output_path: str,
                   emo_mode: int = 0, emo_vector: Optional[List[float]] = None,
                   emo_weight: float = 1.0):
        """合成语音（在工作线程调用）

        Args:
            spk_audio_path: 音色参考音频路径
            text: 要合成的文本
            output_path: 输出 wav 路径
            emo_mode: 情感模式 (0=与音色相同, 2=向量控制)
            emo_vector: 情感向量 [喜,怒,哀,惧,厌恶,低落,惊喜,平静]，仅 emo_mode=2 时有效
            emo_weight: 情感权重 0.0-1.0
        """
        if not self.is_model_loaded:
            self.error_signal.emit("模型未加载")
            return

        if not text or not text.strip():
            self.error_signal.emit("文本不能为空")
            return

        if not os.path.exists(spk_audio_path):
            self.error_signal.emit(f"参考音频不存在: {spk_audio_path}")
            return

        try:
            self.update_progress_signal.emit(0.05, "准备推理（独立子进程）...")
            self._send_cmd(
                "synthesize",
                {
                    "spk_audio_prompt": spk_audio_path,
                    "text": text.strip(),
                    "output_path": output_path,
                    "emo_mode": int(emo_mode),
                    "emo_vector": emo_vector if emo_vector else [0.0] * 8,
                    "emo_alpha": float(emo_weight),
                },
            )

            resp = self._wait_for_result({"synthesized"}, timeout=600)
            out_path = resp.get("output_path") or output_path
            sample_rate = int(resp.get("sample_rate") or 22050)

            if os.path.exists(out_path):
                self.update_progress_signal.emit(1.0, "生成完成")
                self.generated_signal.emit(out_path, sample_rate)
            else:
                self.error_signal.emit("推理完成但未生成文件")

        except Exception as e:
            import traceback

            self.error_signal.emit(f"推理失败: {e}\n{traceback.format_exc()}")

    def unload_model(self):
        """卸载模型，释放显存"""
        with QMutexLocker(self._mutex):
            self._shutdown_engine()
            self._model_dir = ""
            self._device = "未加载"

    def _ensure_engine_started(self) -> None:
        if self._engine_proc is not None and self._engine_proc.poll() is None:
            return

        paths = get_runtime_paths()
        if not os.path.exists(paths.venv_python):
            raise RuntimeError("独立 venv 不存在")
        if not os.path.exists(paths.engine_worker):
            raise RuntimeError("找不到独立引擎脚本")

        env = os.environ.copy()
        source_dir = os.path.join(paths.repo_root, "Source")
        old_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = source_dir if not old_pp else (source_dir + os.pathsep + old_pp)
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONUNBUFFERED"] = "1"

        hf_cache = os.path.join(paths.repo_root, "checkpoints", "hf_cache")
        env["HF_HOME"] = hf_cache
        env["HF_HUB_CACHE"] = hf_cache

        creation_flags = 0x08000000 if sys.platform == "win32" else 0
        self._engine_proc = subprocess.Popen(
            [paths.venv_python, paths.engine_worker],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            creationflags=creation_flags,
        )

        assert self._engine_proc.stdout is not None
        # 启动后第一条应该是 ready；若不是，继续尝试读取几行。
        deadline = time.time() + 5
        while time.time() < deadline:
            line = self._engine_proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line.strip())
            except Exception:
                continue
            if msg.get("type") == "ready":
                break

        # 后台清空 stderr，避免缓冲区写满导致卡死
        if self._engine_proc.stderr is not None:
            self._engine_stderr_thread = threading.Thread(
                target=self._drain_engine_stderr,
                args=(self._engine_proc.stderr,),
                daemon=True,
            )
            self._engine_stderr_thread.start()

    def _drain_engine_stderr(self, stderr_pipe):
        for line in stderr_pipe:
            if not line:
                break
            line = line.rstrip("\n")
            if not line.strip():
                continue
            self._engine_stderr_tail.append(line)
            if len(self._engine_stderr_tail) > 50:
                self._engine_stderr_tail = self._engine_stderr_tail[-50:]

    def _send_cmd(self, cmd: str, payload: dict) -> None:
        self._ensure_engine_started()
        assert self._engine_proc is not None
        assert self._engine_proc.stdin is not None

        self._engine_proc.stdin.write(json.dumps({"cmd": cmd, "payload": payload}, ensure_ascii=False) + "\n")
        self._engine_proc.stdin.flush()

    def _wait_for_result(self, ok_types: set[str], timeout: float) -> dict:
        assert self._engine_proc is not None
        assert self._engine_proc.stdout is not None

        end = time.time() + timeout
        while time.time() < end:
            line = self._engine_proc.stdout.readline()
            if not line:
                rc = self._engine_proc.poll()
                if rc is not None:
                    tail = "\n".join(self._engine_stderr_tail[-15:])
                    raise RuntimeError(f"引擎子进程已退出 (exit={rc})\n{tail}")
                time.sleep(0.05)
                continue

            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except Exception:
                continue

            msg_type = msg.get("type")

            if msg_type == "progress":
                try:
                    v = float(msg.get("value") or 0.0)
                except Exception:
                    v = 0.0
                desc = msg.get("desc") or ""
                mapped = 0.1 + max(0.0, min(1.0, v)) * 0.8
                self.update_progress_signal.emit(mapped, desc)
                continue

            if msg_type == "error":
                raise RuntimeError(msg.get("message") or "引擎返回错误")

            if msg_type in ok_types:
                return msg

        raise RuntimeError("等待引擎响应超时")

    def _shutdown_engine(self) -> None:
        proc = self._engine_proc
        if proc is None:
            return

        try:
            if proc.poll() is None and proc.stdin is not None:
                try:
                    proc.stdin.write(json.dumps({"cmd": "shutdown", "payload": {}}, ensure_ascii=False) + "\n")
                    proc.stdin.flush()
                except Exception:
                    pass
        finally:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass

            self._engine_proc = None
