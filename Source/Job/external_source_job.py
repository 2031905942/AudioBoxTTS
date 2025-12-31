from typing import Optional

from PySide6.QtCore import Signal

from Source.Job.base_job import BaseJob
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.Utility.external_source_utility import ExternalSourceUtility


class ExternalSourceJob(BaseJob):
    convert_project_external_source_signal = Signal(str)

    def __init__(self, main_window):
        super().__init__(main_window)
        self._external_source_utility: Optional[ExternalSourceUtility] = None

    def convert_project_external_source_action(self, project_id: str):
        self._create_external_source_utility()
        self._external_source_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._create_progress_bar_window()
        self.convert_project_external_source_signal.emit(project_id)

    def _create_external_source_utility(self):
        self._external_source_utility = ExternalSourceUtility(self)
        self.convert_project_external_source_signal.connect(self._external_source_utility.convert_project_external_source_job)

    def _create_progress_bar_window(self):
        self._progress_bar_window: ProgressBarWindow = ProgressBarWindow(self.main_window)
        if self._external_source_utility:
            self._progress_bar_window.cancel_signal.connect(lambda: self._external_source_utility.notice_cancel_job())
            self._external_source_utility.update_progress_text_signal.connect(self._progress_bar_window.set_text)
            self._external_source_utility.update_progress_total_count_signal.connect(self._progress_bar_window.set_total_count)
            self._external_source_utility.update_progress_current_count_signal.connect(self._progress_bar_window.set_current_count)

    def job_finish(self, title: str, content: str, result: str):
        if self._external_source_utility:
            self._external_source_utility.deleteLater()
            self._external_source_utility = None

        super().job_finish(title, content, result)
