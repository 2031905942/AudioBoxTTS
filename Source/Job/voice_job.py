import os.path
from pathlib import Path

from PySide6.QtCore import QDir, QFileInfo, QStandardPaths, Signal
from PySide6.QtWidgets import QFileDialog

from Source.Job.base_job import BaseJob
from Source.UI.Basic.check_list_window import CheckListWindow
from Source.UI.Basic.progress_ring_window import ProgressRingWindow
from Source.Utility.config_utility import config_utility
from Source.Utility.voice_excel_utility import VoiceExcelUtility


class VoiceJob(BaseJob):
    _LAST_SELECTED_EXPORT_EXCEL_FILE_PARENT_PATH_CONFIG_NAME = "LastSelectedExportExcelFileParentPath"
    _LAST_SELECTED_EXPORT_EXCEL_FILE_NAME_CONFIG_NAME = "LastSelectedExportExcelFileName"
    LAST_SELECTED_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME = "LastSelectedVoiceExcelFileParentPath"
    LAST_SELECTED_VOICE_EXCEL_FILE_NAME_CONFIG_NAME = "LastSelectedVoiceExcelFileName"
    _LAST_SELECTED_FORMAT_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME = "LastSelectedFormatVoiceExcelFileParentPath"
    _LAST_SELECTED_FORMAT_VOICE_EXCEL_FILE_NAME_CONFIG_NAME = "LastSelectedFormatVoiceExcelFileName"
    _LAST_SELECTED_RENAME_VOICE_SAMPLE_PARENT_PATH_CONFIG_NAME = "LastSelectedRenameVoiceSampleParentPath"

    _sync_export_excel_and_voice_excel_signal = Signal(str, str)
    _sync_localized_voice_excel_signal = Signal(str, str)
    _generate_voice_id_for_voice_excel_signal = Signal(str)
    _generate_voice_event_for_voice_excel_signal = Signal(str)
    _format_voice_excel_signal = Signal(str)
    _rename_voice_sample_by_voice_excel_signal = Signal(str, str)

    def __init__(self, main_window):
        super().__init__(main_window)
        self._voice_excel_utility: VoiceExcelUtility | None = None
        self._dialogue_check_list_window: CheckListWindow | None = None

    def uninit(self):
        if self._dialogue_check_list_window:
            self._dialogue_check_list_window.close()
            if self._dialogue_check_list_window:
                self._dialogue_check_list_window.deleteLater()
                self._dialogue_check_list_window = None
        super().unit()

    def sync_export_excel_and_voice_excel_action(self):
        export_excel_file_dialog: QFileDialog = QFileDialog(self.main_window)
        export_excel_file_dialog.setWindowTitle("请选择文案平台工作簿")
        project_id: str | None = self.main_window.get_current_project_id()
        last_selected_export_excel_file_parent_path = config_utility.get_config(VoiceJob._LAST_SELECTED_EXPORT_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, project_id)

        if last_selected_export_excel_file_parent_path and os.path.isdir(last_selected_export_excel_file_parent_path):
            set_directory: str = last_selected_export_excel_file_parent_path
        else:
            set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]

        export_excel_file_dialog.setDirectory(set_directory)
        last_selected_export_excel_file_name: str = config_utility.get_config(VoiceJob._LAST_SELECTED_EXPORT_EXCEL_FILE_NAME_CONFIG_NAME, project_id)
        if last_selected_export_excel_file_name:
            last_selected_export_excel_file_path = f"{set_directory}/{last_selected_export_excel_file_name}"
            if os.path.isfile(last_selected_export_excel_file_path):
                export_excel_file_dialog.selectFile(last_selected_export_excel_file_name)
        export_excel_file_dialog.setNameFilter("Excel文件 (*.xlsx)")
        export_excel_file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        export_excel_file_dialog.setViewMode(QFileDialog.ViewMode.List)
        export_excel_file_path: str = ""
        export_excel_file_directory_path: str = ""
        if export_excel_file_dialog.exec():
            export_excel_file_path = export_excel_file_dialog.selectedFiles()[0]
            export_excel_file_directory: QDir = export_excel_file_dialog.directory()
            export_excel_file_directory_path = export_excel_file_directory.path()
            print(f"文案平台工作簿所在目录路径: {export_excel_file_directory_path}.")

        if not export_excel_file_path:
            return
        print(f"文案平台工作簿: {export_excel_file_path}.")

        voice_excel_file_dialog: QFileDialog = QFileDialog(self.main_window)
        voice_excel_file_dialog.setWindowTitle("请选择录音工作簿")
        last_selected_voice_excel_file_parent_path: str = config_utility.get_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, project_id)
        if last_selected_voice_excel_file_parent_path and os.path.isdir(last_selected_voice_excel_file_parent_path):
            set_directory: str = last_selected_voice_excel_file_parent_path
        else:
            set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]

        voice_excel_file_dialog.setDirectory(set_directory)
        last_selected_voice_excel_file_name: str = config_utility.get_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, project_id)
        if last_selected_voice_excel_file_name:
            last_selected_voice_excel_file_path = f"{set_directory}/{last_selected_voice_excel_file_name}"
            if os.path.isfile(last_selected_voice_excel_file_path):
                voice_excel_file_dialog.selectFile(last_selected_voice_excel_file_name)

        voice_excel_file_dialog.setNameFilter("Excel文件 (*.xlsx)")
        voice_excel_file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        voice_excel_file_dialog.setViewMode(QFileDialog.ViewMode.List)
        voice_excel_file_path: str = ""
        voice_excel_file_directory_path: str = ""
        if voice_excel_file_dialog.exec():
            voice_excel_file_path = voice_excel_file_dialog.selectedFiles()[0]
            voice_excel_file_directory: QDir = voice_excel_file_dialog.directory()
            voice_excel_file_directory_path = voice_excel_file_directory.path()
            print(f"录音工作簿所在目录路径: {voice_excel_file_directory_path}.")
        if not voice_excel_file_path:
            return
        print(f"录音工作簿: {voice_excel_file_path}.")

        if self._create_dialog("确认执行同步?", f"文案平台工作簿: \"{export_excel_file_path}\"\n录音工作簿: \"{voice_excel_file_path}\""):
            config_utility.set_config(VoiceJob._LAST_SELECTED_EXPORT_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, export_excel_file_directory_path, project_id)
            export_excel_file_name: str = Path(export_excel_file_path).name
            config_utility.set_config(VoiceJob._LAST_SELECTED_EXPORT_EXCEL_FILE_NAME_CONFIG_NAME, export_excel_file_name, project_id)
            config_utility.set_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, voice_excel_file_directory_path, project_id)
            voice_excel_file_name: str = Path(voice_excel_file_path).name
            config_utility.set_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, voice_excel_file_name, project_id)
            self._create_utility()
            self.start_worker()
            self._create_progress_ring_window()
            self._sync_export_excel_and_voice_excel_signal.emit(export_excel_file_path, voice_excel_file_path)

    def sync_localized_voice_excel_action(self):
        first_language_excel_file_dialog: QFileDialog = QFileDialog(self.main_window)
        first_language_excel_file_dialog.setWindowTitle("请选择第一语言录音工作簿")
        project_id: str | None = self.main_window.get_current_project_id()
        last_selected_first_language_excel_file_parent_path: str = config_utility.get_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, project_id)

        if last_selected_first_language_excel_file_parent_path and os.path.isdir(last_selected_first_language_excel_file_parent_path):
            set_directory: str = last_selected_first_language_excel_file_parent_path
        else:
            set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]

        first_language_excel_file_dialog.setDirectory(set_directory)
        last_selected_first_language_excel_file_name: str = config_utility.get_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, project_id)
        if last_selected_first_language_excel_file_name:
            last_selected_first_language_excel_file_path = f"{set_directory}/{last_selected_first_language_excel_file_name}"
            if os.path.isfile(last_selected_first_language_excel_file_path):
                first_language_excel_file_dialog.selectFile(last_selected_first_language_excel_file_name)
        first_language_excel_file_dialog.setNameFilter("Excel文件 (*.xlsx)")
        first_language_excel_file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        first_language_excel_file_dialog.setViewMode(QFileDialog.ViewMode.List)
        first_language_excel_file_path: str = ""
        first_language_excel_file_directory_path: str = ""
        if first_language_excel_file_dialog.exec():
            first_language_excel_file_path = first_language_excel_file_dialog.selectedFiles()[0]
            export_excel_file_directory: QDir = first_language_excel_file_dialog.directory()
            first_language_excel_file_directory_path = export_excel_file_directory.path()
            print(f"第一语言录音工作簿所在目录路径: {first_language_excel_file_directory_path}.")

        if not first_language_excel_file_path:
            return
        print(f"第一语言录音工作簿: {first_language_excel_file_path}.")

        second_language_excel_file_dialog: QFileDialog = QFileDialog(self.main_window)
        second_language_excel_file_dialog.setWindowTitle("请选择第二语言录音工作簿")
        second_language_excel_file_dialog.setDirectory(set_directory)
        second_language_excel_file_dialog.setNameFilter("Excel文件 (*.xlsx)")
        second_language_excel_file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        second_language_excel_file_dialog.setViewMode(QFileDialog.ViewMode.List)
        second_language_excel_file_path: str = ""
        if second_language_excel_file_dialog.exec():
            second_language_excel_file_path = second_language_excel_file_dialog.selectedFiles()[0]
            second_language_excel_file_directory: QDir = second_language_excel_file_dialog.directory()
            second_language_excel_file_directory_path = second_language_excel_file_directory.path()
            print(f"第二语言录音工作簿所在目录路径: {second_language_excel_file_directory_path}.")
        if not second_language_excel_file_path:
            return
        print(f"第二语言录音工作簿: {second_language_excel_file_path}.")

        if self._create_dialog("确认执行同步?", f"第一语言录音工作簿: \"{first_language_excel_file_path}\"\n第二语言录音工作簿: \"{second_language_excel_file_path}\""):
            config_utility.set_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, first_language_excel_file_directory_path, project_id)
            voice_excel_file_name: str = Path(first_language_excel_file_path).name
            config_utility.set_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, voice_excel_file_name, project_id)
            self._create_utility()
            self.start_worker()
            self._create_progress_ring_window()
            self._sync_localized_voice_excel_signal.emit(first_language_excel_file_path, second_language_excel_file_path)

    def generate_voice_id_for_voice_excel_action(self):
        file_dialog: QFileDialog = QFileDialog(self.main_window)
        file_dialog.setWindowTitle("请选择录音工作簿")
        project_id: str | None = self.main_window.get_current_project_id()
        last_selected_file_parent_path: str = config_utility.get_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, project_id)

        if last_selected_file_parent_path and os.path.isdir(last_selected_file_parent_path):
            set_directory: str = last_selected_file_parent_path
        else:
            set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]

        file_dialog.setDirectory(set_directory)
        last_selected_file_name: str = config_utility.get_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, project_id)
        if last_selected_file_name:
            last_selected_file_path = f"{set_directory}/{last_selected_file_name}"
            if os.path.isfile(last_selected_file_path):
                file_dialog.selectFile(last_selected_file_name)

        file_dialog.setNameFilter("Excel文件 (*.xlsx)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setViewMode(QFileDialog.ViewMode.List)
        file_path: str = ""
        file_parent_path: str = ""
        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]
            file_directory: QDir = file_dialog.directory()
            file_parent_path = file_directory.path()
            print(f"录音工作簿所在目录路径: {file_parent_path}.")

        if not file_path:
            return
        print(f"录音工作簿: {file_path}.")

        if self._create_dialog("确认执行生成语音ID?", f"录音工作簿: \"{file_path}\""):
            config_utility.set_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, file_parent_path, project_id)
            file_name: str = Path(file_path).name
            config_utility.set_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, file_name, project_id)
            self._create_utility()
            self.start_worker()
            self._create_progress_ring_window()
            self._generate_voice_id_for_voice_excel_signal.emit(file_path)

    def generate_voice_event_for_voice_excel_action(self):
        file_dialog: QFileDialog = QFileDialog(self.main_window)
        file_dialog.setWindowTitle("请选择录音工作簿")
        project_id: str | None = self.main_window.get_current_project_id()
        last_selected_file_parent_path: str = config_utility.get_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, project_id)

        if last_selected_file_parent_path and os.path.isdir(last_selected_file_parent_path):
            set_directory: str = last_selected_file_parent_path
        else:
            set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]

        file_dialog.setDirectory(set_directory)
        last_selected_file_name: str = config_utility.get_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, project_id)
        if last_selected_file_name:
            last_selected_file_path = f"{set_directory}/{last_selected_file_name}"
            if os.path.isfile(last_selected_file_path):
                file_dialog.selectFile(last_selected_file_name)

        file_dialog.setNameFilter("Excel文件 (*.xlsx)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setViewMode(QFileDialog.ViewMode.List)
        file_path: str = ""
        file_parent_path: str = ""
        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]
            file_directory: QDir = file_dialog.directory()
            file_parent_path = file_directory.path()
            print(f"录音工作簿所在目录路径: {file_parent_path}.")

        if not file_path:
            return
        print(f"录音工作簿: {file_path}.")

        if self._create_dialog("确认执行生成语音事件?", f"录音工作簿: \"{file_path}\""):
            config_utility.set_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, file_parent_path, project_id)
            file_name: str = Path(file_path).name
            config_utility.set_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, file_name, project_id)
            self._create_utility()
            self.start_worker()
            self._create_progress_ring_window()
            self._generate_voice_event_for_voice_excel_signal.emit(file_path)

    def format_voice_excel_action(self):
        file_dialog: QFileDialog = QFileDialog(self.main_window)
        file_dialog.setWindowTitle("请选择录音工作簿")
        project_id: str | None = self.main_window.get_current_project_id()
        last_selected_file_parent_path: str = config_utility.get_config(VoiceJob._LAST_SELECTED_FORMAT_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, project_id)

        if last_selected_file_parent_path and os.path.isdir(last_selected_file_parent_path):
            set_directory: str = last_selected_file_parent_path
        else:
            last_selected_file_parent_path = config_utility.get_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, project_id)
            if last_selected_file_parent_path and os.path.isdir(last_selected_file_parent_path):
                set_directory: str = last_selected_file_parent_path
            else:
                set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]

        file_dialog.setDirectory(set_directory)
        last_selected_file_name: str = config_utility.get_config(VoiceJob._LAST_SELECTED_FORMAT_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, project_id)
        if last_selected_file_name:
            last_selected_file_path = f"{set_directory}/{last_selected_file_name}"
            if os.path.isfile(last_selected_file_path):
                file_dialog.selectFile(last_selected_file_name)
        else:
            last_selected_file_name: str = config_utility.get_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, project_id)
            if last_selected_file_name:
                last_selected_file_path = f"{set_directory}/{last_selected_file_name}"
                if os.path.isfile(last_selected_file_path):
                    file_dialog.selectFile(last_selected_file_name)
        file_dialog.setNameFilter("Excel文件 (*.xlsx)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setViewMode(QFileDialog.ViewMode.List)
        file_path: str = ""
        file_parent_path: str = ""
        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]
            file_directory: QDir = file_dialog.directory()
            file_parent_path = file_directory.path()
            print(f"录音工作簿所在目录路径: {file_parent_path}.")

        if not file_path:
            return
        print(f"录音工作簿: {file_path}.")

        if self._create_dialog("确认执行格式化?", f"录音工作簿: \"{file_path}\""):
            config_utility.set_config(VoiceJob._LAST_SELECTED_FORMAT_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, file_parent_path, project_id)
            file_name: str = Path(file_path).name
            config_utility.set_config(VoiceJob._LAST_SELECTED_FORMAT_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, file_name, project_id)
            self._create_utility()
            self.start_worker()
            self._create_progress_ring_window()
            self._format_voice_excel_signal.emit(file_path)

    def rename_voice_sample_by_voice_excel_action(self):
        dir_dialog: QFileDialog = QFileDialog(self.main_window)
        dir_dialog.setWindowTitle("请选择语音素材目录")
        dir_dialog.setFileMode(QFileDialog.FileMode.Directory)
        dir_dialog.setViewMode(QFileDialog.ViewMode.List)
        project_id: str | None = self.main_window.get_current_project_id()
        last_selected_rename_voice_sample_parent_path: str = config_utility.get_config(VoiceJob._LAST_SELECTED_RENAME_VOICE_SAMPLE_PARENT_PATH_CONFIG_NAME, project_id)
        if last_selected_rename_voice_sample_parent_path and os.path.isdir(last_selected_rename_voice_sample_parent_path):
            set_directory: str = last_selected_rename_voice_sample_parent_path
        else:
            set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        dir_dialog.setDirectory(set_directory)

        dir_path: str = ""
        dir_parent_path: str = ""
        if dir_dialog.exec():
            dir_path: str = dir_dialog.selectedFiles()[0]  # print(f"语音素材目录路径: {dir_path}.")
            dir_info: QFileInfo = QFileInfo(dir_path)
            dir_parent_path = dir_info.dir().path()

        if not dir_path:
            return

        excel_dialog: QFileDialog = QFileDialog(self.main_window)
        excel_dialog.setWindowTitle("请选择录音工作簿")
        last_selected_excel_parent_path: str = config_utility.get_config(VoiceJob._LAST_SELECTED_FORMAT_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, project_id)

        if last_selected_excel_parent_path and os.path.isdir(last_selected_excel_parent_path):
            set_directory: str = last_selected_excel_parent_path
        else:
            last_selected_excel_parent_path = config_utility.get_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, project_id)
            if last_selected_excel_parent_path and os.path.isdir(last_selected_excel_parent_path):
                set_directory: str = last_selected_excel_parent_path
            else:
                set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]

        excel_dialog.setDirectory(set_directory)
        last_selected_excel_name: str = config_utility.get_config(VoiceJob._LAST_SELECTED_FORMAT_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, project_id)
        if last_selected_excel_name:
            last_selected_excel_path = f"{set_directory}/{last_selected_excel_name}"
            if os.path.isfile(last_selected_excel_path):
                excel_dialog.selectFile(last_selected_excel_name)
        else:
            last_selected_excel_name: str = config_utility.get_config(VoiceJob.LAST_SELECTED_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, project_id)
            if last_selected_excel_name:
                last_selected_excel_path = f"{set_directory}/{last_selected_excel_name}"
                if os.path.isfile(last_selected_excel_path):
                    excel_dialog.selectFile(last_selected_excel_name)
        excel_dialog.setNameFilter("Excel文件 (*.xlsx)")
        excel_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        excel_dialog.setViewMode(QFileDialog.ViewMode.List)
        excel_path: str = ""
        excel_parent_path: str = ""
        if excel_dialog.exec():
            excel_path = excel_dialog.selectedFiles()[0]
            excel_dir: QDir = excel_dialog.directory()
            excel_parent_path = excel_dir.path()  # print(f"录音工作簿所在目录路径: {excel_parent_path}.")

        if not excel_path:
            return

        if self._create_dialog("确认执行重命名语音素材?", f"语音素材目录: \"{dir_path}\"\n录音工作簿: \"{excel_path}\""):
            config_utility.set_config(VoiceJob._LAST_SELECTED_FORMAT_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, excel_parent_path, project_id)
            excel_name: str = Path(excel_path).name
            config_utility.set_config(VoiceJob._LAST_SELECTED_FORMAT_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, excel_name, project_id)
            config_utility.set_config(VoiceJob._LAST_SELECTED_RENAME_VOICE_SAMPLE_PARENT_PATH_CONFIG_NAME, dir_parent_path, project_id)
            self._create_utility()
            self.start_worker()
            self._create_progress_ring_window()
            self._rename_voice_sample_by_voice_excel_signal.emit(dir_path, excel_path)

    def _show_dialogue_check_list_window(self, title: str, dialogue_check_list: [(str, bool)]):
        if self._dialogue_check_list_window:
            self._dialogue_check_list_window.close()
            self._dialogue_check_list_window.deleteLater()
            self._dialogue_check_list_window = None
        self._dialogue_check_list_window = CheckListWindow(title, dialogue_check_list)
        self._dialogue_check_list_window.window_closed_signal.connect(self._on_dialogue_check_list_window_closed)

    def _on_dialogue_check_list_window_closed(self):
        if not self._dialogue_check_list_window:
            return
        self._dialogue_check_list_window.deleteLater()
        self._dialogue_check_list_window = None

    def job_finish(self, title: str, content: str, result: str):
        if self._voice_excel_utility:
            self._voice_excel_utility.deleteLater()
            self._voice_excel_utility = None
        super().job_finish(title, content, result)

    def _create_utility(self):
        self._voice_excel_utility: VoiceExcelUtility = VoiceExcelUtility(self)
        self._voice_excel_utility.moveToThread(self.worker_thread)

        self._sync_export_excel_and_voice_excel_signal.connect(self._voice_excel_utility.sync_dialogue_data)
        self._sync_localized_voice_excel_signal.connect(self._voice_excel_utility.sync_localized_dialogue_data)
        self._generate_voice_id_for_voice_excel_signal.connect(self._voice_excel_utility.generate_voice_id_for_voice_excel)
        self._generate_voice_event_for_voice_excel_signal.connect(self._voice_excel_utility.generate_voice_event_for_voice_excel)
        self._format_voice_excel_signal.connect(self._voice_excel_utility.format_voice_excel)
        self._rename_voice_sample_by_voice_excel_signal.connect(self._voice_excel_utility.rename_voice_sample_by_voice_excel)

        self._voice_excel_utility.show_dialogue_check_list_window_signal.connect(self._show_dialogue_check_list_window)

    def _create_progress_ring_window(self):
        self._progress_ring_window: ProgressRingWindow = ProgressRingWindow(self.main_window)
        self._progress_ring_window.cancel_signal.connect(lambda: self._voice_excel_utility.notice_cancel_job())

        self._voice_excel_utility.update_progress_text_signal.connect(self._progress_ring_window.set_text)
