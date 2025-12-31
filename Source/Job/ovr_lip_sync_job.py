import os
from typing import Optional

from PySide6.QtCore import QStandardPaths, Signal
from PySide6.QtWidgets import QFileDialog

from Source.Job.base_job import BaseJob
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.Utility.config_utility import config_utility, ProjectData
from Source.Utility.ovr_lip_sync_utility import OVRLipSyncUtility
from Source.Utility.wproj_utility import WprojUtility


class OVRLipSyncJob(BaseJob):
    _LAST_SELECTED_VOICE_SAMPLE_VISEME_EXPORT_DIR_PATH_CONFIG_NAME = "LastSelectedVoiceSampleVisemeExportDirPath"

    _export_voice_sample_viseme_signal = Signal(str, str)

    def __init__(self, main_window):
        super().__init__(main_window)
        self._ovr_lip_sync_utility: OVRLipSyncUtility | None = OVRLipSyncUtility(self)

    def export_voice_sample_viseme_action(self):
        dir_dialog = QFileDialog(self.main_window)
        dir_dialog.setWindowTitle("请选择语音素材目录")
        dir_dialog.setFileMode(QFileDialog.FileMode.Directory)
        dir_dialog.setViewMode(QFileDialog.ViewMode.List)
        project_id: Optional[str] = self.main_window.get_current_project_id()
        if project_id:
            wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
            if wwise_project_path and os.path.isfile(wwise_project_path):
                wproj_utility: WprojUtility = WprojUtility(self)
                wproj_root_element = wproj_utility.read_wwise_project_file(wwise_project_path)
                original_dir_path = WprojUtility.get_original_sample_path(wproj_root_element)
                if not original_dir_path:
                    original_dir_path = "Originals"
                wwise_project_dir_path: str = os.path.dirname(wwise_project_path)
                wwise_project_voices_dir_path = f"{wwise_project_dir_path}/{original_dir_path}/Voices"
                if os.path.isdir(wwise_project_voices_dir_path):
                    set_directory: str = wwise_project_voices_dir_path
                else:
                    set_directory: str = wwise_project_dir_path
            else:
                set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        else:
            set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        dir_dialog.setDirectory(set_directory)

        voice_sample_dir_path = ""
        if dir_dialog.exec():
            voice_sample_dir_path: str = dir_dialog.selectedFiles()[0]

        if not voice_sample_dir_path:
            return

        dir_dialog.setWindowTitle("请选择视素导出目录")
        last_selected_voice_sample_viseme_export_dir_path: Optional[str] = config_utility.get_config(OVRLipSyncJob._LAST_SELECTED_VOICE_SAMPLE_VISEME_EXPORT_DIR_PATH_CONFIG_NAME, project_id)
        if last_selected_voice_sample_viseme_export_dir_path and os.path.isdir(last_selected_voice_sample_viseme_export_dir_path):
            set_directory: str = last_selected_voice_sample_viseme_export_dir_path
        else:
            set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        dir_dialog.setDirectory(set_directory)

        viseme_export_dir_path = ""
        if dir_dialog.exec():
            viseme_export_dir_path: str = dir_dialog.selectedFiles()[0]

        if not viseme_export_dir_path:
            return

        if self._create_dialog("确认执行导出语音素材视素?", f"语音素材目录: \"{voice_sample_dir_path}\"\n视素导出目录: \"{viseme_export_dir_path}\""):
            config_utility.set_config(OVRLipSyncJob._LAST_SELECTED_VOICE_SAMPLE_VISEME_EXPORT_DIR_PATH_CONFIG_NAME, viseme_export_dir_path, project_id)
            self._create_utility()
            self.start_worker()
            self._create_progress_bar_window()
            self._export_voice_sample_viseme_signal.emit(voice_sample_dir_path, viseme_export_dir_path)

    def _create_utility(self):
        self._ovr_lip_sync_utility = OVRLipSyncUtility(self)
        self._ovr_lip_sync_utility.moveToThread(self.worker_thread)
        self._export_voice_sample_viseme_signal.connect(self._ovr_lip_sync_utility.export_voice_sample_viseme)

    def _create_progress_bar_window(self):
        self._progress_bar_window = ProgressBarWindow(self.main_window)
        self._progress_bar_window.cancel_signal.connect(lambda: self._ovr_lip_sync_utility.notice_cancel_job())

        self._ovr_lip_sync_utility.update_progress_text_signal.connect(self._progress_bar_window.set_text)
        self._ovr_lip_sync_utility.update_progress_total_count_signal.connect(self._progress_bar_window.set_total_count)
        self._ovr_lip_sync_utility.update_progress_current_count_signal.connect(self._progress_bar_window.set_current_count)

    def job_finish(self, title: str, content: str, result: str):
        if self._ovr_lip_sync_utility:
            self._ovr_lip_sync_utility.deleteLater()
            self._ovr_lip_sync_utility = None
        super().job_finish(title, content, result)
