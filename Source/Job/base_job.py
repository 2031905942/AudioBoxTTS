from PySide6.QtCore import QObject, QThread
from qfluentwidgets import Dialog

from Source.UI.Basic.error_info_bar import ErrorInfoBar
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.UI.Basic.progress_ring_window import ProgressRingWindow
from Source.UI.Basic.result_info_bar import ResultInfoBar


class BaseJob(QObject):
    def __init__(self, main_window):
        super().__init__()
        from Source.main_window import MainWindow
        self.main_window: MainWindow = main_window
        self.worker_thread: QThread = QThread(self)
        self._progress_ring_window: ProgressRingWindow | None = None
        self._progress_bar_window: ProgressBarWindow | None = None

    def unit(self):
        if self.worker_thread.isRunning():
            self.worker_thread.quit()

    def start_worker(self):
        self.worker_thread.start()
        # self.worker_thread.run()
        self.main_window.setDisabled(True)

    def show_error_info_bar(self, content: str):
        ErrorInfoBar(content, self.main_window)
        self.main_window.raise_()

    def job_finish(self, title: str, content: str, result: str):
        self.delete_progress_window()
        self.main_window.setDisabled(False)
        self.show_result_info_bar(result, title, content)
        self.main_window.raise_()

    def show_result_info_bar(self, info_bar_type: str, title: str, content: str):
        ResultInfoBar(info_bar_type, title, content, self.main_window)

    def delete_progress_window(self):
        if self._progress_ring_window:
            self._progress_ring_window.close()
            self._progress_ring_window.deleteLater()
            self._progress_ring_window = None

        if self._progress_bar_window:
            self._progress_bar_window.close()
            self._progress_bar_window.deleteLater()
            self._progress_bar_window = None

    def _create_dialog(self, title: str, content: str) -> int:
        dialog: Dialog = Dialog(title, content, self.main_window)
        return dialog.exec()

    def _print_log(self, log: str):
        """
        打印日志
        :param log: 日志
        """
        print(f"[{self.__class__.__name__}] {log}")

    def _print_log_error(self, log: str):
        """
        打印错误日志
        :param log: 日志
        """
        print(f"[{self.__class__.__name__}][Error] {log}")
