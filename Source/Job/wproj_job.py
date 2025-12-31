import os
import os.path
import pathlib
import subprocess
from pathlib import Path
from typing import Optional

from lxml.etree import Element
from PySide6.QtCore import QStandardPaths, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

import main
from Source.Job.base_job import BaseJob
from Source.UI.Basic.check_list_window import CheckListWindow
from Source.UI.Basic.import_voice_option_window import ImportVoiceOptionWindow
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.UI.Basic.progress_ring_window import ProgressRingWindow
from Source.UI.Basic.wwise_object_check_window import WwiseObjectCheckWindow
from Source.Utility import wproj_utility
from Source.Utility.config_utility import config_utility, ProjectData
from Source.Utility.file_utility import FileUtility
from Source.Utility.svn_utility import SVNUtility
from Source.Utility.waapi_utility import WaapiUtility
from Source.Utility.wproj_utility import WprojUtility


class WprojJob(BaseJob):
    _LAST_SELECTED_IMPORT_SAMPLE_DIR_PATH_CONFIG_NAME = "LastSelectedImportSampleDirPath"
    LAST_SELECTED_IMPORT_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME = "LastSelectedImportVoiceExcelFileParentPath"
    LAST_SELECTED_IMPORT_VOICE_EXCEL_FILE_NAME_CONFIG_NAME = "LastSelectedImportVoiceExcelFileName"

    _sync_original_dir_structure_signal = Signal(str)
    on_sync_original_dir_structure_complete_signal = Signal(bool)

    _clean_akd_file_signal: Signal = Signal(str)
    _clean_unused_sample_signal: Signal = Signal(str)

    # _sync_external_source_list_signal = Signal(str)
    # convert_external_source_signal = Signal(str)

    _validate_sample_name_for_import_signal = Signal(str)
    _validate_example_actor_mixer_for_import_signal = Signal(str)
    _import_sample_signal = Signal(dict)

    _split_work_unit_signal = Signal()

    _find_sound_object_contain_inactive_source_signal: Signal = Signal(str)
    _find_missing_language_voice_object_signal: Signal = Signal(str)
    _find_wrong_referenced_voice_event_signal: Signal = Signal(str)
    _select_sound_object_within_text_signal = Signal(str)
    _test_signal = Signal()

    _validate_wwise_project_succeeded_signal = Signal(str)

    _update_wwise_authoring_signal = Signal(dict)
    _check_workcopy_has_update_signal = Signal(dict)

    def __init__(self, main_window):
        super().__init__(main_window)
        self._wproj_utility: WprojUtility | None = None
        self._waapi_utility: WaapiUtility | None = None
        self._svn_utility: Optional[SVNUtility] = None
        self.file_utility: FileUtility = FileUtility(self)
        self._wwise_object_check_window: WwiseObjectCheckWindow | None = None
        self._check_window: CheckListWindow | None = None
        self._import_voice_option_window: Optional[ImportVoiceOptionWindow] = None

    def uninit(self):
        if self._wwise_object_check_window:
            self._wwise_object_check_window.close()
            if self._wwise_object_check_window:
                self._wwise_object_check_window.deleteLater()
                self._wwise_object_check_window = None

        if self._check_window:
            self._check_window.close()
            if self._check_window:
                self._check_window.deleteLater()
                self._check_window = None

        if self._import_voice_option_window:
            self._import_voice_option_window.close()
            if self._import_voice_option_window:
                self._import_voice_option_window.deleteLater()
                self._import_voice_option_window = None

        super().unit()

    def read_wproj_file(self, wproj_file_path: str) -> Element | None:
        self._create_wproj_utility()
        return self._wproj_utility.read_wwise_project_file(wproj_file_path)

    @staticmethod
    def get_wwise_version(wproj_root_element: Element) -> str | None:
        return WprojUtility.get_wwise_version(wproj_root_element)

    @staticmethod
    def get_language(wproj_root_element: Element) -> [str]:
        return WprojUtility.get_language_list(wproj_root_element)

    @staticmethod
    def get_reference_language(wproj_root_element: Element) -> [str]:
        return WprojUtility.get_reference_language(wproj_root_element)

    def open_wwise_project_prepare_action(self, project_id: str):
        self._create_wproj_utility()
        wwise_authoring_path = self._wproj_utility.get_best_match_wwise_authoring_path(project_id)
        if not wwise_authoring_path:
            self.job_finish("任务中止", "", "error")
            return

        wwise_authoring_path = pathlib.PurePosixPath(wwise_authoring_path)
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        if not os.path.isfile(wwise_project_path):
            self.show_error_info_bar(f"无法在以下路径找到Wwise工程, 请确认:\n\"{wwise_project_path}\"")
            self.job_finish("任务中止", "", "error")
            return
        if main.is_windows_os():
            wwise_authoring_root_dir_path = str(wwise_authoring_path)[: len(str(wwise_authoring_path)) - len("/Authoring/x64/Release/bin/Wwise.exe")]
            self._create_svn_utility()
            if self._svn_utility.check_dir_is_workcopy(wwise_authoring_root_dir_path):
                self._check_workcopy_has_update_signal.connect(self._svn_utility.check_workcopy_has_update_job)
                self._svn_utility.check_workcopy_update_complete_signal.connect(self._check_wwise_authoring_update_complete)
                self._svn_utility.moveToThread(self.worker_thread)
                self.start_worker()
                self._create_progress_ring_window()
                self._progress_ring_window.set_enable_cancel(False)
                info_dict = {
                    "dir_path":                  wwise_authoring_root_dir_path,
                    "wwise_authoring_file_path": str(wwise_authoring_path),
                    "wwise_project_path":        wwise_project_path
                }
                self._check_workcopy_has_update_signal.emit(info_dict)
                return

            self._svn_utility.deleteLater()
            self._svn_utility = None
            subprocess.Popen([wwise_authoring_path, wwise_project_path])
        else:
            subprocess.Popen([f"{wwise_authoring_path}/Contents/Tools/WwiseOpenProject.sh", wwise_project_path])
        self.job_finish("结果", "打开Wwise工程成功", "success")

    def _check_wwise_authoring_update_complete(self, info_dict: dict):
        has_update = info_dict.get("has_update", False)
        if has_update:
            if self._create_dialog("提醒", "Wwise设计工具存在更新, 是否更新?"):
                self._create_svn_utility()
                self._svn_utility.update_wwise_authoring_succeed_signal.connect(self._open_wwise_project_after_update)
                self._svn_utility.moveToThread(self.worker_thread)
                self.start_worker()
                self._create_progress_ring_window()
                self._progress_ring_window.set_enable_cancel(False)
                self._update_wwise_authoring_signal.emit(info_dict)
                return
        self._open_wwise_project_after_update(info_dict)

    def _open_wwise_project_after_update(self, wwise_authoring_info_dict: dict):
        wwise_authoring_file_path = wwise_authoring_info_dict["wwise_authoring_file_path"]
        wwise_project_path = wwise_authoring_info_dict["wwise_project_path"]
        subprocess.Popen([wwise_authoring_file_path, wwise_project_path])

    def sync_original_dir_structure_action(self):
        self._validate_wwise_project_succeeded_signal.connect(self.sync_original_dir_structure_implement_action)
        if not self._validate_wwise_project_optional_open_action():
            self._validate_wwise_project_succeeded_signal.disconnect()

    def sync_original_dir_structure_implement_action(self, project_id: str):
        self._validate_wwise_project_succeeded_signal.disconnect()
        self._create_wproj_utility()
        self._wproj_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._create_progress_bar_window()
        self._sync_original_dir_structure_signal.emit(project_id)

    def clean_akd_file_action(self, project_id: str):
        self._create_wproj_utility()
        self._wproj_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._create_progress_ring_window()
        self._clean_akd_file_signal.emit(project_id)

    def clean_unused_sample_action(self, project_id: str):
        self._create_wproj_utility()
        self._wproj_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._create_progress_ring_window()
        self._clean_unused_sample_signal.emit(project_id)

    def open_external_source_dir_action(self, project_id: str):
        external_source_dir_path = self.get_external_source_dir(project_id)
        if not os.path.isdir(external_source_dir_path):
            self._create_wproj_utility()
            self._wproj_utility.create_directory(external_source_dir_path)
            self.job_finish("结果", "创建目录完成", "success")
        QDesktopServices.openUrl(f"file:///{Path(external_source_dir_path)}")

    def get_external_source_dir(self, project_id: str) -> str:
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wwise_project_dir_path = os.path.dirname(wwise_project_path)
        wproj_root_element = self.read_wproj_file(wwise_project_path)
        original_dir_path: str = WprojUtility.get_original_sample_path(wproj_root_element)
        if not original_dir_path:
            original_dir_path = "Originals"
        external_source_dir_path = f"{wwise_project_dir_path}/{original_dir_path}/ExternalSource"
        if self._wproj_utility:
            self._wproj_utility.deleteLater()
            self._wproj_utility = None
        return external_source_dir_path

    '''
    def sync_external_source_list_action(self, project_id: str):
        self._create_wproj_utility()
        self._wproj_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._create_progress_ring_window()
        self._sync_external_source_list_signal.emit(project_id)

    def open_external_source_list_action(self, project_id: str):
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wwise_project_dir_path = os.path.dirname(wwise_project_path)
        generated_soundbank_dir_path = f"{wwise_project_dir_path}/GeneratedSoundBanks"
        external_source_list_file_name = "ExternalSourceList.xml"
        external_source_list_path = f"{generated_soundbank_dir_path}/{external_source_list_file_name}"
        if not os.path.isfile(external_source_list_path):
            self.show_error_info_bar("外部源列表不存在, 请先刷新外部源列表.")
            return
        QDesktopServices.openUrl(f"file:///{external_source_list_path}")

    def convert_external_source_action(self, project_id: str):
        self._create_wproj_utility()
        self._wproj_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._create_progress_ring_window()
        self.convert_external_source_signal.emit(project_id)
    '''

    def sample_import_action(self):
        self._validate_wwise_project_succeeded_signal.connect(self._validate_sample_name_for_import_action)
        if not self._validate_wwise_project_require_open_action():
            self._validate_wwise_project_succeeded_signal.disconnect()

    def _validate_sample_name_for_import_action(self, project_id: str):
        self._validate_wwise_project_succeeded_signal.disconnect()
        wproj_utility.CUSTOM_IMPORT_CHARACTER_TYPE_DICT = self._waapi_utility.get_custom_auto_import_sample_type_dict()

        dir_dialog = QFileDialog(self.main_window)
        dir_dialog.setWindowTitle("请选择素材目录")
        dir_dialog.setFileMode(QFileDialog.FileMode.Directory)
        dir_dialog.setViewMode(QFileDialog.ViewMode.List)
        last_selected_import_sample_dir_path = config_utility.get_config(WprojJob._LAST_SELECTED_IMPORT_SAMPLE_DIR_PATH_CONFIG_NAME, project_id)
        if last_selected_import_sample_dir_path and os.path.isdir(last_selected_import_sample_dir_path):
            set_directory = last_selected_import_sample_dir_path
        else:
            set_directory = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        dir_dialog.setDirectory(set_directory)

        dir_path = ""
        if dir_dialog.exec():
            dir_path = dir_dialog.selectedFiles()[0]

        if not dir_path:
            self.job_finish("结果", "任务中止", "warning")
            return

        self._create_wproj_utility()
        self._wproj_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._create_progress_ring_window()
        self._validate_sample_name_for_import_signal.emit(dir_path)

    def _validate_example_actor_mixer_for_import_action(self, dir_path: str):
        self._waapi_utility.moveToThread(self.worker_thread)
        self._validate_example_actor_mixer_for_import_signal.emit(dir_path)

    def _show_import_voice_option_window(self, dir_path: str, has_voice_sample: bool):
        self.delete_progress_window()
        if self._import_voice_option_window:
            self._import_voice_option_window.close()
            self._import_voice_option_window.deleteLater()
            self._import_voice_option_window = None
        project_id = self.main_window.get_current_project_id()
        if has_voice_sample:
            parameter_dict = {}
            wwise_project_path = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
            wproj_root_element = self.read_wproj_file(wwise_project_path)
            language_list: [str] = WprojJob.get_language(wproj_root_element)
            reference_language: str = WprojJob.get_reference_language(wproj_root_element)
            parameter_dict["dir_path"] = dir_path
            parameter_dict["project_id"] = project_id
            parameter_dict["language_list"] = language_list
            parameter_dict["reference_language"] = reference_language
            self._import_voice_option_window = ImportVoiceOptionWindow(parameter_dict)
            self._import_voice_option_window.accept_signal.connect(self._on_import_voice_option_window_accepted)
            self._import_voice_option_window.cancel_signal.connect(self._on_import_voice_option_window_cancelled)
        else:
            check_str = f"素材目录: \"{dir_path}\""
            if self._create_dialog("确认执行入库?", check_str):
                dir_parent_path = os.path.dirname(dir_path)
                config_utility.set_config(WprojJob._LAST_SELECTED_IMPORT_SAMPLE_DIR_PATH_CONFIG_NAME, dir_parent_path, project_id)
                self._create_progress_bar_window()
                parameter_dict = {
                    "dir_path": dir_path
                }
                self._import_sample_signal.emit(parameter_dict)
            else:
                self.worker_thread.quit()
                self.job_finish("结果", "任务中止", "warning")

    def _on_import_voice_option_window_accepted(self):
        project_id = self._import_voice_option_window.project_id
        dir_path = self._import_voice_option_window.dir_path
        import_language_list = self._import_voice_option_window.import_language_list
        reference_language = self._import_voice_option_window.reference_language
        dir_parent_path = os.path.dirname(dir_path)
        voice_excel_file_path = self._import_voice_option_window.voice_excel_file_path
        voice_excel_file_parent_path = self._import_voice_option_window.voice_excel_file_parent_path

        check_str = f"素材目录: \"{dir_path}\""
        if len(import_language_list) == 0:
            check_str = f"{check_str}\n没有选择入库语言, 语音素材将会被忽略, 不执行入库操作"
        else:
            check_str = f"{check_str}\n语音素材将会以\"{import_language_list}\"语言入库"
            if voice_excel_file_path:
                check_str = f"{check_str}\n已选择录音工作簿辅助语音素材入库标记, 录音工作簿路径: \"{voice_excel_file_path}\""
            else:
                check_str = f"{check_str}\n没有选择录音工作簿辅助语音素材入库标记"

        if self._create_dialog("确认执行入库?", check_str):
            config_utility.set_config(WprojJob._LAST_SELECTED_IMPORT_SAMPLE_DIR_PATH_CONFIG_NAME, dir_parent_path, project_id)
            if voice_excel_file_path:
                config_utility.set_config(WprojJob.LAST_SELECTED_IMPORT_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, voice_excel_file_parent_path, project_id)
                voice_excel_file_name = Path(voice_excel_file_path).name
                config_utility.set_config(WprojJob.LAST_SELECTED_IMPORT_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, voice_excel_file_name, project_id)
            self._create_progress_bar_window()
            parameter_dict = {
                "dir_path":              dir_path,
                "import_language_list":  import_language_list,
                "reference_language":    reference_language,
                "voice_excel_file_path": voice_excel_file_path
            }
            self._import_sample_signal.emit(parameter_dict)
        else:
            self.worker_thread.quit()
            self.job_finish("结果", "任务中止", "warning")

        if not self._import_voice_option_window:
            return
        self._import_voice_option_window.deleteLater()
        self._import_voice_option_window = None

    def _on_import_voice_option_window_cancelled(self):
        if not self._import_voice_option_window:
            return
        self._import_voice_option_window.deleteLater()
        self._import_voice_option_window = None
        self.worker_thread.quit()
        self.job_finish("结果", "任务中止", "warning")

    def split_work_unit_action(self):
        self._validate_wwise_project_succeeded_signal.connect(self.split_work_unit_implement_action)
        if not self._validate_wwise_project_require_open_action():
            self._validate_wwise_project_succeeded_signal.disconnect()

    def split_work_unit_implement_action(self):
        self._validate_wwise_project_succeeded_signal.disconnect()
        self._waapi_utility.moveToThread(self.worker_thread)
        self.worker_thread.start()
        self._create_progress_ring_window()
        self._split_work_unit_signal.emit()

    def find_sound_object_contain_inactive_source_action(self):
        self._validate_wwise_project_succeeded_signal.connect(self.find_sound_object_contain_inactive_source_implement_action)
        if not self._validate_wwise_project_require_open_action():
            self._validate_wwise_project_succeeded_signal.disconnect()

    def find_sound_object_contain_inactive_source_implement_action(self, project_id: str):
        self._waapi_utility.disconnect_waapi()
        self._validate_wwise_project_succeeded_signal.disconnect()
        self._create_wproj_utility()
        self._wproj_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._create_progress_ring_window()
        self._find_sound_object_contain_inactive_source_signal.emit(project_id)

    def find_missing_language_voice_object_action(self):
        self._validate_wwise_project_succeeded_signal.connect(self.find_missing_language_voice_object_implement_action)
        if not self._validate_wwise_project_require_open_action():
            self._validate_wwise_project_succeeded_signal.disconnect()

    def find_missing_language_voice_object_implement_action(self, project_id: str):
        self._waapi_utility.disconnect_waapi()
        self._validate_wwise_project_succeeded_signal.disconnect()
        self._create_wproj_utility()
        self._wproj_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._create_progress_ring_window()
        self._find_missing_language_voice_object_signal.emit(project_id)

    def find_wrong_referenced_voice_event_action(self):
        self._validate_wwise_project_succeeded_signal.connect(self.find_wrong_referenced_voice_event_implement_action)
        if not self._validate_wwise_project_require_open_action():
            self._validate_wwise_project_succeeded_signal.disconnect()

    def find_wrong_referenced_voice_event_implement_action(self, project_id: str):
        self._waapi_utility.disconnect_waapi()
        self._validate_wwise_project_succeeded_signal.disconnect()
        self._create_wproj_utility()
        self._wproj_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._create_progress_ring_window()
        self._find_wrong_referenced_voice_event_signal.emit(project_id)

    def select_sound_object_within_text_action(self):
        self._validate_wwise_project_succeeded_signal.connect(self.select_sound_object_within_text_implement_action)
        if not self._validate_wwise_project_require_open_action():
            self._validate_wwise_project_succeeded_signal.disconnect()

    def select_sound_object_within_text_implement_action(self):
        self._validate_wwise_project_succeeded_signal.disconnect()

        file_dialog = QFileDialog(self.main_window)
        file_dialog.setWindowTitle("请选择含有需要在Wwise设计工具中选中声音对象的事件的文本文件")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setViewMode(QFileDialog.ViewMode.List)
        file_dialog.setNameFilter("文本文件 (*.txt)")
        set_directory = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        file_dialog.setDirectory(set_directory)

        file_path = ""
        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]

        if not file_path:
            self.job_finish("结果", "任务中止", "warning")
            return

        if self._create_dialog("确认执行?", f"文本文件: \"{file_path}\""):
            self._waapi_utility.moveToThread(self.worker_thread)
            self.start_worker()
            self._create_progress_ring_window()
            self._progress_ring_window.set_enable_cancel(False)
            self._select_sound_object_within_text_signal.emit(file_path)
        else:
            self.job_finish("结果", "任务中止", "warning")

    def job_finish(self, title: str, content: str, result: str):
        if self._wproj_utility:
            self._wproj_utility.deleteLater()
            self._wproj_utility = None

        if self._waapi_utility:
            self._waapi_utility.disconnect_waapi()
            self._waapi_utility.deleteLater()
            self._waapi_utility = None

        if self._svn_utility:
            self._svn_utility.deleteLater()
            self._svn_utility = None

        super().job_finish(title, content, result)

    def _create_wproj_utility(self):
        self._wproj_utility: WprojUtility = WprojUtility(self)
        self._wproj_utility.show_wwise_object_check_window_signal.connect(self._show_wwise_object_check_window)
        self._wproj_utility.show_check_window_signal.connect(self._show_check_window)
        self._wproj_utility.validate_import_sample_name_succeeded_signal.connect(self._validate_example_actor_mixer_for_import_action)

        self._sync_original_dir_structure_signal.connect(self._wproj_utility.sync_original_dir_structure_job)
        self._clean_akd_file_signal.connect(self._wproj_utility.clean_akd_file_job)
        self._clean_unused_sample_signal.connect(self._wproj_utility.clean_unused_sample_job)

        # self._sync_external_source_list_signal.connect(self._wproj_utility.sync_external_source_list)
        # self.convert_external_source_signal.connect(self._wproj_utility.convert_external_source)

        self._validate_sample_name_for_import_signal.connect(self._wproj_utility.validate_sample_name_for_import_job)
        self._find_sound_object_contain_inactive_source_signal.connect(self._wproj_utility.find_sound_object_contain_inactive_source_job)
        self._find_missing_language_voice_object_signal.connect(self._wproj_utility.find_missing_language_voice_object_job)
        self._find_wrong_referenced_voice_event_signal.connect(self._wproj_utility.find_wrong_referenced_voice_event_job)

    def _create_waapi_utility(self):
        self._waapi_utility: WaapiUtility = WaapiUtility(self)
        self._waapi_utility.show_wwise_object_check_window_signal.connect(self._show_wwise_object_check_window)
        self._waapi_utility.show_check_window_signal.connect(self._show_check_window)
        self._waapi_utility.validate_for_import_succeeded_signal.connect(self._show_import_voice_option_window)

        self._validate_example_actor_mixer_for_import_signal.connect(self._waapi_utility.validate_for_import_job)
        self._import_sample_signal.connect(self._waapi_utility.import_sample_job)
        self._split_work_unit_signal.connect(self._waapi_utility.split_work_unit_job)
        self._select_sound_object_within_text_signal.connect(self._waapi_utility.select_sound_object_within_text_job)

        self._test_signal.connect(self._waapi_utility.post_event)

    def _create_svn_utility(self):
        self._svn_utility = SVNUtility(self)
        self._update_wwise_authoring_signal.connect(self._svn_utility.update_wwise_authoring_job)

    def _create_progress_bar_window(self):
        self._progress_bar_window: ProgressBarWindow = ProgressBarWindow(self.main_window)

        if self._wproj_utility:
            self._progress_bar_window.cancel_signal.connect(lambda: self._wproj_utility.notice_cancel_job())
            self._wproj_utility.update_progress_text_signal.connect(self._progress_bar_window.set_text)
            self._wproj_utility.update_progress_total_count_signal.connect(self._progress_bar_window.set_total_count)
            self._wproj_utility.update_progress_current_count_signal.connect(self._progress_bar_window.set_current_count)

        if self._waapi_utility:
            self._progress_bar_window.cancel_signal.connect(lambda: self._waapi_utility.notice_cancel_job())
            self._waapi_utility.update_progress_text_signal.connect(self._progress_bar_window.set_text)
            self._waapi_utility.update_progress_total_count_signal.connect(self._progress_bar_window.set_total_count)
            self._waapi_utility.update_progress_current_count_signal.connect(self._progress_bar_window.set_current_count)

    def _create_progress_ring_window(self):
        self._progress_ring_window: ProgressRingWindow = ProgressRingWindow(self.main_window)

        if self._wproj_utility:
            self._wproj_utility.update_progress_text_signal.connect(self._progress_ring_window.set_text)
            self._progress_ring_window.cancel_signal.connect(lambda: self._wproj_utility.notice_cancel_job())

        if self._waapi_utility:
            self._progress_ring_window.cancel_signal.connect(lambda: self._waapi_utility.notice_cancel_job())
            self._waapi_utility.update_progress_text_signal.connect(self._progress_ring_window.set_text)

        if self._svn_utility:
            self._svn_utility.update_progress_text_signal.connect(self._progress_ring_window.set_text)
            self._progress_ring_window.cancel_signal.connect(lambda: self._svn_utility.notice_cancel_job())

    def _show_wwise_object_check_window(self, title: str, check_list):
        if self._wwise_object_check_window:
            self._wwise_object_check_window.close()
            self._wwise_object_check_window.deleteLater()
            self._wwise_object_check_window = None
        self._wwise_object_check_window = WwiseObjectCheckWindow(title, check_list)
        self._wwise_object_check_window.window_closed_signal.connect(self._on_wwise_object_check_window_closed)

    def _on_wwise_object_check_window_closed(self):
        if not self._wwise_object_check_window:
            return
        self._wwise_object_check_window.deleteLater()
        self._wwise_object_check_window = None

    def _show_check_window(self, title: str, dialogue_check_list: [(str, bool)]):
        if self._check_window:
            self._check_window.close()
            self._check_window = None
        self._check_window = CheckListWindow(title, dialogue_check_list)
        self._check_window.window_closed_signal.connect(self._on_check_window_closed)

    def _on_check_window_closed(self):
        if not self._check_window:
            return
        self._check_window.deleteLater()
        self._check_window = None

    def _validate_wwise_project_require_open_action(self) -> bool:
        project_id: str = self.main_window.get_current_project_id()
        if not WprojUtility.is_wwise_project_valid(project_id):
            self.show_error_info_bar("当前项目的Wwise工程不合法, 请为当前项目设置合法的Wwise工程后再执行.")
            self.job_finish("结果", "任务中止", "warning")
            return False

        self._create_waapi_utility()

        if not self._waapi_utility.connect_waapi():
            self.show_error_info_bar("Waapi未建立连接, 请打开Wwise设计工具并开启Waapi相关功能.")
            self.job_finish("结果", "任务中止", "warning")
            return False

        if not self._waapi_utility.is_current_wwise_project_open(project_id):
            self.show_error_info_bar("Wwise设计工具未打开当前项目的Wwise工程, 请打开Wwise工程后再执行.")
            self.job_finish("结果", "任务中止", "warning")
            return False

        # noinspection PyUnusedLocal
        def on_wwise_project_save(*args, **kwargs):
            self._validate_wwise_project_succeeded_signal.emit(project_id)

        if self._waapi_utility.is_current_wwise_project_dirty():
            if self._create_dialog("提醒", f"当前打开的Wwise工程存在未保存的修改, 点击确认将会保存当前打开的Wwise工程并继续执行."):
                self._waapi_utility.client.subscribe("ak.wwise.core.project.saved", on_wwise_project_save)
                self._waapi_utility.save_wwise_project()
                return True
            else:
                self.job_finish("结果", "任务中止", "warning")
                return False
        else:
            self._validate_wwise_project_succeeded_signal.emit(project_id)
            return True

    def _validate_wwise_project_optional_open_action(self) -> bool:
        project_id: str = self.main_window.get_current_project_id()
        if not WprojUtility.is_wwise_project_valid(project_id):
            self.show_error_info_bar("当前项目的Wwise工程不合法, 请为当前项目设置合法的Wwise工程后再执行.")
            self.job_finish("结果", "任务中止", "warning")
            return False

        self._create_waapi_utility()

        if not self._waapi_utility.connect_waapi():
            self._validate_wwise_project_succeeded_signal.emit(project_id)
            return True

        if not self._waapi_utility.is_current_wwise_project_open(project_id):
            self._validate_wwise_project_succeeded_signal.emit(project_id)
            return True

        # noinspection PyUnusedLocal
        def on_wwise_project_save(*args, **kwargs):
            self._validate_wwise_project_succeeded_signal.emit(project_id)

        if self._waapi_utility.is_current_wwise_project_dirty():
            if self._create_dialog("提醒", f"当前打开的Wwise工程存在未保存的修改, 点击确认将会保存当前打开的Wwise工程并继续执行."):
                self._waapi_utility.client.subscribe("ak.wwise.core.project.saved", on_wwise_project_save)
                self.on_sync_original_dir_structure_complete_signal.connect(self.on_sync_original_dir_structure_complete)
                self._waapi_utility.save_wwise_project()
                return True
            else:
                self.job_finish("结果", "任务中止", "warning")
                return False
        else:
            self.on_sync_original_dir_structure_complete_signal.connect(self.on_sync_original_dir_structure_complete)
            self._validate_wwise_project_succeeded_signal.emit(project_id)
            return True

    def on_sync_original_dir_structure_complete(self, is_modified: bool):
        # macOS平台的Wwise设计工具无法自动检测到工作单元或工程的变动, 所以同步完后自动重新打开Wwise工程防止在旧的工作单元或工程上继续做修改
        self.on_sync_original_dir_structure_complete_signal.disconnect()
        if not is_modified or main.is_windows_os():
            return
        self._waapi_utility.connect_waapi()
        self._waapi_utility.reopen_wwise_project()
        self._waapi_utility.disconnect_waapi()

    def test_action(self):
        self._validate_wwise_project_succeeded_signal.connect(self.test_implement_action)
        if not self._validate_wwise_project_require_open_action():
            self._validate_wwise_project_succeeded_signal.disconnect()

    def test_implement_action(self, project_id: str):
        self._validate_wwise_project_succeeded_signal.disconnect()
        self._waapi_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._test_signal.emit()
