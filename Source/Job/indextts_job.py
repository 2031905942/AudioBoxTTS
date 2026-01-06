"""
IndexTTS2 推理 Job

负责线程管理、进度窗口、错误提示与结果回传。
"""
import os
import warnings
from typing import Optional, List

from PySide6.QtCore import Signal

from Source.Job.base_job import BaseJob
from Source.UI.Basic.progress_ring_window import ProgressRingWindow
from Source.Utility.indextts_utility import IndexTTSUtility


class IndexTTSJob(BaseJob):
    """IndexTTS2 推理 Job：负责线程、进度窗、错误提示与结果回传。"""

    # 信号定义
    load_model_signal = Signal(str, bool, bool, bool)  # model_dir, fp16, cuda_kernel, deepspeed
    synthesize_signal = Signal(str, str, str, int, list, float)  # spk_audio, text, output, emo_mode, emo_vec, emo_weight
    synthesize_variants_signal = Signal(str, str, list, int, list, float)  # spk_audio, text, output_paths, emo_mode, emo_vec, emo_weight
    
    # UI 更新信号（用于通知界面更新进度和状态）
    progress_updated = Signal(float, str)  # progress (0.0-1.0), description
    job_completed = Signal(bool)  # success
    variant_generated = Signal(int, str)  # index, wav_path
    variant_progress = Signal(int, float, str)  # index, progress(0-1), desc

    def __init__(self, main_window):
        super().__init__(main_window)
        self._utility: Optional[IndexTTSUtility] = None
        self._last_wav_path: Optional[str] = None
        self._is_model_loaded: bool = False

    @property
    def last_wav_path(self) -> Optional[str]:
        """最后生成的 wav 路径"""
        return self._last_wav_path

    @property
    def is_model_loaded(self) -> bool:
        """模型是否已加载"""
        return self._is_model_loaded and self._utility is not None and self._utility.is_model_loaded

    @property
    def device(self) -> str:
        """当前设备"""
        if self._utility:
            return self._utility.device
        return "未加载"

    def load_model_action(self, model_dir: str, use_fp16: bool = False,
                          use_cuda_kernel: bool = False, use_deepspeed: bool = False):
        """加载模型（UI 调用入口）"""
        if self.worker_thread.isRunning():
            self.show_error_info_bar("任务进行中，请稍候")
            return

        self._create_utility()
        self._utility.moveToThread(self.worker_thread)

        # 模型加载：保持“禁用主窗口 + 弹出进度环”逻辑
        self.start_worker()
        self._create_progress_ring_window("模型加载")
        self._progress_ring_window.set_text("准备加载模型...")

        self.load_model_signal.emit(model_dir, use_fp16, use_cuda_kernel, use_deepspeed)

    def synthesize_action(self, spk_audio_path: str, text: str, output_path: str,
                          emo_mode: int = 0, emo_vector: Optional[List[float]] = None,
                          emo_weight: float = 1.0):
        """合成语音（UI 调用入口）

        Args:
            spk_audio_path: 音色参考音频路径
            text: 要合成的文本
            output_path: 输出 wav 路径
            emo_mode: 情感模式 (0=与音色相同, 2=向量控制)
            emo_vector: 情感向量 [喜,怒,哀,惧,厌恶,低落,惊喜,平静]
            emo_weight: 情感权重 0.0-1.0
        """
        if self.worker_thread.isRunning():
            self.show_error_info_bar("任务进行中，请稍候")
            return

        if not self.is_model_loaded:
            self.show_error_info_bar("请先加载模型")
            return

        # 复用已有的 utility（模型已加载）
        self._utility.moveToThread(self.worker_thread)

        # 语音合成：不禁用整个主窗口，不再弹出 ProgressRingWindow
        self.worker_thread.start()

        # 传递参数
        vec = emo_vector if emo_vector else [0.0] * 8
        self.synthesize_signal.emit(spk_audio_path, text, output_path, emo_mode, vec, emo_weight)

    def synthesize_variants_action(self, spk_audio_path: str, text: str, output_paths: List[str],
                                  emo_mode: int = 0, emo_vector: Optional[List[float]] = None,
                                  emo_weight: float = 1.0):
        """合成语音（一次生成多个候选样本）。

        Args:
            spk_audio_path: 音色参考音频路径
            text: 要合成的文本
            output_paths: 输出 wav 路径列表（建议长度为 3）
            emo_mode: 情感模式
            emo_vector: 情感向量
            emo_weight: 情感权重
        """
        if self.worker_thread.isRunning():
            self.show_error_info_bar("任务进行中，请稍候")
            return

        if not self.is_model_loaded:
            self.show_error_info_bar("请先加载模型")
            return

        if not output_paths or not isinstance(output_paths, list):
            self.show_error_info_bar("输出路径无效")
            return

        # 复用已有的 utility（模型已加载）
        self._utility.moveToThread(self.worker_thread)

        # 语音合成：不禁用整个主窗口，不再弹出 ProgressRingWindow
        self.worker_thread.start()

        vec = emo_vector if emo_vector else [0.0] * 8
        self.synthesize_variants_signal.emit(spk_audio_path, text, output_paths, emo_mode, vec, emo_weight)

    def _create_utility(self):
        """创建 Utility 实例并连接信号"""
        # 如果已有实例且模型已加载，保留它
        if self._utility and self._is_model_loaded:
            # 只需要重新连接信号
            pass
        else:
            self._utility = IndexTTSUtility()
            self._is_model_loaded = False

        def _safe_disconnect(sig):
            """Qt 信号断开连接：若未连接则不输出 RuntimeWarning。"""
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        category=RuntimeWarning,
                        message=r"Failed to disconnect.*",
                    )
                    sig.disconnect()
            except Exception:
                # 包含: TypeError/RuntimeError 等
                pass

        # 断开旧连接，避免重复触发或引用旧 utility
        _safe_disconnect(self.load_model_signal)
        _safe_disconnect(self.synthesize_signal)
        _safe_disconnect(self.synthesize_variants_signal)

        self.load_model_signal.connect(self._utility.load_model)
        self.synthesize_signal.connect(self._utility.synthesize)
        self.synthesize_variants_signal.connect(self._utility.synthesize_variants)

        _safe_disconnect(self._utility.update_progress_signal)
        _safe_disconnect(self._utility.error_signal)
        _safe_disconnect(self._utility.generated_signal)
        _safe_disconnect(getattr(self._utility, "variant_generated_signal", self._utility.generated_signal))
        _safe_disconnect(getattr(self._utility, "variant_progress_signal", self._utility.generated_signal))
        _safe_disconnect(getattr(self._utility, "variants_done_signal", self._utility.generated_signal))
        _safe_disconnect(self._utility.model_loaded_signal)

        self._utility.update_progress_signal.connect(self._on_progress_update)
        self._utility.error_signal.connect(self._on_error)
        self._utility.generated_signal.connect(self._on_generated)
        self._utility.variant_generated_signal.connect(self._on_variant_generated)
        self._utility.variant_progress_signal.connect(self._on_variant_progress)
        self._utility.variants_done_signal.connect(self._on_variants_done)
        self._utility.model_loaded_signal.connect(self._on_model_loaded)

    def _on_variant_generated(self, index: int, wav_path: str, sample_rate: int):
        """某个候选样本生成完成回调（3 样本流程）。"""
        self._last_wav_path = wav_path
        self.variant_generated.emit(int(index), str(wav_path))

    def _on_variant_progress(self, index: int, progress: float, desc: str):
        """某个候选样本的实时进度回调。"""
        self.variant_progress.emit(int(index), float(progress), str(desc or ""))

    def _on_variants_done(self, wav_paths: List[str], sample_rate: int):
        """所有候选样本生成完成回调。"""
        try:
            if wav_paths:
                self._last_wav_path = wav_paths[-1]
        except Exception:
            pass
        self.worker_thread.quit()
        tail = ""
        try:
            tail = os.path.basename(self._last_wav_path) if self._last_wav_path else ""
        except Exception:
            tail = ""
        msg = f"已生成 3 个样本{('，最后: ' + tail) if tail else ''} ({int(sample_rate)}Hz)"
        self.job_finish("IndexTTS", msg, "success")
        self.job_completed.emit(True)

    def _create_progress_ring_window(self, title: str = "处理中"):
        """创建进度环窗口"""
        self._progress_ring_window = ProgressRingWindow(self.main_window)
        self._progress_ring_window.set_enable_cancel(False)
        self._progress_ring_window.set_text(f"{title}...")

    def _on_progress_update(self, progress: float, text: str):
        """进度更新回调"""
        if self._progress_ring_window:
            display_text = text if text else f"处理中 {int(progress * 100)}%"
            self._progress_ring_window.set_text(display_text)
        # 同时发射信号通知 UI 界面更新
        self.progress_updated.emit(progress, text)

    def _on_error(self, message: str):
        """错误回调"""
        self.worker_thread.quit()
        self.job_finish("IndexTTS", message, "error")
        self.job_completed.emit(False)

    def _on_model_loaded(self):
        """模型加载完成回调"""
        self._is_model_loaded = True
        self.worker_thread.quit()
        self.job_finish("IndexTTS", f"模型加载成功\n设备: {self._utility.device}", "success")
        self.job_completed.emit(True)

    def _on_generated(self, wav_path: str, sample_rate: int):
        """生成完成回调"""
        self._last_wav_path = wav_path
        self.worker_thread.quit()
        self.job_finish("IndexTTS", f"已生成: {os.path.basename(wav_path)} ({sample_rate}Hz)", "success")
        self.job_completed.emit(True)

    def unload_model(self):
        """卸载模型"""
        if self._utility:
            self._utility.unload_model()
            self._is_model_loaded = False

    def uninit(self):
        """资源释放"""
        self.unload_model()
        if self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(3000)
