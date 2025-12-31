import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QFile, QStandardPaths

import main


class ProjectData:
    TITLE_CONFIG_NAME = "Title"
    WWISE_PROJECT_PATH = "WwiseProjectPath"
    UNITY_WWISE_BANK_PATH = "UnityWwiseBankPath"
    LANGUAGE_CHECK_DICT = "LanguageCheckDict"


class ConfigUtility:
    WWISE_AUTHORING_LIST_CONFIG_NAME = "WwiseAuthoringList"

    _CONFIG_FILE_NAME = "Config.json"
    _PROJECT_DATA_DICT_CONFIG_NAME = "ProjectDataDict"

    def __init__(self):
        self.config_data: {} = {}
        self.config_file_path: str = ""
        app_config_location = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.AppConfigLocation)
        if isinstance(app_config_location, list):
            app_config_location = app_config_location[0]
        self.config_file_path = f"{app_config_location}/{ConfigUtility._CONFIG_FILE_NAME}"
        Path(app_config_location).mkdir(parents=True, exist_ok=True)
        self._read_config_data()

    def get_project_data_dict(self) -> dict[str, dict[str, str]]:
        """
        获取项目数据字典
        :return: 项目数据字段
        :rtype: {项目ID: {属性 : 属性值}}
        """
        if ConfigUtility._PROJECT_DATA_DICT_CONFIG_NAME not in self.config_data.keys():
            self.config_data[ConfigUtility._PROJECT_DATA_DICT_CONFIG_NAME] = {}
        return self.config_data[ConfigUtility._PROJECT_DATA_DICT_CONFIG_NAME]

    def get_project_data(self, project_id: str) -> dict[str, str] | None:
        project_data_dict: dict[str, dict[str, str]] = self.get_project_data_dict()
        return project_data_dict.get(project_id)

    def get_project_language_check_dict_config(self, project_id: str) -> dict[str, bool] | None:
        project_data: dict = self.get_project_data(project_id)
        if project_data:
            language_check_dict: [str, bool] = project_data.get(ProjectData.LANGUAGE_CHECK_DICT)
            return language_check_dict
        else:
            return None

    def add_project_data(self, project_id: str, project_title: str) -> bool:
        if not project_id:
            self._print_log_error("无法添加项目数据, 项目ID为空.")
            return False
        if not project_title:
            self._print_log_error("无法添加项目数据, 项目名称为空.")
            return False
        project_data_dict: dict[str, dict[str, str]] = self.get_project_data_dict()
        if project_id not in project_data_dict:
            self.config_data[ConfigUtility._PROJECT_DATA_DICT_CONFIG_NAME][project_id] = {
                ProjectData.TITLE_CONFIG_NAME: project_title
            }
        else:
            self.config_data[ConfigUtility._PROJECT_DATA_DICT_CONFIG_NAME][project_id][ProjectData.TITLE_CONFIG_NAME] = project_title
        return self._write_config_data()

    def set_project_data_config(self, project_id: str, config_name: str, config_value: str) -> bool:
        if not project_id:
            self._print_log_error("无法设置项目数据, 项目ID为空.")
            return False
        if not config_name:
            self._print_log_error("无法设置项目数据, 设置名称为空.")
            return False
        project_data: dict[str, str] = self.get_project_data(project_id)
        if not project_data:
            self._print_log_error(f"无法设置项目数据, 项目ID\"{project_id}\"数据不存在.")
            return False
        self.config_data[ConfigUtility._PROJECT_DATA_DICT_CONFIG_NAME][project_id][config_name] = config_value
        return self._write_config_data()

    def set_project_language_check_dict_config(self, project_id: str, language_check_dict: {
        str: bool
    }) -> bool:
        if not project_id:
            self._print_log_error("无法设置项目语言勾选字典数据, 项目ID为空.")
            return False
        if not language_check_dict:
            self._print_log_error("无法设置项目语言勾选字典数据, 语言勾选字典数据为空.")
            return False
        project_data: dict[str, str] = self.get_project_data(project_id)
        if not project_data:
            self._print_log_error(f"无法设置项目语言勾选字典数据, 项目ID\"{project_id}\"数据不存在.")
            return False
        self.config_data[ConfigUtility._PROJECT_DATA_DICT_CONFIG_NAME][project_id][ProjectData.LANGUAGE_CHECK_DICT] = language_check_dict
        return self._write_config_data()

    def swap_project_data(self, index1: int, index2: int):
        project_data_count: int = len(self.get_project_data_dict())
        if index1 == index2 or index1 >= project_data_count or index2 >= project_data_count:
            return
        project_data_list: list = list(self.get_project_data_dict().items())
        project_data_list[index1], project_data_list[index2] = project_data_list[index2], project_data_list[index1]
        self.config_data[ConfigUtility._PROJECT_DATA_DICT_CONFIG_NAME] = dict(project_data_list)
        self._write_config_data()

    def remove_project_data(self, project_id: str) -> bool:
        if not project_id:
            self._print_log_error("无法删除项目数据, 项目ID为空.")
            return False
        project_data_dict: dict[str, dict[str, str]] = self.config_data[ConfigUtility._PROJECT_DATA_DICT_CONFIG_NAME]
        if project_id in project_data_dict.keys():
            self.config_data[ConfigUtility._PROJECT_DATA_DICT_CONFIG_NAME].pop(project_id)
            self._write_config_data()

    def get_config(self, config_name: str, project_id: str = None) -> Optional:
        if not config_name:
            self._print_log_error("无法获取设置, 设置名称为空.")
            return None
        project_data_dict: dict = self.get_project_data_dict()
        if project_id:
            if project_id in project_data_dict.keys():
                project_data: dict = project_data_dict[project_id]
                if config_name in project_data.keys():
                    return project_data[config_name]
                else:
                    return None
            else:
                return None
        else:
            if config_name not in self.config_data.keys():
                return None
            return self.config_data[config_name]

    def set_config(self, config_name: str, config_value, project_id: str = None) -> bool:
        if not config_name:
            self._print_log_error("无法设置设置, 设置名称为空.")
            return False
        project_data_dict: dict = self.get_project_data_dict()
        if project_id:
            if project_id in project_data_dict.keys():
                project_data_dict[project_id][config_name] = config_value
            else:
                self._print_log_error(f"无法设置设置, 项目ID\"{project_id}\"数据不存在.")
        else:
            self.config_data[config_name] = config_value
        return self._write_config_data()

    @staticmethod
    def get_wwise_authoring_version(wwise_authoring_path: str) -> str:
        if main.is_windows_os():
            import win32api
            info = win32api.GetFileVersionInfo(wwise_authoring_path, "\\")
            ms = info['FileVersionMS']
            ls = info['FileVersionLS']
            version = f"{win32api.HIWORD(ms)}.{win32api.LOWORD(ms)}.{win32api.HIWORD(ls)}.{win32api.LOWORD(ls)}"
            return version
        else:
            import os
            stream = os.popen(f"defaults read \"{wwise_authoring_path}/Contents/Info.plist\" CFBundleVersion")
            version = stream.read()
            version = version.strip()
            return version

    def _read_config_data(self) -> bool:
        if QFile.exists(self.config_file_path):
            try:
                config_file = open(self.config_file_path)
                self.config_data = json.load(config_file)
                config_file.close()
            except Exception as error:
                self._print_log_error(f"读取配置文件发生异常: {error}.")
                return False
            return True

    def _write_config_data(self) -> bool:
        try:
            self.config_data = dict(sorted(self.config_data.items(), key=lambda item: item[0]))
            config_file = open(self.config_file_path, "w")
            json.dump(self.config_data, config_file, indent=4)
            config_file.close()
        except Exception as error:
            self._print_log_error(f"写入配置文件发生异常: {error}.")
            return False
        return True

    def _print_log_error(self, log: str):
        print(f"[{self.__class__.__name__}][Error] {log}")


config_utility = ConfigUtility()
