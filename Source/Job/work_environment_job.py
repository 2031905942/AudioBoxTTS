import os
import pathlib
from typing import Optional

from PySide6.QtCore import Signal

from Source.Job.base_job import BaseJob
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.UI.Basic.progress_ring_window import ProgressRingWindow
from Source.UI.WorkEnvironmentJob.unity_install_version_select_window import UnityInstallVersionSelectWindow
from Source.UI.WorkEnvironmentJob.wwise_authoring_install_version_select_window import WwiseAuthoringInstallVersionSelectWindow
from Source.Utility.config_utility import config_utility
from Source.Utility.svn_utility import SVNUtility
from Source.Utility.work_environment_utility import WorkEnvironmentUtility
from webdav4.client import Client


class WorkEnvironmentJob(BaseJob):
    WEBDAV_URL = "https://jazmaybe.com:5008"
    WEBDAV_USER = "MoontonAudio"
    WEBDAV_PASSWORD = "MoontonAudio123"
    WEBDAV_ROOT_PATH = "Work Software"

    MOONTON_UNITY_HUB_APPLICATION_PATH = "C:/Unity Hub/Unity Hub.exe"

    UNITY_REMOTE_DIR_PATH = "Unity"

    SVN_WWISE_AUTHORING_PATH = "svn://jazmaybe.com/Wwise_Authoring/WwiseAuthoring"
    WWISE_AUTHORING_ROOT_DIR_PATH_WINDOWS = "C:/Wwise Authoring"

    _prepare_work_environment_signal = Signal()
    _install_unity_signal = Signal(list, dict)
    _install_wwise_authoring_signal = Signal(list)

    def __init__(self, main_window):
        super().__init__(main_window)
        self.work_environment_utility: WorkEnvironmentUtility | None = None
        self._unity_install_version_select_window: UnityInstallVersionSelectWindow | None = None
        self._wwise_authoring_install_version_select_window: Optional[WwiseAuthoringInstallVersionSelectWindow] = None

    def uninit(self):
        super().unit()

    def prepare_work_environment_action(self):
        self.work_environment_utility = WorkEnvironmentUtility(self)
        from windows_tools import installed_software
        installed_software_list = installed_software.get_installed_software()

        if not any("SmartSVN" in installed_software['name'] for installed_software in installed_software_list):
            dialog_content = "* 安装SmartSVN并配置\n"
        else:
            dialog_content = "* 配置SmartSVN\n"

        if not any("TortoiseSVN" in installed_software['name'] for installed_software in installed_software_list):
            dialog_content = f"{dialog_content}* 安装TortoiseSVN\n"

        if not any(installed_software['name'] == "Git" for installed_software in installed_software_list):
            dialog_content = f"{dialog_content}* 安装Git\n"

        if not any(".NET Framework 4.8.1" in installed_software['name'] for installed_software in installed_software_list):
            dialog_content = f"{dialog_content}* 安装.NET Framework 4.8.1\n"

        dialog_content = f"{dialog_content}* 安装VisualCppRedist AIO\n"

        if not any("Unity Hub" in installed_software['name'] for installed_software in installed_software_list):
            dialog_content = f"{dialog_content}* 安装官方版Unity Hub\n"

        if not os.path.isfile(WorkEnvironmentJob.MOONTON_UNITY_HUB_APPLICATION_PATH) or not config_utility.get_config("UnityHubInstalled") is True:
            dialog_content = f"{dialog_content}* 安装沐瞳版Unity Hub至\"C:/Unity Hub\"\n"

        if self._create_dialog("确定准备工作环境?", f"{dialog_content}如果存在SmartSVN或TortoiseSVN的任务正在进行, 请先中止任务并关闭所有SVN相关应用程序后进行"):
            self._prepare_work_environment_signal.connect(self.work_environment_utility.prepare_work_environment_job)
            self.work_environment_utility.refresh_title_bar_signal.connect(self.main_window.title_bar.refresh)
            self.work_environment_utility.moveToThread(self.worker_thread)
            self.start_worker()
            self._create_progress_ring_window()
            self._prepare_work_environment_signal.emit()

    def install_unity_action(self):
        self.work_environment_utility = WorkEnvironmentUtility(self)
        try:
            webdav_client = Client(self.WEBDAV_URL, (self.WEBDAV_USER, self.WEBDAV_PASSWORD))
            webdav_client.ls("/")
        except Exception as error:
            self.show_error_info_bar(f"连接WebDAV服务器发生异常:\n{error}")
            self.show_result_info_bar("error", "任务中止", "")
            return

        file_item_list = webdav_client.ls(f"{self.WEBDAV_ROOT_PATH}/{self.UNITY_REMOTE_DIR_PATH}")
        unity_version_info_dict = {}
        for file_item in file_item_list:
            file_item: dict
            version_name = pathlib.Path(file_item.get("name")).name
            is_directory = file_item.get("type") == "directory"
            file_name_lower = version_name.lower()
            if version_name.startswith(".") or file_name_lower == "unity hub" or file_name_lower == "unitylauncher" or not is_directory:
                continue
            unity_version_info_dict[version_name] = []
            unity_component_path_list = webdav_client.ls(f"{self.WEBDAV_ROOT_PATH}/{self.UNITY_REMOTE_DIR_PATH}/{version_name}/Windows", False)
            for unity_component_path in unity_component_path_list:
                unity_component_path: str
                file_name = pathlib.Path(unity_component_path).name
                file_name_lower = file_name.lower()
                if not file_name_lower.endswith(".exe"):
                    continue
                unity_version_info_dict[version_name].append(file_name)
            unity_version_info_dict[version_name].sort()

        if len(unity_version_info_dict) == 0:
            self.show_result_info_bar("warning", "任务中止", "没有在共享盘找到任何Unity版本")
            return

        self._show_unity_install_version_select_window_window(unity_version_info_dict)

    def install_unity_implement_action(self, version_list: list, version_info_dict: dict):
        self._install_unity_signal.connect(self.work_environment_utility.install_unity_job)
        self.work_environment_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._create_progress_bar_window()
        self._install_unity_signal.emit(version_list, version_info_dict)

    def install_wwise_authoring_action(self):
        self.work_environment_utility = WorkEnvironmentUtility(self)
        version_list = self.work_environment_utility.list_file(WorkEnvironmentJob.SVN_WWISE_AUTHORING_PATH, SVNUtility.JAZMAYBE_SVN_USER, SVNUtility.JAZMAYBE_SVN_PASSWORD, False)
        if version_list is None:
            self.job_finish("任务中止", "", "error")
            return
        elif len(version_list) == 0:
            self.job_finish("结果", f"未在音频仓库\"{WorkEnvironmentJob.SVN_WWISE_AUTHORING_PATH}\"中找到任何版本的Wwise设计工具.", "warning")
            return

        self._show_wwise_authoring_install_version_select_window_window(version_list)

    def _show_wwise_authoring_install_version_select_window_window(self, version_list: list[str]):
        if self._wwise_authoring_install_version_select_window:
            self._wwise_authoring_install_version_select_window.close()
            self._wwise_authoring_install_version_select_window.deleteLater()
            self._wwise_authoring_install_version_select_window = None
        self._wwise_authoring_install_version_select_window = WwiseAuthoringInstallVersionSelectWindow(version_list)
        self._wwise_authoring_install_version_select_window.confirm_signal.connect(self.install_wwise_authoring_implement_action)
        self._wwise_authoring_install_version_select_window.window_closed_signal.connect(self._on_install_version_select_window_closed)

    def install_wwise_authoring_implement_action(self, version_list: list[str]):
        self._install_wwise_authoring_signal.connect(self.work_environment_utility.install_wwise_authoring_job)
        self.work_environment_utility.add_wwise_authoring_signal.connect(self.main_window.setting_interface.add_wwise_authoring_path)
        self.work_environment_utility.moveToThread(self.worker_thread)
        self.start_worker()
        self._create_progress_bar_window()
        self._install_wwise_authoring_signal.emit(version_list)

    def _create_progress_bar_window(self):
        self._progress_bar_window: ProgressBarWindow = ProgressBarWindow(self.main_window)
        self._progress_bar_window.cancel_signal.connect(lambda: self.work_environment_utility.notice_cancel_job())

        self.work_environment_utility.update_progress_text_signal.connect(self._progress_bar_window.set_text)
        self.work_environment_utility.update_progress_total_count_signal.connect(self._progress_bar_window.set_total_count)
        self.work_environment_utility.update_progress_current_count_signal.connect(self._progress_bar_window.set_current_count)

    def _create_progress_ring_window(self):
        self._progress_ring_window: ProgressRingWindow = ProgressRingWindow(self.main_window)
        self._progress_ring_window.cancel_signal.connect(lambda: self.work_environment_utility.notice_cancel_job())

        self.work_environment_utility.update_progress_text_signal.connect(self._progress_ring_window.set_text)

    def _show_unity_install_version_select_window_window(self, version_info_dict: dict):
        if self._unity_install_version_select_window:
            self._unity_install_version_select_window.close()
            self._unity_install_version_select_window.deleteLater()
            self._unity_install_version_select_window = None
        self._unity_install_version_select_window = UnityInstallVersionSelectWindow(version_info_dict)
        self._unity_install_version_select_window.confirm_signal.connect(self.install_unity_implement_action)
        self._unity_install_version_select_window.window_closed_signal.connect(self._on_install_version_select_window_closed)

    def _on_install_version_select_window_closed(self):
        if self._unity_install_version_select_window:
            self._unity_install_version_select_window.deleteLater()
            self._unity_install_version_select_window = None

        if self._wwise_authoring_install_version_select_window:
            self._wwise_authoring_install_version_select_window.deleteLater()
            self._wwise_authoring_install_version_select_window = None

    def job_finish(self, title: str, content: str, result: str):
        if self.work_environment_utility:
            self.work_environment_utility.deleteLater()
            self.work_environment_utility = None
        super().job_finish(title, content, result)
