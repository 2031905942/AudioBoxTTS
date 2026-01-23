"""IndexTTS2 TTS 服务层

复用 engine_worker.py 的通信协议，通过子进程与推理引擎交互。
"""

import asyncio
import base64
import json
import logging
import os
import subprocess
import tempfile
import time
import wave
import shutil
import threading
from typing import Any, Dict, Optional

from ..models.schemas import SynthesizeRequest, SynthesizeResponse

logger = logging.getLogger(__name__)


class TTSService:
    """TTS 服务（复用 engine_worker.py 的通信协议）"""

    def __init__(
        self,
        model_dir: str,
        runtime_python: str,
        engine_worker: str,
        source_dir: str,
        hf_cache_dir: Optional[str] = None,
        use_fp16: bool = False,
        use_cuda_kernel: bool = True,
        load_timeout: float = 180,
        synthesize_timeout: float = 300,
    ):
        """
        初始化 TTS 服务

        Args:
            model_dir: 模型目录路径 (包含 config.yaml, gpt.pth 等)
            runtime_python: IndexTTS2 运行时 Python 解释器路径
            engine_worker: engine_worker.py 脚本路径
            source_dir: Source 目录路径 (用于 PYTHONPATH)
            hf_cache_dir: HuggingFace 缓存目录
            use_fp16: 是否使用半精度推理
            use_cuda_kernel: 是否使用 CUDA kernel 加速
        """
        self.model_dir = model_dir
        self.runtime_python = runtime_python
        self.engine_worker = engine_worker
        self.source_dir = source_dir
        self.hf_cache_dir = hf_cache_dir or os.path.join(model_dir, "hf_cache")
        self.use_fp16 = use_fp16
        self.use_cuda_kernel = use_cuda_kernel

        self.load_timeout = float(load_timeout)
        self.synthesize_timeout = float(synthesize_timeout)

        self._proc: Optional[subprocess.Popen] = None
        self._lock = asyncio.Lock()
        self._model_loaded = False
        self._device = "未加载"

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stdout_queue: Optional[asyncio.Queue[str]] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None

    @property
    def is_model_loaded(self) -> bool:
        """模型是否已加载"""
        return (
            self._model_loaded
            and self._proc is not None
            and self._proc.poll() is None
        )

    @property
    def device(self) -> str:
        """当前推理设备"""
        return self._device

    async def start_engine(self) -> None:
        """启动推理引擎子进程"""
        if self._proc is not None and self._proc.poll() is None:
            return

        # 验证路径
        if not os.path.exists(self.runtime_python):
            raise RuntimeError(f"Python 解释器不存在: {self.runtime_python}")
        if not os.path.exists(self.engine_worker):
            raise RuntimeError(f"引擎脚本不存在: {self.engine_worker}")

        env = os.environ.copy()
        env["PYTHONPATH"] = self.source_dir
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONNOUSERSITE"] = "1"
        env["HF_HOME"] = self.hf_cache_dir
        env["HF_HUB_CACHE"] = self.hf_cache_dir

        logger.info(f"启动推理引擎: {self.runtime_python} {self.engine_worker}")

        self._proc = subprocess.Popen(
            [self.runtime_python, self.engine_worker],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )

        # 启动 stdout 读取线程（避免 readline 永久阻塞导致超时失效）
        self._loop = asyncio.get_running_loop()
        self._stdout_queue = asyncio.Queue()

        def _reader_loop(proc: subprocess.Popen):
            try:
                if proc.stdout is None or self._stdout_queue is None or self._loop is None:
                    return
                for line in iter(proc.stdout.readline, ""):
                    # 跨线程安全投递到 asyncio 队列
                    try:
                        self._loop.call_soon_threadsafe(self._stdout_queue.put_nowait, line)
                    except Exception:
                        break
            finally:
                # EOF
                try:
                    if self._loop is not None and self._stdout_queue is not None:
                        self._loop.call_soon_threadsafe(self._stdout_queue.put_nowait, "")
                except Exception:
                    pass

        self._reader_thread = threading.Thread(
            target=_reader_loop, args=(self._proc,), daemon=True
        )
        self._reader_thread.start()

        # Drain stderr to avoid subprocess blocking when stderr pipe buffer fills.
        def _stderr_loop(proc: subprocess.Popen):
            try:
                if proc.stderr is None:
                    return
                for line in iter(proc.stderr.readline, ""):
                    line = (line or "").rstrip("\n")
                    if line:
                        logger.debug(f"engine stderr: {line}")
            except Exception:
                return

        self._stderr_thread = threading.Thread(
            target=_stderr_loop, args=(self._proc,), daemon=True
        )
        self._stderr_thread.start()

        # 等待 ready 消息（10秒）
        msg = await self._wait_for_result({"ready"}, timeout=10)
        logger.info(f"引擎已就绪, PID={msg.get('pid')}")

    async def load_model(self) -> None:
        """加载模型"""
        await self.start_engine()

        cfg_path = os.path.join(self.model_dir, "config.yaml")
        if not os.path.exists(cfg_path):
            raise RuntimeError(f"配置文件不存在: {cfg_path}")

        cmd = {
            "cmd": "load_model",
            "payload": {
                "model_dir": self.model_dir,
                "cfg_path": cfg_path,
                "use_fp16": self.use_fp16,
                "use_cuda_kernel": self.use_cuda_kernel,
                "use_deepspeed": False,
            },
        }

        async with self._lock:
            self._send_cmd(cmd)
            # 等待加载完成
            result = await self._wait_for_result({"loaded"}, timeout=self.load_timeout)
        self._model_loaded = True
        self._device = result.get("device", "Unknown")
        logger.info(f"模型加载完成, device={self._device}")

    async def synthesize(self, request: SynthesizeRequest) -> SynthesizeResponse:
        """
        合成语音

        Args:
            request: 合成请求

        Returns:
            合成响应
        """
        if not self.is_model_loaded:
            return SynthesizeResponse(success=False, error="模型未加载")

        spk_audio_path: Optional[str] = None
        spk_audio_input_path: Optional[str] = None
        output_path: Optional[str] = None

        try:
            # 1. 解码并保存参考音频
            try:
                audio_b64 = request.speaker_audio_base64.strip()
                # 兼容 data URL: data:audio/wav;base64,xxxx
                if "," in audio_b64 and "base64" in audio_b64.split(",", 1)[0].lower():
                    audio_b64 = audio_b64.split(",", 1)[1]
                audio_bytes = base64.b64decode(audio_b64)
            except Exception as e:
                return SynthesizeResponse(
                    success=False, error=f"无效的音频base64编码: {e}"
                )

            # 尽量保证输入是 WAV：如果不是 WAV，尝试使用 ffmpeg 转换
            spk_audio_path, spk_audio_input_path = self._prepare_speaker_audio(audio_bytes)
            if spk_audio_path is None:
                return SynthesizeResponse(
                    success=False,
                    error=(
                        "参考音频不是 WAV，且无法转换。请上传 WAV，"
                        "或在服务器上安装 ffmpeg 以支持 mp3/m4a 等格式。"
                    ),
                )

            # 2. 准备输出路径
            output_path = tempfile.mktemp(suffix=".wav")

            # 3. 构建合成命令
            generation_kwargs: Dict[str, Any] = {"do_sample": True}
            if request.temperature is not None:
                generation_kwargs["temperature"] = request.temperature
            if request.top_p is not None:
                generation_kwargs["top_p"] = request.top_p
            if request.top_k is not None:
                generation_kwargs["top_k"] = request.top_k
            if request.repetition_penalty is not None:
                generation_kwargs["repetition_penalty"] = request.repetition_penalty

            cmd = {
                "cmd": "synthesize",
                "payload": {
                    "spk_audio_prompt": spk_audio_path,
                    "text": request.text.strip(),
                    "output_path": output_path,
                    "emo_mode": int(request.emo_mode),
                    "emo_vector": request.emo_vector or [0.0] * 8,
                    "emo_alpha": request.emo_weight,
                    "generation_kwargs": generation_kwargs,
                },
            }

            async with self._lock:
                self._send_cmd(cmd)
                # 4. 等待结果（由配置控制超时；默认与队列 request_timeout 对齐）
                result = await self._wait_for_result(
                    {"synthesized"}, timeout=self.synthesize_timeout
                )

            actual_output = result.get("output_path", output_path)
            sample_rate = int(result.get("sample_rate", 22050))

            if not os.path.exists(actual_output):
                return SynthesizeResponse(
                    success=False, error="推理完成但未生成文件"
                )

            # 5. 读取并编码输出音频
            with open(actual_output, "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode("utf-8")

            # 6. 获取音频时长
            duration = self._get_wav_duration(actual_output)

            return SynthesizeResponse(
                success=True,
                audio_base64=audio_base64,
                sample_rate=sample_rate,
                duration_seconds=duration,
            )

        except RuntimeError as e:
            logger.error(f"合成失败: {e}")
            return SynthesizeResponse(success=False, error=str(e))
        except Exception as e:
            logger.exception(f"合成异常: {e}")
            return SynthesizeResponse(success=False, error=f"内部错误: {e}")
        finally:
            # 清理临时文件
            for path in [spk_audio_path, spk_audio_input_path, output_path]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception:
                        pass

    def _prepare_speaker_audio(
        self, audio_bytes: bytes
    ) -> tuple[Optional[str], Optional[str]]:
        """准备参考音频文件

        返回: (wav_path, original_input_path)
        - 如果本来就是 WAV，则 original_input_path 为 None
        - 如果需要转换，则 original_input_path 为转换前的临时文件
        """
        if self._looks_like_wav(audio_bytes):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                return f.name, None

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return None, None

        with tempfile.NamedTemporaryFile(suffix=".input", delete=False) as fin:
            fin.write(audio_bytes)
            input_path = fin.name

        output_wav = tempfile.mktemp(suffix=".wav")

        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    input_path,
                    "-ac",
                    "1",
                    output_wav,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return output_wav, input_path
        except Exception as e:
            logger.warning(f"ffmpeg 转换参考音频失败: {e}")
            # 转换失败时清理输出
            try:
                if os.path.exists(output_wav):
                    os.unlink(output_wav)
            except Exception:
                pass
            return None, input_path

    @staticmethod
    def _looks_like_wav(data: bytes) -> bool:
        """粗略判断是否为 WAV (RIFF/WAVE)"""
        return len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"

    def _send_cmd(self, cmd: Dict[str, Any]) -> None:
        """发送命令到引擎"""
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("引擎未启动")
        self._proc.stdin.write(json.dumps(cmd, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    async def _wait_for_result(
        self, ok_types: set, timeout: float
    ) -> Dict[str, Any]:
        """等待引擎返回结果"""
        if self._proc is None:
            raise RuntimeError("引擎未启动")
        if self._stdout_queue is None:
            raise RuntimeError("引擎输出通道未就绪")

        end_time = time.time() + float(timeout)
        while True:
            remaining = end_time - time.time()
            if remaining <= 0:
                # 超时：主动重启引擎，避免一次卡死拖垮后续请求
                await self._restart_engine_on_failure("等待引擎响应超时")
                raise RuntimeError("等待引擎响应超时")

            try:
                line = await asyncio.wait_for(self._stdout_queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                await self._restart_engine_on_failure("等待引擎响应超时")
                raise RuntimeError("等待引擎响应超时")

            if not line:
                rc = self._proc.poll()
                if rc is not None:
                    stderr = ""
                    if self._proc.stderr:
                        stderr = self._proc.stderr.read()[:500]
                    raise RuntimeError(f"引擎进程已退出 (exit={rc}): {stderr}")
                # 可能是 reader 线程投递的 EOF，但进程尚未退出，稍等再看
                await asyncio.sleep(0.05)
                continue

            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "progress":
                # 进度消息，记录日志
                logger.debug(
                    f"进度: {msg.get('value', 0):.1%} - {msg.get('desc', '')}"
                )
                continue

            if msg_type == "error":
                # 引擎内部错误：重启以恢复服务可用性
                await self._restart_engine_on_failure(msg.get("message", "引擎返回错误"))
                raise RuntimeError(msg.get("message", "引擎返回错误"))

            if msg_type in ok_types:
                return msg

    async def _restart_engine_on_failure(self, reason: str) -> None:
        """在引擎卡死/错误时进行自愈重启。

        目标：避免一次卡死导致队列 worker 永远阻塞。
        """
        logger.warning(f"引擎异常，准备重启: {reason}")
        try:
            await self.shutdown()
        except Exception:
            pass
        try:
            await self.start_engine()
            await self.load_model()
        except Exception as e:
            logger.error(f"引擎重启失败: {e}")

    def _get_wav_duration(self, path: str) -> Optional[float]:
        """获取 WAV 文件时长"""
        try:
            with wave.open(path, "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / float(rate)
        except Exception:
            return None

    async def shutdown(self) -> None:
        """关闭引擎"""
        if self._proc is None:
            return

        try:
            if self._proc.poll() is None and self._proc.stdin is not None:
                self._send_cmd({"cmd": "shutdown", "payload": {}})
                await asyncio.sleep(0.5)
        except Exception:
            pass

        try:
            if self._proc.poll() is None:
                self._proc.terminate()
                await asyncio.sleep(1)
            if self._proc.poll() is None:
                self._proc.kill()
        except Exception:
            pass

        self._proc = None
        self._model_loaded = False
        self._device = "未加载"
        self._stdout_queue = None
        self._loop = None
        logger.info("引擎已关闭")
