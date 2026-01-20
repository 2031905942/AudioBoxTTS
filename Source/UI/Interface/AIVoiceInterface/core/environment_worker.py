"""
环境检测后台任务模块

包含环境检测的信号类和后台工作线程。
"""
from PySide6.QtCore import QObject, Signal, QRunnable


class EnvCheckSignals(QObject):
    """环境检测信号类"""
    finished = Signal(bool, str)  # is_ready, message


class EnvCheckWorker(QRunnable):
    """环境检测后台任务"""

    def __init__(self):
        super().__init__()
        self.signals = EnvCheckSignals()

    def run(self):
        """在后台线程执行环境检测"""
        try:
            from Source.Job.indextts_env_job import IndexTTSEnvJob
            is_ready, msg = IndexTTSEnvJob.check_env_ready()
            self.signals.finished.emit(is_ready, msg)
        except Exception as e:
            self.signals.finished.emit(False, f"检测失败: {str(e)}")
