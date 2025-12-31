# noinspection PyPackageRequirements
import json
import os
import pathlib
import shutil
import stat
import subprocess
import zipfile

from PySide6.QtCore import Signal

import main
import send2trash
from main import ROOT_PATH
from ruamel.yaml import CommentedMap, CommentedSeq, YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, SingleQuotedScalarString
from Source.Utility.config_utility import config_utility
from Source.Utility.file_utility import FileUtility
from Source.Utility.svn_utility import SVNUtility
from webdav4.client import Client


class WorkEnvironmentUtility(FileUtility, SVNUtility):
    SMART_SVN_REMOTE_DIR_PATH = "SmartSVN"
    TORTOISE_SVN_REMOTE_DIR_PATH = "TortoiseSVN"
    GIT_REMOTE_DIR_PATH = "Git"
    DOT_NET_FRAMEWORK_REMOTE_DIR_PATH = ".NET Framework"
    VISUAL_CPP_REDIST_AIO_REMOTE_DIR_PATH = "VisualCppRedist AIO"
    UNITY_HUB_REMOTE_DIR_PATH = "Unity/Unity Hub/Windows"
    MOONTON_UNITY_HUB_LOCAL_DIR_PATH = "C:/Unity Hub"

    UNITY_ENGINE_INSTALL_ROOT_DIR_PATH = "C:/Program Files"
    SMART_SVN_LATEST_VERSION = "14.4"

    # 信号定义
    refresh_title_bar_signal = Signal()
    add_wwise_authoring_signal = Signal()

    def __init__(self, work_environment_job):
        from Source.Job.work_environment_job import WorkEnvironmentJob
        work_environment_job: WorkEnvironmentJob
        self._work_environment_job = work_environment_job
        super().__init__(work_environment_job)

    def prepare_work_environment_job(self):
        self._config_smartsvn()

        self.update_progress_text_signal.emit(f"连接WebDAV服务器\"{self._work_environment_job.WEBDAV_URL}\"...")
        try:
            webdav_client = Client(self._work_environment_job.WEBDAV_URL, (self._work_environment_job.WEBDAV_USER, self._work_environment_job.WEBDAV_PASSWORD))
            webdav_client.ls("/")
        except Exception as error:
            self.error_signal.emit(f"连接WebDAV服务器发生异常:\n{error}")
            self.finish_signal.emit("任务中止", "", "error")
            return

        from windows_tools import installed_software
        installed_software_list = installed_software.get_installed_software()

        # 安装SmartSVN
        if not any("SmartSVN" in installed_software['name'] for installed_software in installed_software_list):
            file_path_list = webdav_client.ls(f"{self._work_environment_job.WEBDAV_ROOT_PATH}/{self.SMART_SVN_REMOTE_DIR_PATH}/Windows", False)
            installer_remote_path = ""
            installer_file_name = ""
            for file_path in file_path_list:
                file_path: str
                file_name = pathlib.Path(file_path).name
                file_name_lower = file_name.lower()
                if file_name_lower.endswith(".exe"):
                    installer_remote_path = file_path
                    installer_file_name = file_name
                    break

            self.update_progress_text_signal.emit(f"获取文件...\n{installer_file_name}\"")
            installer_file_local_path = f"{ROOT_PATH}/{installer_file_name}"
            try:
                webdav_client.download_file(installer_remote_path, installer_file_local_path)
            except Exception as error:
                self.delete_file(installer_file_local_path)
                self.error_signal.emit(f"获取\"{installer_file_name}\"发生异常:\n{error}")
                self.finish_signal.emit("任务中止", "", "error")
                return

            self.update_progress_text_signal.emit(f"安装SmartSVN...\n{installer_file_local_path}")
            process = subprocess.run([installer_file_local_path, "/SP-", "/VERYSILENT", "/ALLUSERS", "/NOCANCEL", "NORESTART", "/CLOSEAPPLICATIONS", "/TASKS=\"explorerintegration\""],
                                     capture_output=True)
            if process.returncode != 0:
                self.delete_file(installer_file_local_path)
                self.error_signal.emit(f'安装\"{installer_file_local_path}\"失败"\n{process.stderr.decode().strip()}')
                self.finish_signal.emit("任务中止", "", "error")
                return
            self.delete_file(installer_file_local_path)

        # 安装TortoiseSVN
        if not any("TortoiseSVN" in installed_software['name'] for installed_software in installed_software_list):
            file_path_list = webdav_client.ls(f"{self._work_environment_job.WEBDAV_ROOT_PATH}/{self.TORTOISE_SVN_REMOTE_DIR_PATH}", False)
            installer_remote_path_list = []

            for file_path in file_path_list:
                file_path: str
                file_name = pathlib.Path(file_path).name
                file_name_lower = file_name.lower()
                if not file_name_lower.endswith(".msi"):
                    continue
                installer_remote_path = file_path
                installer_remote_path_list.append(installer_remote_path)

            installer_remote_path_list.sort(reverse=True)

            for installer_remote_path in installer_remote_path_list:
                installer_file_name = pathlib.Path(installer_remote_path).name
                self.update_progress_text_signal.emit(f"获取文件...\n{installer_file_name}\"")
                installer_file_local_path = f"{ROOT_PATH}/{installer_file_name}"
                try:
                    webdav_client.download_file(installer_remote_path, installer_file_local_path)
                except Exception as error:
                    self.delete_file(installer_file_local_path)
                    self.error_signal.emit(f"获取\"{installer_file_name}\"发生异常:\n{error}")
                    self.finish_signal.emit("任务中止", "", "error")
                    return

                self.update_progress_text_signal.emit(f"安装Tortoise...\n{installer_file_local_path}")
                process = subprocess.run(["msiexec", "/i", installer_file_local_path.replace("/", "\\"), "/passive", "/norestart", "ADDLOCAL=ALL"], capture_output=True)
                if process.returncode != 0:
                    self.delete_file(installer_file_local_path)
                    self.error_signal.emit(f'安装\"{installer_file_local_path}\"失败"\n{process.stderr.decode().strip()}')
                    self.finish_signal.emit("任务中止", "", "error")
                    return
                self.delete_file(installer_file_local_path)

        # 安装Git
        if not any(installed_software['name'] == "Git" for installed_software in installed_software_list):
            file_path_list = webdav_client.ls(f"{self._work_environment_job.WEBDAV_ROOT_PATH}/{self.GIT_REMOTE_DIR_PATH}", False)
            installer_remote_path = ""
            installer_file_name = ""
            for file_path in file_path_list:
                file_path: str
                file_name = pathlib.Path(file_path).name
                file_name_lower = file_name.lower()
                if file_name_lower.endswith(".exe"):
                    installer_remote_path = file_path
                    installer_file_name = file_name
                    break

            self.update_progress_text_signal.emit(f"获取文件...\n{installer_file_name}\"")
            installer_file_local_path = f"{ROOT_PATH}/{installer_file_name}"
            try:
                webdav_client.download_file(installer_remote_path, installer_file_local_path)
            except Exception as error:
                self.delete_file(installer_file_local_path)
                self.error_signal.emit(f"获取\"{installer_file_name}\"发生异常:\n{error}")
                self.finish_signal.emit("任务中止", "", "error")
                return

            self.update_progress_text_signal.emit(f"安装Git...\n{installer_file_local_path}")
            process = subprocess.run([installer_file_local_path, "/SP-", "/VERYSILENT", "/ALLUSERS", "/NOCANCEL", "NORESTART", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS",
                                      "/COMPONENTS=\"icons,ext\reg\shellhere,assoc,assoc_sh\""], capture_output=True)
            if process.returncode != 0:
                self.delete_file(installer_file_local_path)
                self.error_signal.emit(f'安装\"{installer_file_local_path}\"失败"\n{process.stderr.decode().strip()}')
                self.finish_signal.emit("任务中止", "", "error")
                return
            self.delete_file(installer_file_local_path)

        # 安装.NET Framework
        if not any(".NET Framework 4.8.1" in installed_software['name'] for installed_software in installed_software_list):
            file_path_list = webdav_client.ls(f"{self._work_environment_job.WEBDAV_ROOT_PATH}/{self.DOT_NET_FRAMEWORK_REMOTE_DIR_PATH}", False)
            installer_remote_path = ""
            installer_file_name = ""
            for file_path in file_path_list:
                file_path: str
                file_name = pathlib.Path(file_path).name
                file_name_lower = file_name.lower()
                if file_name_lower.endswith(".exe"):
                    installer_remote_path = file_path
                    installer_file_name = file_name
                    break

            self.update_progress_text_signal.emit(f"获取文件...\n{installer_file_name}\"")
            installer_file_local_path = f"{ROOT_PATH}/{installer_file_name}"
            try:
                webdav_client.download_file(installer_remote_path, installer_file_local_path)
            except Exception as error:
                self.delete_file(installer_file_local_path)
                self.error_signal.emit(f"获取\"{installer_file_name}\"发生异常:\n{error}")
                self.finish_signal.emit("任务中止", "", "error")
                return

            self.update_progress_text_signal.emit(f"安装.NET Framework...\n{installer_file_local_path}")
            process = subprocess.run([installer_file_local_path, "/norestart", "/pipe", "/q"], capture_output=True)
            if process.returncode != 0:
                self.delete_file(installer_file_local_path)
                self.error_signal.emit(f'安装\"{installer_file_local_path}\"失败"\n{process.stderr.decode().strip()}')
                self.finish_signal.emit("任务中止", "", "error")
                return
            self.delete_file(installer_file_local_path)

        # 安装VisualCppRedist AIO
        file_path_list = webdav_client.ls(f"{self._work_environment_job.WEBDAV_ROOT_PATH}/{self.VISUAL_CPP_REDIST_AIO_REMOTE_DIR_PATH}", False)
        installer_remote_path = ""
        installer_file_name = ""
        for file_path in file_path_list:
            file_path: str
            file_name = pathlib.Path(file_path).name
            file_name_lower = file_name.lower()
            if file_name_lower.endswith(".exe"):
                installer_remote_path = file_path
                installer_file_name = file_name
                break

        self.update_progress_text_signal.emit(f"获取文件...\n{installer_file_name}\"")
        installer_file_local_path = f"{ROOT_PATH}/{installer_file_name}"
        try:
            webdav_client.download_file(installer_remote_path, installer_file_local_path)
        except Exception as error:
            self.delete_file(installer_file_local_path)
            self.error_signal.emit(f"获取\"{installer_file_name}\"发生异常:\n{error}")
            self.finish_signal.emit("任务中止", "", "error")
            return

        self.update_progress_text_signal.emit(f"安装VisualCppRedist AIO...\n{installer_file_local_path}")
        try:
            subprocess.Popen([installer_file_local_path, "/ai"], stderr=subprocess.PIPE, shell=True)
        except Exception as error:
            self.delete_file(installer_file_local_path)
            self.error_signal.emit(f"安装\"{installer_file_name}\"发生异常:\n{error}")
            self.finish_signal.emit("任务中止", "", "error")
            return
        self.delete_file(installer_file_local_path)

        # 安装官方版Unity Hub
        if not any("Unity Hub" in installed_software['name'] for installed_software in installed_software_list):
            file_path_list = webdav_client.ls(f"{self._work_environment_job.WEBDAV_ROOT_PATH}/{self.UNITY_HUB_REMOTE_DIR_PATH}", False)
            installer_remote_path = ""
            installer_file_name = ""
            for file_path in file_path_list:
                file_path: str
                file_name = pathlib.Path(file_path).name
                file_name_lower = file_name.lower()
                if file_name_lower.endswith(".exe"):
                    installer_remote_path = file_path
                    installer_file_name = file_name
                    break

            self.update_progress_text_signal.emit(f"获取文件...\n{installer_file_name}\"")
            installer_file_local_path = f"{ROOT_PATH}/{installer_file_name}"
            try:
                webdav_client.download_file(installer_remote_path, installer_file_local_path)
            except Exception as error:
                self.delete_file(installer_file_local_path)
                self.error_signal.emit(f"获取\"{installer_file_name}\"发生异常:\n{error}")
                self.finish_signal.emit("任务中止", "", "error")
                return

            self.update_progress_text_signal.emit(f"安装官方版Unity Hub...\n{installer_file_local_path}")
            process = subprocess.run([installer_file_local_path, "/S"], capture_output=True, shell=True)
            if process.returncode != 0:
                self.delete_file(installer_file_local_path)
                self.error_signal.emit(f'安装\"{installer_file_local_path}\"失败"\n{process.stderr.decode().strip()}')
                self.finish_signal.emit("任务中止", "", "error")
                return
            self.delete_file(installer_file_local_path)

        # 安装沐瞳版Unity Hub
        if not os.path.isfile(self._work_environment_job.MOONTON_UNITY_HUB_APPLICATION_PATH) or not config_utility.get_config("UnityHubInstalled") is True:
            file_path_list = webdav_client.ls(f"{self._work_environment_job.WEBDAV_ROOT_PATH}/{self.UNITY_HUB_REMOTE_DIR_PATH}", False)
            installer_remote_path = ""
            installer_file_name = ""
            for file_path in file_path_list:
                file_path: str
                file_name = pathlib.Path(file_path).name
                file_name_lower = file_name.lower()
                if file_name_lower.endswith(".zip"):
                    installer_remote_path = file_path
                    installer_file_name = file_name
                    break

            self.update_progress_text_signal.emit(f"获取文件...\n{installer_file_name}\"")
            installer_file_local_path = f"{ROOT_PATH}/{installer_file_name}"
            try:
                webdav_client.download_file(installer_remote_path, installer_file_local_path)
            except Exception as error:
                self.delete_file(installer_file_local_path)
                self.error_signal.emit(f"获取\"{installer_file_name}\"发生异常:\n{error}")
                self.finish_signal.emit("任务中止", "", "error")
                return

            self.update_progress_text_signal.emit(f"安装沐瞳版Unity Hub...\n{installer_file_local_path}")
            if os.path.exists(self.MOONTON_UNITY_HUB_LOCAL_DIR_PATH):
                send2trash.send2trash(self.MOONTON_UNITY_HUB_LOCAL_DIR_PATH.replace("/", "\\"))
            try:
                with zipfile.ZipFile(installer_file_local_path) as zip_re:
                    zip_re.extractall(self.MOONTON_UNITY_HUB_LOCAL_DIR_PATH)
            except Exception as error:
                self.delete_file(installer_file_local_path)
                self.error_signal.emit(f"解压缩沐瞳版Unity Hub发生异常:\n{error}")
                self.finish_signal.emit("任务中止", "", "error")
                return
            self.delete_file(installer_file_local_path)
            config_utility.set_config("UnityHubInstalled", True)
            self.refresh_title_bar_signal.emit()

        self.finish_signal.emit("结果", "工作环境准备完成.", "success")

    def _config_smartsvn(self):
        # 对SmartSVN进行配置
        self.update_progress_text_signal.emit("配置SmartSVN...")
        if main.is_windows_os():
            appdata_path = os.getenv("APPDATA").replace("\\", "/")
        else:
            appdata_path = f"{os.path.expanduser('~')}/Library/Preferences"
        smartsvn_config_dir_root_path = f"{appdata_path}/SmartSVN"
        if not self.create_directory(smartsvn_config_dir_root_path):
            self.finish_signal.emit("任务中止", "", "error")
            return
        try:
            vmoptions_file_path = f"{smartsvn_config_dir_root_path}/smartsvn.vmoptions"
            vmoptions_file = open(vmoptions_file_path, "w")
            vmoptions_file.write("-Xmx2048m")
            vmoptions_file.close()
        except Exception as error:
            self.error_signal.emit(f"配置\"smartsvn.vmoptions\"发生异常:\n{error}")
            self.finish_signal.emit("任务中止", "", "error")
            return

        if not self.create_directory(f"{smartsvn_config_dir_root_path}/{self.SMART_SVN_LATEST_VERSION}"):
            self.finish_signal.emit("任务中止", "", "error")
            return

        scan_dir_iterator = os.scandir(smartsvn_config_dir_root_path)
        for dir_entry in scan_dir_iterator:
            dir_entry: os.DirEntry
            if not dir_entry.is_dir():
                continue

            smartsvn_config_dir_path = dir_entry.path.replace("\\", "/")
            yaml_object = {}

            yaml = YAML()
            yaml.preserve_quotes = True
            yaml.default_flow_style = False
            smartsvn_preferences_yaml_path = f"{smartsvn_config_dir_path}/preferences.yml"

            if os.path.isfile(smartsvn_preferences_yaml_path):
                yaml_object = yaml.load(pathlib.Path(smartsvn_preferences_yaml_path))
                if not yaml_object:
                    yaml_object = {}

            action_object = self._get_child_commented_map(yaml_object, "action")
            commit_object = self._get_child_commented_map(action_object, "commit", True)
            refresh_object = self._get_child_commented_map(action_object, "refresh", True)

            commit_object["addUnversionedFiles"] = False
            commit_object["detectMoves"] = False
            commit_object["missedCheck"] = "off"
            commit_object["removeMissingFiles"] = False
            commit_object["removeRemovedParentDirectories"] = False
            commit_object["skipChangeSetOrChangelistEntries"] = True
            commit_object["warnForCaseChangedFiles"] = False

            refresh_object["backgroundRefreshing"] = True
            refresh_object["remoteStateRefreshWithLocalRefresh"] = False
            refresh_object["type"] = "selected-view"

            date_format_object = self._get_child_commented_map(yaml_object, "dateFormat", True)
            date_format_object["datePattern"] = "yyyy-MM-dd"
            date_format_object["showTimeForLastDays"] = False
            date_format_object["timePattern"] = SingleQuotedScalarString("HH:mm")

            project_object = self._get_child_commented_map(yaml_object, "project", True)
            project_object["askForClose"] = False
            project_object["openProjectAskDirectoryShortcut"] = False
            project_object["openProjectInNewWindow"] = True

            startup_object = self._get_child_commented_map(yaml_object, "startup", True)
            startup_object["startupMode"] = "show-welcome-dialog"

            yaml.dump(yaml_object, pathlib.Path(smartsvn_preferences_yaml_path))

            yaml_object = {}
            smartsvn_project_defaults_yaml_path = f"{smartsvn_config_dir_path}/project-defaults.yml"
            if os.path.isfile(smartsvn_project_defaults_yaml_path):
                yaml_object = yaml.load(pathlib.Path(smartsvn_project_defaults_yaml_path))
                if not yaml_object:
                    yaml_object = {}

            action_settings_object = self._get_child_commented_map(yaml_object, "actionSettings")

            refresh_settings_object = self._get_child_commented_map(action_settings_object, "refreshSettings", True)
            refresh_settings_object["scanRootOnly"] = False

            working_copy_settings_object = self._get_child_commented_map(action_settings_object, "workingCopySettings")
            working_copy_settings_object["globalIgnoreOption"] = "off"
            working_copy_settings_object["globalIgnorePatterns"] = SingleQuotedScalarString("")
            working_copy_settings_object["eolStyle"] = "as-is"

            text_file_settings_object = self._get_child_commented_map(yaml_object, "textFileSettings", True)
            text_file_settings_object["encoding"] = "UTF-8"

            yaml.dump(yaml_object, pathlib.Path(smartsvn_project_defaults_yaml_path))

            yaml_object = {}
            smartsvn_projects_yaml_path = f"{smartsvn_config_dir_path}/projects.yml"
            if os.path.isfile(smartsvn_projects_yaml_path):
                with open(smartsvn_projects_yaml_path, encoding="utf-8") as yaml_file:
                    yaml_object = yaml.load(yaml_file)
                if not yaml_object:
                    yaml_object = {}

            tree_object = self._get_child_commented_map(yaml_object, "tree")
            root_nodes_object = CommentedSeq() if tree_object.get("nodes") is None else tree_object["nodes"]

            def set_workcopy_config_recursively(nodes_commented_seq: CommentedSeq):
                for commented_map in nodes_commented_seq:
                    if not isinstance(commented_map, CommentedMap):
                        continue
                    commented_map: CommentedMap
                    if "project" in commented_map.keys():
                        project_map = commented_map["project"]
                        file_filter_map = self._get_child_commented_map(project_map, "fileFilter", True)
                        file_filter_map["viewAssignedToChangeSet"] = False
                        file_filter_map["viewRemoteChanged2"] = False
                        settings_map = self._get_child_commented_map(project_map, "settings")
                        text_file_settings_map = self._get_child_commented_map(project_map, "textFileSettings", True)
                        text_file_settings_map["encoding"] = "UTF-8"
                        action_settings_map = self._get_child_commented_map(settings_map, "actionSettings")
                        refresh_settings_map = self._get_child_commented_map(action_settings_map, "refreshSettings", True)
                        refresh_settings_map["scanRootOnly"] = False
                        working_copy_settings_map = self._get_child_commented_map(action_settings_map, "workingCopySettings")
                        working_copy_settings_map["eolStyle"] = "as-is"
                        working_copy_settings_map["globalIgnoreOption"] = "off"
                        working_copy_settings_map["globalIgnorePatterns"] = SingleQuotedScalarString("")
                        ui_settings_map = self._get_child_commented_map(settings_map, "uiSettings")
                        main_frame_file_table_map = self._get_child_commented_map(ui_settings_map, "mainFrameFileTable")
                        main_frame_file_table_map["visibleColumnNames"] = DoubleQuotedScalarString('Ext.\tLocal State\tName\tRelative Directory')
                        transaction_settings_map = self._get_child_commented_map(settings_map, "transactionSettings")
                        display_settings_map = self._get_child_commented_map(transaction_settings_map, "displaySettings", True)
                        display_settings_map["layoutId"] = "transaction-layout-raw"
                    elif "nodes" in commented_map.keys():
                        set_workcopy_config_recursively(commented_map["nodes"])

            set_workcopy_config_recursively(root_nodes_object)

            with open(smartsvn_projects_yaml_path, "w", encoding="utf-8") as yaml_file:
                yaml.dump(yaml_object, yaml_file)

    @staticmethod
    def _get_child_commented_map(commented_map_object: CommentedMap, key: str, set_flow_style=False) -> CommentedMap:
        commented_map_object[key] = CommentedMap() if commented_map_object.get(key) is None else commented_map_object[key]
        if set_flow_style:
            commented_map_object[key].fa.set_flow_style()
        else:
            commented_map_object[key].fa.set_block_style()
        return commented_map_object[key]

    def install_unity_job(self, install_version_list: list[str], unity_version_info_dict: dict):
        self.update_progress_text_signal.emit(f"连接WebDAV服务器\"{self._work_environment_job.WEBDAV_URL}\"...")
        try:
            webdav_client = Client(self._work_environment_job.WEBDAV_URL, (self._work_environment_job.WEBDAV_USER, self._work_environment_job.WEBDAV_PASSWORD))
            webdav_client.ls("/")
        except Exception as error:
            self.error_signal.emit(f"连接WebDAV服务器发生异常:\n{error}")
            self.finish_signal.emit("任务中止", "", "error")
            return

        total_installer_count = 0
        for install_version in install_version_list:
            total_installer_count += len(unity_version_info_dict.get(install_version, []))
        self.update_progress_current_count_signal.emit(0)
        self.update_progress_total_count_signal.emit(total_installer_count)

        current_install_count = 0
        for install_version in install_version_list:
            unity_install_dir_path = f"{self.UNITY_ENGINE_INSTALL_ROOT_DIR_PATH}/Unity {install_version}"
            # 需要先安装本体, 再安装操作系统支持组件
            installer_file_name_list = []
            for installer_file_name in unity_version_info_dict.get(install_version, []):
                if "unitysetup64" in installer_file_name.lower():
                    installer_file_name_list.append(installer_file_name)
                    break
            for installer_file_name in unity_version_info_dict.get(install_version, []):
                if "unitysetup64" in installer_file_name.lower():
                    continue
                installer_file_name_list.append(installer_file_name)

            for installer_file_name in installer_file_name_list:
                unity_component_installer_remote_path = f"{self._work_environment_job.WEBDAV_ROOT_PATH}/{self._work_environment_job.UNITY_REMOTE_DIR_PATH}/{install_version}/Windows/{installer_file_name}"
                self.update_progress_text_signal.emit(f"安装Unity {install_version}至\"{unity_install_dir_path}\"...\n获取\"{installer_file_name}\"...")
                unity_component_installer_local_path = f"{ROOT_PATH}/{installer_file_name}"
                try:
                    webdav_client.download_file(unity_component_installer_remote_path, unity_component_installer_local_path)
                except Exception as error:
                    self.delete_file(unity_component_installer_local_path)
                    self.error_signal.emit(f"获取\"{unity_component_installer_remote_path}\"发生异常:\n{error}")
                    self.finish_signal.emit("任务中止", "", "error")
                    return

                if self.cancel_job:
                    self.delete_file(unity_component_installer_local_path)
                    self.finish_signal.emit("任务中止", "", "warning")
                    return

                self.update_progress_text_signal.emit(f"安装Unity {install_version}至\"{unity_install_dir_path}\"...\n安装\"{installer_file_name}\"...")
                unity_install_dir_path_windows = unity_install_dir_path.replace("/", "\\")
                process = subprocess.run([unity_component_installer_local_path, "/S", f"/D={unity_install_dir_path_windows}"], capture_output=True, shell=True)
                if process.returncode != 0:
                    self.delete_file(unity_component_installer_local_path)
                    self.error_signal.emit(f'安装\"{installer_file_name}\"失败":\n{process.stderr.decode().strip()}')
                    self.finish_signal.emit("任务中止", "", "error")
                    return

                current_install_count += 1
                self.update_progress_current_count_signal.emit(current_install_count)
                self.delete_file(unity_component_installer_local_path)

                if self.cancel_job:
                    self.finish_signal.emit("任务中止", "", "warning")
                    return

            # 添加到Unity Hub中
            unity_exe_path = f"{unity_install_dir_path}/Editor/Unity.exe".replace("/", "\\")
            appdata_path = os.getenv("APPDATA").replace("\\", "/")
            editors_json_path = f"{appdata_path}/UnityHub/editors.json"
            unity_editor_list_dict: dict = {}
            if not os.path.isfile(editors_json_path):
                os.makedirs(os.path.dirname(editors_json_path), exist_ok=True)
                json_object = json.dumps(unity_editor_list_dict, indent=4)
                with open(editors_json_path, "w", encoding="utf-8") as json_file:
                    json_file.write(json_object)

            with open(editors_json_path, encoding="utf-8") as json_file:
                unity_editor_list_dict = json.load(json_file)

            is_existed = False
            for _, version_info in unity_editor_list_dict.items():
                if version_info["location"][0] != unity_exe_path:
                    continue
                is_existed = True

            if not is_existed:
                import uuid
                version_id = str(uuid.uuid4())
                while id in unity_editor_list_dict.keys():
                    version_id = str(uuid.uuid4())
                unity_editor_list_dict[version_id] = {
                    "version":  install_version,
                    "location": [unity_exe_path],
                    "manual":   True
                }

            json_object = json.dumps(unity_editor_list_dict, indent=4)
            with open(editors_json_path, "w", encoding="utf-8") as json_file:
                json_file.write(json_object)

        self.finish_signal.emit("结果", "Unity安装完成.", "success")

    def install_wwise_authoring_job(self, version_list: list[str]):
        svn_wwise_authoring_path = self._work_environment_job.SVN_WWISE_AUTHORING_PATH
        wwise_authoring_root_dir_path_windows = self._work_environment_job.WWISE_AUTHORING_ROOT_DIR_PATH_WINDOWS
        self.create_directory(wwise_authoring_root_dir_path_windows)
        if not self.check_dir_is_workcopy(wwise_authoring_root_dir_path_windows) or self.get_repository_url(wwise_authoring_root_dir_path_windows) != svn_wwise_authoring_path:
            if os.path.isdir(wwise_authoring_root_dir_path_windows):
                def remove_readonly(func, target_path, _):
                    os.chmod(target_path, stat.S_IWRITE)
                    func(target_path)

                shutil.rmtree(wwise_authoring_root_dir_path_windows, onerror=remove_readonly)
            for path in self.checkout_repository(svn_wwise_authoring_path, wwise_authoring_root_dir_path_windows, SVNUtility.JAZMAYBE_SVN_USER, SVNUtility.JAZMAYBE_SVN_PASSWORD, "immediates"):
                if path is None:
                    self.finish_signal.emit("任务中止", "", "error")
                    return

        for version in version_list:
            wwise_authoring_remote_path = f"{svn_wwise_authoring_path}/{version}/Windows"
            wwise_authoring_local_version_path = f"{wwise_authoring_root_dir_path_windows}/{version}"
            wwise_authoring_local_path = f"{wwise_authoring_local_version_path}/Windows"
            self.update_progress_text_signal.emit(f"检出\"{svn_wwise_authoring_path}\"\n至\"{wwise_authoring_root_dir_path_windows}\"...\n平台: \"Windows\"; 版本: \"{version}\"")
            self.update_progress_total_count_signal.emit(0)
            self.update_progress_current_count_signal.emit(0)
            self.cleanup_repository(wwise_authoring_root_dir_path_windows, SVNUtility.JAZMAYBE_SVN_USER, SVNUtility.JAZMAYBE_SVN_PASSWORD)

            file_count = self.get_repository_file_count(wwise_authoring_remote_path, SVNUtility.JAZMAYBE_SVN_USER, SVNUtility.JAZMAYBE_SVN_PASSWORD, 30)
            if file_count >= 0:
                self.update_progress_total_count_signal.emit(file_count)

            current_file_count = 0
            self.update_repository(wwise_authoring_local_version_path, SVNUtility.JAZMAYBE_SVN_USER, SVNUtility.JAZMAYBE_SVN_PASSWORD, "immediates")

            for path in self.update_repository(wwise_authoring_local_path, SVNUtility.JAZMAYBE_SVN_USER, SVNUtility.JAZMAYBE_SVN_PASSWORD):
                if self.cancel_job:
                    self.cleanup_repository(wwise_authoring_root_dir_path_windows, SVNUtility.JAZMAYBE_SVN_USER, SVNUtility.JAZMAYBE_SVN_PASSWORD)
                    self.finish_signal.emit("任务中止", "", "warning")
                    return
                if path is None:
                    continue  # self.finish_signal.emit("任务中止", "", "error")
                elif path.startswith("At revision"):
                    self.update_progress_current_count_signal.emit(file_count)
                elif any(path.startswith(action) for action in self.SVN_FILE_ACTION_CHARACTER_LIST):
                    current_file_count += 1
                    self.update_progress_current_count_signal.emit(current_file_count)

        self.add_wwise_authoring_signal.emit()
        self.finish_signal.emit("结果", "Wwise设计工具安装完成.", "success")
