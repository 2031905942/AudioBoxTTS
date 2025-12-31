from PySide6.QtCore import QMutex, QMutexLocker, QObject, QRunnable, Signal


class BaseTask(QRunnable):
    class Signals(QObject):
        progress = Signal(int)  # 进度百分比(0-100)
        finished = Signal(dict)  # 完成信号
        error = Signal(dict)  # 错误信息
        interrupted = Signal(dict)  # 中断信号

    def __init__(self, utility):
        super().__init__()
        self.signals = self.Signals()
        self._is_running = True  # 中断控制标志
        self._lock = QMutex()  # 线程锁保证标志位安全
        from Source.Utility.base_utility import BaseUtility
        self.utility: BaseUtility = utility
        self.signals.finished.connect(utility.on_single_task_finished_internal)
        self.signals.error.connect(utility.notice_error_and_cancel_job)
        self.setAutoDelete(True)  # 任务完成后自动删除()

    def stop(self):
        with QMutexLocker(self._lock):
            self._is_running = False  # 安全修改标志位
