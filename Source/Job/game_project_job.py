from PySide6.QtCore import Signal

from Source.Job.base_job import BaseJob
from Source.UI.Basic.game_project_initialize_window import GameProjectInitializeWindow
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.Utility.game_project_utility import GameProjectUtility


class GameProjectJob(BaseJob):
    _initialize_game_project_signal = Signal(dict)

    def __init__(self, main_window):
        super().__init__(main_window)
        self.game_project_utility: GameProjectUtility | None = None
        self._game_project_initialize_window: GameProjectInitializeWindow | None = None

    def uninit(self):
        if self._game_project_initialize_window:
            self._game_project_initialize_window.close()
            if self._game_project_initialize_window:
                self._game_project_initialize_window.deleteLater()
                self._game_project_initialize_window = None
        super().unit()

    def initialize_game_project_action(self):
        self.game_project_utility = GameProjectUtility(self)
        if not self.game_project_utility.check_svn_validity():
            self.show_error_info_bar("未安装SVN, 请先安装Subversion(可通过Brew安装)")
            self.job_finish("任务中止", "", "error")
            return
        self._show_game_project_initialize_window()

    def _initialize_game_project_implement_action(self, game_project_info_dict: dict):
        self.game_project_utility.add_project_info_signal.connect(self.main_window.project_interface.add_project_info)
        self.game_project_utility.moveToThread(self.worker_thread)
        self._initialize_game_project_signal.connect(self.game_project_utility.initialize_game_project_job)
        self.start_worker()
        self._create_progress_bar_window()
        self._initialize_game_project_signal.emit(game_project_info_dict)

    # def _create_utility(self):
    #     self.game_project_utility: GameProjectUtility = GameProjectUtility(self)
    #     self.game_project_utility.moveToThread(self.worker_thread)
    #     self._initialize_game_project_signal.connect(self.game_project_utility.initialize_game_project_job)
    #     self._prepare_work_environment_signal.connect(self.game_project_utility.prepare_work_environment_job)

    def _create_progress_bar_window(self):
        self._progress_bar_window: ProgressBarWindow = ProgressBarWindow(self.main_window)
        self._progress_bar_window.cancel_signal.connect(lambda: self.game_project_utility.notice_cancel_job())

        self.game_project_utility.update_progress_text_signal.connect(self._progress_bar_window.set_text)
        self.game_project_utility.update_progress_total_count_signal.connect(self._progress_bar_window.set_total_count)
        self.game_project_utility.update_progress_current_count_signal.connect(self._progress_bar_window.set_current_count)

    def _show_game_project_initialize_window(self):
        if self._game_project_initialize_window:
            self._game_project_initialize_window.close()
            if self._game_project_initialize_window:
                self._game_project_initialize_window.deleteLater()
                self._game_project_initialize_window = None
        self._game_project_initialize_window = GameProjectInitializeWindow(self)
        self._game_project_initialize_window.confirm_signal.connect(self._initialize_game_project_implement_action)
        self._game_project_initialize_window.window_closed_signal.connect(self._on_game_project_initialize_window_closed)

    def _on_game_project_initialize_window_closed(self):
        if not self._game_project_initialize_window:
            return
        self._game_project_initialize_window.deleteLater()
        self._game_project_initialize_window = None

    def job_finish(self, title: str, content: str, result: str):
        if self.game_project_utility:
            self.game_project_utility.deleteLater()
            self.game_project_utility = None
        super().job_finish(title, content, result)
