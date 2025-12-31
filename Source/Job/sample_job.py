import os.path

from lxml.etree import Element
from PySide6.QtCore import QFileInfo, QStandardPaths, Signal
from PySide6.QtWidgets import QFileDialog

from Source.Job.base_job import BaseJob
from Source.UI.Basic.check_list_window import CheckListWindow
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.Utility.config_utility import config_utility, ProjectData
from Source.Utility.sample_utility import SampleUtility
from Source.Utility.wproj_utility import WprojUtility


class SampleJob(BaseJob):
    _LAST_SELECTED_NORMALIZE_SAMPLE_DIR_PATH_CONFIG_NAME: str = "LastSelectedNormalizeSampleDirPath"
    _LAST_SELECTED_UPDATE_SAMPLE_DIR_PATH_CONFIG_NAME: str = "LastSelectedUpdateSampleDirPath"

    _normalize_sample_signal: Signal = Signal(str)
    _update_wwise_project_sample_signal: Signal = Signal(str, str)

    def __init__(self, main_window):
        super().__init__(main_window)
        self._sample_utility: SampleUtility | None = None
        self._check_list_window: CheckListWindow | None = None

    def uninit(self):
        if self._check_list_window:
            self._check_list_window.close()
            if self._check_list_window:
                self._check_list_window.deleteLater()
                self._check_list_window = None
        super().unit()

    def normalize_sample_action(self):
        dir_dialog: QFileDialog = QFileDialog(self.main_window)
        dir_dialog.setWindowTitle("请选择素材目录")
        dir_dialog.setFileMode(QFileDialog.FileMode.Directory)
        dir_dialog.setViewMode(QFileDialog.ViewMode.List)
        project_id: str | None = self.main_window.get_current_project_id()
        last_selected_normalize_sample_dir_path: str = config_utility.get_config(SampleJob._LAST_SELECTED_NORMALIZE_SAMPLE_DIR_PATH_CONFIG_NAME, project_id)
        if last_selected_normalize_sample_dir_path and os.path.isdir(last_selected_normalize_sample_dir_path):
            set_directory: str = last_selected_normalize_sample_dir_path
        else:
            set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        dir_dialog.setDirectory(set_directory)

        dir_path: str = ""
        dir_parent_path: str = ""
        if dir_dialog.exec():
            dir_path: str = dir_dialog.selectedFiles()[0]
            dir_info: QFileInfo = QFileInfo(dir_path)
            dir_parent_path = dir_info.dir().path()

        if not dir_path:
            return

        if self._create_dialog("确认执行素材标准化?", f"素材目录: \"{dir_path}\""):
            config_utility.set_config(SampleJob._LAST_SELECTED_NORMALIZE_SAMPLE_DIR_PATH_CONFIG_NAME, dir_parent_path, project_id)
            self._create_utility()
            self.start_worker()
            self._create_progress_bar_window()
            self._normalize_sample_signal.emit(dir_path)

    def update_wwise_project_sample_action(self):
        update_sample_dir_dialog: QFileDialog = QFileDialog(self.main_window)
        update_sample_dir_dialog.setWindowTitle("请选择源素材目录")
        update_sample_dir_dialog.setFileMode(QFileDialog.FileMode.Directory)
        update_sample_dir_dialog.setViewMode(QFileDialog.ViewMode.List)
        project_id: str | None = self.main_window.get_current_project_id()
        last_selected_update_sample_dir_path: str = config_utility.get_config(SampleJob._LAST_SELECTED_UPDATE_SAMPLE_DIR_PATH_CONFIG_NAME, project_id)
        if last_selected_update_sample_dir_path and os.path.isdir(last_selected_update_sample_dir_path):
            set_directory: str = last_selected_update_sample_dir_path
        else:
            set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        update_sample_dir_dialog.setDirectory(set_directory)

        update_sample_dir_path: str = ""
        update_sample_dir_parent_path: str = ""
        if update_sample_dir_dialog.exec():
            update_sample_dir_path: str = update_sample_dir_dialog.selectedFiles()[0]
            update_sample_dir_parent_path = os.path.dirname(update_sample_dir_path)

        if not update_sample_dir_path:
            return

        wwise_original_dir_dialog: QFileDialog = QFileDialog(self.main_window)
        wwise_original_dir_dialog.setWindowTitle("请选择Wwise素材目录")
        wwise_original_dir_dialog.setFileMode(QFileDialog.FileMode.Directory)
        wwise_original_dir_dialog.setViewMode(QFileDialog.ViewMode.List)

        if project_id:
            wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
            if wwise_project_path and os.path.isfile(wwise_project_path):
                wproj_utility: WprojUtility = WprojUtility(self)
                wproj_root_element: Element = wproj_utility.read_wwise_project_file(wwise_project_path)
                original_dir_path: str = WprojUtility.get_original_sample_path(wproj_root_element)
                if not original_dir_path:
                    original_dir_path = "Originals"
                wwise_project_dir_path: str = os.path.dirname(wwise_project_path)
                wwise_project_originals_dir_path: str = f"{wwise_project_dir_path}/{original_dir_path}"
                if os.path.isdir(wwise_project_originals_dir_path):
                    set_directory: str = wwise_project_originals_dir_path
                else:
                    set_directory: str = wwise_project_dir_path
            else:
                set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        else:
            set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        wwise_original_dir_dialog.setDirectory(set_directory)
        wwise_project_sample_dir_path: str = ""
        if wwise_original_dir_dialog.exec():
            wwise_project_sample_dir_path: str = wwise_original_dir_dialog.selectedFiles()[0]

        if not wwise_project_sample_dir_path:
            return

        if self._create_dialog("确认执行更新Wwise工程素材?", f"源素材目录: \"{update_sample_dir_path}\"\nWwise工程素材目录: \"{wwise_project_sample_dir_path}\""):
            config_utility.set_config(SampleJob._LAST_SELECTED_UPDATE_SAMPLE_DIR_PATH_CONFIG_NAME, update_sample_dir_parent_path, project_id)
            self._create_utility()
            self._sample_utility.show_check_list_window_signal.connect(self._show_check_list_window)
            self.start_worker()
            self._create_progress_bar_window()
            self._update_wwise_project_sample_signal.emit(update_sample_dir_path, wwise_project_sample_dir_path)

    def _create_utility(self):
        self._sample_utility: SampleUtility = SampleUtility(self)
        self._sample_utility.moveToThread(self.worker_thread)
        self._normalize_sample_signal.connect(self._sample_utility.normalize_sample)
        self._update_wwise_project_sample_signal.connect(self._sample_utility.update_wwise_project_sample_job)

    def _create_progress_bar_window(self):
        self._progress_bar_window: ProgressBarWindow = ProgressBarWindow(self.main_window)
        self._progress_bar_window.cancel_signal.connect(lambda: self._sample_utility.notice_cancel_job())

        self._sample_utility.update_progress_text_signal.connect(self._progress_bar_window.set_text)
        self._sample_utility.update_progress_total_count_signal.connect(self._progress_bar_window.set_total_count)
        self._sample_utility.update_progress_current_count_signal.connect(self._progress_bar_window.set_current_count)

    def _show_check_list_window(self, title: str, check_list: [(str, bool)]):
        if self._check_list_window:
            self._check_list_window.close()
            self._check_list_window.deleteLater()
            self._check_list_window = None
        self._check_list_window = CheckListWindow(title, check_list)
        self._check_list_window.window_closed_signal.connect(self._on_check_list_window_closed)

    def _on_check_list_window_closed(self):
        if not self._check_list_window:
            return
        self._check_list_window.deleteLater()
        self._check_list_window = None

    def job_finish(self, title: str, content: str, result: str):
        if self._sample_utility:
            self._sample_utility.deleteLater()
            self._sample_utility = None
        super().job_finish(title, content, result)
