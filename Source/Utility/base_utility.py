from typing import Optional

from PySide6.QtCore import QObject, Signal

from Source.Job.base_job import BaseJob
from Source.Task.base_task import BaseTask


class BaseUtility(QObject):
    # 信号定义
    update_progress_text_signal: Signal = Signal(str)
    update_progress_total_count_signal: Signal = Signal(int)
    update_progress_current_count_signal: Signal = Signal(int)
    error_signal: Signal = Signal(str)
    show_result_info_bar_signal = Signal(str, str, str)
    finish_signal: Signal = Signal(str, str, str)

    def __init__(self, base_job: BaseJob):
        super().__init__()
        self._base_job: BaseJob = base_job
        self.error_signal.connect(self._base_job.show_error_info_bar)
        self.show_result_info_bar_signal.connect(self._base_job.show_result_info_bar)
        self.finish_signal.connect(self._base_job.job_finish)
        self.finish_signal.connect(self._base_job.worker_thread.quit)
        self.cancel_job: bool = False
        self.active_task_list: list[BaseTask] = []  # 存储正在运行的任务
        self.total_task_count = 0
        self.completed_task_count = 0

    def notice_cancel_job(self):
        """
        通知取消任务
        """
        self.cancel_all_task()
        self.finish_signal.emit("任务中止", "", "warning")

    def notice_error_and_cancel_job(self, data: Optional[dict]):
        self.cancel_all_task()
        if data:
            message: Optional[str] = data.get("message")
            if message:
                self.error_signal.emit(message)
        self.finish_signal.emit("任务中止", "", "error")

    def on_single_task_finished_internal(self, data: Optional[dict]):
        self.completed_task_count += 1
        self.on_single_task_finished(data)
        self.update_progress_current_count_signal.emit(self.completed_task_count)
        if self.completed_task_count == self.total_task_count:
            self.on_all_task_finished_internal()

    def on_single_task_finished(self, data: Optional[dict]):
        pass

    def on_all_task_finished_internal(self):
        self.cancel_all_task()
        self.on_all_task_finished()

    def on_all_task_finished(self):
        pass

    def start_all_task(self):
        for active_task in self.active_task_list:
            self._base_job.main_window.threadpool.start(active_task)

    def cancel_all_task(self):
        self.cancel_job = True
        for task in self.active_task_list:
            task.stop()
        self.active_task_list.clear()
        self._base_job.main_window.threadpool.clear()

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
