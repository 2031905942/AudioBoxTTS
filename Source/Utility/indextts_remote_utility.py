"""IndexTTS2 远程推理客户端

与 IndexTTSUtility 保持相同的信号/槽接口，通过 HTTP API 调用云端服务。
"""

import base64
import os
import threading
from typing import List, Optional

import requests
from PySide6.QtCore import QObject, Signal


class IndexTTSRemoteUtility(QObject):
    """IndexTTS2 远程推理客户端

    与 IndexTTSUtility 保持相同的信号接口，对 UI/Job 层透明。
    """

    # 信号定义（与 IndexTTSUtility 完全相同）
    update_progress_signal = Signal(float, str)
    error_signal = Signal(str)
    generated_signal = Signal(str, int)
    variant_generated_signal = Signal(int, str, int)  # index, wav_path, sample_rate
    variant_progress_signal = Signal(int, float, str)  # index, progress(0-1), desc
    variants_done_signal = Signal(list, int)  # wav_paths, sample_rate
    model_loaded_signal = Signal()

    # 情感控制模式常量（与 IndexTTSUtility 相同）
    EMO_MODE_SAME_AS_SPEAKER = 0
    EMO_MODE_VECTOR = 2
    EMO_LABELS = ["喜", "怒", "哀", "惧", "厌恶", "低落", "惊喜", "平静"]

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: float = 300,
        parent: Optional[QObject] = None,
    ):
        """
        初始化远程客户端

        Args:
            base_url: 云服务地址，如 "https://tts.example.com"
            api_key: API Key（如果服务端配置了认证）
            timeout: 请求超时时间（秒）
            parent: Qt 父对象
        """
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"
        if api_key:
            self._session.headers["X-API-Key"] = api_key

        self._model_loaded = False
        self._device = "远程服务"
        self._model_dir = ""

    @property
    def is_model_loaded(self) -> bool:
        """模型是否已加载（远程服务是否就绪）"""
        return self._model_loaded

    @property
    def model_dir(self) -> str:
        """当前模型目录（远程模式下为空）"""
        return self._model_dir

    @property
    def device(self) -> str:
        """当前设备"""
        return self._device

    @staticmethod
    def get_default_model_dir() -> str:
        """获取默认模型目录（远程模式不需要本地模型）"""
        return ""

    @staticmethod
    def get_required_files() -> List[str]:
        """获取必需的模型文件列表（远程模式不需要）"""
        return []

    @staticmethod
    def check_model_files(model_dir: str) -> tuple:
        """检查模型文件（远程模式总是返回完整）"""
        return True, []

    def load_model(
        self,
        model_dir: str = "",
        use_fp16: bool = False,
        use_cuda_kernel: bool = False,
        use_deepspeed: bool = False,
    ):
        """检查远程服务状态（模拟加载过程）

        远程模式下不需要真正加载模型，只需要检查服务是否可用。
        """
        try:
            self.update_progress_signal.emit(0.3, "检查远程服务状态...")

            resp = self._session.get(
                f"{self.base_url}/api/v1/health",
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("model_loaded"):
                self._model_loaded = True
                self._device = f"远程: {data.get('device', 'Unknown')}"
                queue_len = data.get("queue_length", 0)

                self.update_progress_signal.emit(1.0, f"远程服务就绪 (队列: {queue_len})")
                self.model_loaded_signal.emit()
            else:
                self.error_signal.emit("远程服务模型未加载，请联系管理员")

        except requests.Timeout:
            self.error_signal.emit("连接远程服务超时，请检查网络")
        except requests.ConnectionError:
            self.error_signal.emit(f"无法连接远程服务: {self.base_url}")
        except requests.HTTPError as e:
            self.error_signal.emit(f"远程服务错误: {e.response.status_code}")
        except Exception as e:
            self.error_signal.emit(f"连接远程服务失败: {e}")

    def synthesize(
        self,
        spk_audio_path: str,
        text: str,
        output_path: str,
        emo_mode: int = 0,
        emo_vector: Optional[List[float]] = None,
        emo_weight: float = 1.0,
    ):
        """合成语音（远程调用）

        Args:
            spk_audio_path: 音色参考音频路径
            text: 要合成的文本
            output_path: 输出 wav 路径
            emo_mode: 情感模式 (0=与音色相同, 2=向量控制)
            emo_vector: 情感向量 [喜,怒,哀,惧,厌恶,低落,惊喜,平静]
            emo_weight: 情感权重 0.0-1.0
        """
        if not self._model_loaded:
            self.error_signal.emit("远程服务未就绪，请先检查连接")
            return

        if not text or not text.strip():
            self.error_signal.emit("文本不能为空")
            return

        if not os.path.exists(spk_audio_path):
            self.error_signal.emit(f"参考音频不存在: {spk_audio_path}")
            return

        try:
            self.update_progress_signal.emit(0.1, "读取参考音频...")

            # 读取并编码参考音频
            with open(spk_audio_path, "rb") as f:
                spk_audio_base64 = base64.b64encode(f.read()).decode("utf-8")

            self.update_progress_signal.emit(0.2, "发送合成请求...")

            payload = {
                "text": text.strip(),
                "speaker_audio_base64": spk_audio_base64,
                "emo_mode": int(emo_mode),
                "emo_vector": emo_vector if emo_vector else [0.0] * 8,
                "emo_weight": float(emo_weight),
            }

            resp = self._session.post(
                f"{self.base_url}/api/v1/synthesize",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                self.update_progress_signal.emit(0.9, "保存音频文件...")

                # 解码并保存音频
                audio_bytes = base64.b64decode(data["audio_base64"])
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(audio_bytes)

                sample_rate = data.get("sample_rate", 22050)
                self.update_progress_signal.emit(1.0, "生成完成")
                self.generated_signal.emit(output_path, sample_rate)
            else:
                error_msg = data.get("error", "未知错误")
                self.error_signal.emit(f"合成失败: {error_msg}")

        except requests.Timeout:
            self.error_signal.emit("请求超时，服务可能繁忙，请稍后重试")
        except requests.HTTPError as e:
            status_code = e.response.status_code
            if status_code == 401:
                self.error_signal.emit("认证失败，请检查 API Key")
            elif status_code == 503:
                self.error_signal.emit("服务繁忙，请稍后重试")
            elif status_code == 504:
                self.error_signal.emit("请求处理超时")
            else:
                self.error_signal.emit(f"服务错误: {status_code}")
        except requests.RequestException as e:
            self.error_signal.emit(f"网络请求失败: {e}")
        except Exception as e:
            self.error_signal.emit(f"合成失败: {e}")

    def synthesize_variants(
        self,
        spk_audio_path: str,
        text: str,
        output_paths: List[str],
        emo_mode: int = 0,
        emo_vector: Optional[List[float]] = None,
        emo_weight: float = 1.0,
    ):
        """生成多个候选样本（串行调用远程服务）

        Args:
            spk_audio_path: 音色参考音频路径
            text: 要合成的文本
            output_paths: 输出路径列表
            emo_mode: 情感模式
            emo_vector: 情感向量
            emo_weight: 情感权重
        """
        if not self._model_loaded:
            self.error_signal.emit("远程服务未就绪")
            return

        if not text or not text.strip():
            self.error_signal.emit("文本不能为空")
            return

        if not os.path.exists(spk_audio_path):
            self.error_signal.emit(f"参考音频不存在: {spk_audio_path}")
            return

        if not output_paths:
            self.error_signal.emit("输出路径无效")
            return

        cleaned = [str(p) for p in output_paths if p]
        if not cleaned:
            self.error_signal.emit("输出路径无效")
            return

        out_ok: List[str] = []
        last_sr = 22050

        try:
            # 读取参考音频（只读一次）
            with open(spk_audio_path, "rb") as f:
                spk_audio_base64 = base64.b64encode(f.read()).decode("utf-8")

            total = len(cleaned)

            for idx, out_path in enumerate(cleaned):
                self.update_progress_signal.emit(
                    float(idx / total), f"正在生成样本 {idx + 1}/{total}..."
                )
                self.variant_progress_signal.emit(idx, 0.0, "发送请求...")

                payload = {
                    "text": text.strip(),
                    "speaker_audio_base64": spk_audio_base64,
                    "emo_mode": int(emo_mode),
                    "emo_vector": emo_vector if emo_vector else [0.0] * 8,
                    "emo_weight": float(emo_weight),
                    # 每次使用不同的随机参数以产生变化
                    "temperature": 0.7 + (idx * 0.05),
                }

                resp = self._session.post(
                    f"{self.base_url}/api/v1/synthesize",
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("success"):
                    audio_bytes = base64.b64decode(data["audio_base64"])
                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                    with open(out_path, "wb") as f:
                        f.write(audio_bytes)

                    last_sr = data.get("sample_rate", 22050)
                    out_ok.append(out_path)
                    self.variant_generated_signal.emit(idx, out_path, last_sr)
                    self.variant_progress_signal.emit(idx, 1.0, "完成")
                else:
                    raise RuntimeError(data.get("error", "合成失败"))

            self.update_progress_signal.emit(1.0, "全部生成完成")
            self.variants_done_signal.emit(out_ok, last_sr)

        except Exception as e:
            self.error_signal.emit(f"批量合成失败: {e}")

    def unload_model(self):
        """断开连接（释放资源）"""
        self._model_loaded = False
        self._device = "未连接"
        try:
            self._session.close()
        except Exception:
            pass

    def get_queue_status(self) -> dict:
        """获取队列状态

        Returns:
            {"queue_length": int, "estimated_wait_seconds": float}
        """
        try:
            resp = self._session.get(
                f"{self.base_url}/api/v1/queue",
                timeout=5,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return {"queue_length": -1, "estimated_wait_seconds": None}
