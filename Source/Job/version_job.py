from PySide6.QtCore import Signal

from Source.Job.base_job import BaseJob
from Source.Utility.version_utility import VersionUtility


class VersionJob(BaseJob):
    _check_app_latest_version_signal: Signal = Signal()

    # _update_app_signal: Signal = Signal()

    def __init__(self, main_window, title_bar):
        super().__init__(main_window)
        self._version_utility: VersionUtility | None = None
        #     import pysvn
        #     self._svn_client = pysvn.Client()
        from Source.title_bar import TitleBar
        self._title_bar: TitleBar = title_bar
        self.latest_version: str | None = None

    def check_app_latest_version_action(self):
        self._create_utility()
        self.start_worker()
        self.main_window.setDisabled(False)
        self._check_app_latest_version_signal.emit()

    # def update_app_action(self):
    #     if self._create_dialog("确认升级?", f"当前版本\"{APP_VERSION}\" -> 最新版本\"{self.latest_version}\""):
    #         self._create_utility()
    #         self.start_worker()
    #         self._create_progress_ring_window()
    #         self._update_app_signal.emit()

    # def update_finished(self):
    #     if self._create_dialog("更新完毕", "点击\"确认\"关闭应用, 请重新启动应用."):
    #         sys.exit()

    # def check_app_updateability(self) -> bool:
    #     try:
    #         entry = self._svn_client.info(".")
    #         self._print_log(f"应用所在SVN远程仓库路径: \"{entry.url}\".")
    #     except Exception as error:
    #         self._print_log_error(f"获取应用可升级性发生异常: {traceback.format_exc()}.")
    #         self.show_error_info_bar(f"获取应用可升级性发生异常: {error}.")
    #         return False
    #     return True

    def job_finish(self, title: str, content: str, result: str):
        if self._version_utility:
            self._version_utility.deleteLater()
            self._version_utility = None
        super().job_finish(title, content, result)

    def _create_utility(self):
        self._version_utility: VersionUtility = VersionUtility(self)
        self._version_utility.moveToThread(self.worker_thread)

        self._check_app_latest_version_signal.connect(self._version_utility.check_app_latest_version)
        # self._update_app_signal.connect(self._version_utility.update_app)

        self._version_utility.latest_version_get_signal.connect(self._title_bar.display_version_update_notice)
        # self._version_utility.update_finish_signal.connect(self.update_finished)

    # def _create_progress_ring_window(self):
    #     self._progress_ring_window: ProgressRingWindow = ProgressRingWindow(self.main_window)
    #     self._progress_ring_window.cancel_signal.connect(lambda: self._version_utility.notice_cancel_job())
    #
    #     self._version_utility.update_progress_text_signal.connect(self._progress_ring_window.set_text)
