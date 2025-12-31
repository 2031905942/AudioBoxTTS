"""
IndexTTS2 推理工具类

封装 IndexTTS2 的核心推理功能，运行在工作线程中。
支持两种情感控制模式：
1. 与音色参考音频相同（emo_mode=0）
2. 使用情感向量控制（emo_mode=2）
"""
import os
import sys
from typing import Optional, List, Callable

from PySide6.QtCore import QObject, Signal, Slot, QMutex, QMutexLocker

# IndexTTS2 路径配置
# 优先使用 AudioBox/Source/indextts（独立模式）
# 如果不存在，则回退到外部的 index-tts 目录（开发模式）
_SOURCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LOCAL_INDEXTTS = os.path.join(_SOURCE_DIR, "indextts")
_EXTERNAL_INDEXTTS = os.path.abspath(os.path.join(_SOURCE_DIR, "..", "..", "index-tts"))

if os.path.exists(_LOCAL_INDEXTTS):
    # 独立模式：使用 AudioBox/Source/indextts
    INDEXTTS_ROOT = _SOURCE_DIR
    INDEXTTS_MODE = "standalone"
else:
    # 开发模式：使用外部 index-tts 目录
    INDEXTTS_ROOT = _EXTERNAL_INDEXTTS
    INDEXTTS_MODE = "external"

if INDEXTTS_ROOT not in sys.path:
    sys.path.insert(0, INDEXTTS_ROOT)


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
        self._tts: Optional["IndexTTS2"] = None
        self._mutex = QMutex()
        self._model_dir: str = ""
        self._is_loading: bool = False

    @property
    def is_model_loaded(self) -> bool:
        """模型是否已加载"""
        return self._tts is not None

    @property
    def model_dir(self) -> str:
        """当前模型目录"""
        return self._model_dir

    @property
    def device(self) -> str:
        """当前设备"""
        if self._tts:
            return str(self._tts.device)
        return "未加载"

    @staticmethod
    def get_default_model_dir() -> str:
        """获取默认模型目录
        
        优先使用 AudioBox/checkpoints，若不存在则尝试 index-tts/checkpoints
        """
        # AudioBox 根目录
        audiobox_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        audiobox_ckpt = os.path.join(audiobox_root, "checkpoints")
        
        # 优先使用 AudioBox 目录下的 checkpoints
        if os.path.exists(audiobox_ckpt):
            return audiobox_ckpt
        
        # 回退到 index-tts 目录
        return os.path.join(INDEXTTS_ROOT, "checkpoints")

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
            if not os.path.exists(os.path.join(model_dir, f)):
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
            self.update_progress_signal.emit(0.1, "检查模型文件...")

            # 检查模型文件
            is_complete, missing = self.check_model_files(model_dir)
            if not is_complete:
                self.error_signal.emit(f"模型文件不完整，缺少: {', '.join(missing)}")
                return

            self.update_progress_signal.emit(0.2, "导入 IndexTTS2...")

            # 导入 IndexTTS2
            try:
                from indextts.infer_v2 import IndexTTS2
            except ImportError as e:
                self.error_signal.emit(f"无法导入 IndexTTS2: {e}")
                return

            self.update_progress_signal.emit(0.3, "加载模型（可能需要 30-60 秒）...")

            # 加载模型
            cfg_path = os.path.join(model_dir, "config.yaml")
            self._tts = IndexTTS2(
                cfg_path=cfg_path,
                model_dir=model_dir,
                use_fp16=use_fp16,
                use_cuda_kernel=use_cuda_kernel,
                use_deepspeed=use_deepspeed,
            )
            self._model_dir = model_dir

            self.update_progress_signal.emit(1.0, "模型加载完成")
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
        if not self._tts:
            self.error_signal.emit("模型未加载")
            return

        if not text or not text.strip():
            self.error_signal.emit("文本不能为空")
            return

        if not os.path.exists(spk_audio_path):
            self.error_signal.emit(f"参考音频不存在: {spk_audio_path}")
            return

        try:
            self.update_progress_signal.emit(0.1, "准备推理...")

            # 设置 gradio 风格的进度回调
            class ProgressTracker:
                def __init__(self, signal):
                    self._signal = signal

                def __call__(self, value, desc=""):
                    # 映射到 0.1-0.9 区间
                    mapped = 0.1 + value * 0.8
                    self._signal.emit(mapped, desc)

            self._tts.gr_progress = ProgressTracker(self.update_progress_signal)

            # 准备推理参数
            kwargs = {
                "spk_audio_prompt": spk_audio_path,
                "text": text.strip(),
                "output_path": output_path,
                "verbose": False,
            }

            if emo_mode == self.EMO_MODE_SAME_AS_SPEAKER:
                # 模式1：与音色参考音频相同
                # 不传 emo_audio_prompt 和 emo_vector，默认使用 spk_audio_prompt 的情感
                pass

            elif emo_mode == self.EMO_MODE_VECTOR:
                # 模式2：情感向量控制
                if emo_vector and len(emo_vector) == 8:
                    # 归一化情感向量
                    normalized_vec = self._tts.normalize_emo_vec(emo_vector, apply_bias=True)
                    kwargs["emo_vector"] = normalized_vec
                    # 通过 emo_alpha 控制情感强度（在向量模式下会预先缩放向量）
                    kwargs["emo_alpha"] = emo_weight

            # 执行推理
            result = self._tts.infer(**kwargs)

            if result and os.path.exists(output_path):
                self.update_progress_signal.emit(1.0, "生成完成")
                # 采样率固定为 22050（IndexTTS2 输出）
                self.generated_signal.emit(output_path, 22050)
            else:
                self.error_signal.emit("推理完成但未生成文件")

        except Exception as e:
            import traceback
            self.error_signal.emit(f"推理失败: {e}\n{traceback.format_exc()}")
        finally:
            if self._tts:
                self._tts.gr_progress = None

    def unload_model(self):
        """卸载模型，释放显存"""
        with QMutexLocker(self._mutex):
            if self._tts:
                del self._tts
                self._tts = None
                self._model_dir = ""

                # 尝试释放 CUDA 缓存
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
