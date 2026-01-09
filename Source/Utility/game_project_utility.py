# noinspection PyPackageRequirements
import os
import pathlib

from PySide6.QtCore import Signal

import main
from ruamel.yaml import CommentedMap, CommentedSeq, YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, SingleQuotedScalarString
from Source.Utility.file_utility import FileUtility
from Source.Utility.svn_utility import SVNUtility
from typing_extensions import Optional


class GameProjectUtility(FileUtility, SVNUtility):
    # 信号定义
    add_project_info_signal = Signal(dict)

    game_project_info_dict: dict = {
        "Angle-Wwise":               {
            "SVNWwiseProjectPath":      {
                "RemotePath":        "svn://10.90.62.20/audio/Project/Angle/Wwise",
                "LocalRelativePath": "AngleWwise"
            },
            "AudioBoxWwiseProjectPath": "AngleWwise/Angle/Angle.wproj",
            "SVNUnityPath":             {
                "RemotePath":        "http://10.90.62.129/svn/Unity2022/trunk",
                "LocalRelativePath": "AngleUnity",
                "User":              "Guest",
                "Password":          "Guest"
            },
        },
        "Dawn-Trunk":                {
            "SVNTrunkPath":               {
                "RemotePath":        "svn://10.86.239.36/dawn/trunk",
                "LocalRelativePath": "DawnTrunk"
            },
            "AudioBoxUnityWwiseBankPath": "DawnTrunk/client/dawn/WwiseBank",
            "SVNWwiseProjectPath":        {
                "RemotePath":        "svn://10.86.239.36/dawn/audio",
                "LocalRelativePath": "DawnWwise"
            },
            "AudioBoxWwiseProjectPath":   "DawnWwise/Dawn/Dawn.wproj",
        },
        "G42-Wwise":                 {
            "SVNWwiseProjectPath":      {
                "RemotePath":        "svn://jazmaybe.com/G42_Audio",
                "LocalRelativePath": "G42Wwise"
            },
            "AudioBoxWwiseProjectPath": "G42Wwise/G42/G42.wproj",
        },
        "Girls-NewGirls_HD3WarCard": {
            "SVNTrunkPath":               {
                "RemotePath":        "http://svn.mxhzw.com/svn/gju3d/Branches/NewGirls_HD3WarCard",
                "LocalRelativePath": "GirlsNewGirls_HD3WarCard"
            },
            "AudioBoxUnityWwiseBankPath": "GirlsNewGirls_HD3WarCard/Assets/GirlsGame/Editor/Resources/Wwise/Banks",
            "SVNWwiseProjectPath":        {
                "RemotePath":        "svn://10.90.62.20/audio/Project/NewGirlsWarCard/Wwise",
                "LocalRelativePath": "GirlsNewGirls_HD3WarCardWwise"
            },
            "AudioBoxWwiseProjectPath":   "GirlsNewGirls_HD3WarCardWwise/NewGirlsWarCard/NewGirlsWarCard.wproj",
        },
        "Lovania-Release": {
            "SVNTrunkPath":               {
                "RemotePath":        "svn://192.168.12.28/lovania/release/release",
                "LocalRelativePath": "LovaniaRelease"
            },
            "AudioBoxUnityWwiseBankPath": "LovaniaRelease/Bin/WwiseBank",
            "SVNWwiseProjectPath":        {
                "RemotePath":        "svn://192.168.12.28/lovania_audio/release",
                "LocalRelativePath": "LovaniaWwiseRelease"
            },
            "AudioBoxWwiseProjectPath":   "LovaniaWwiseRelease/Lovania/Lovania.wproj",
        },
        "Lovania-Trunk":             {
            "SVNTrunkPath":               {
                "RemotePath":        "svn://192.168.12.28/lovania/trunk",
                "LocalRelativePath": "LovaniaTrunk"
            },
            "AudioBoxUnityWwiseBankPath": "LovaniaTrunk/Bin/WwiseBank",
            "SVNWwiseProjectPath":        {
                "RemotePath":        "svn://192.168.12.28/lovania_audio/trunk",
                "LocalRelativePath": "LovaniaWwiseTrunk"
            },
            "AudioBoxWwiseProjectPath":   "LovaniaWwiseTrunk/Lovania/Lovania.wproj",
        },
        "SS-Trunk":                  {
            "SVNTrunkPath":               {
                "RemotePath":        "svn://10.90.62.185/SS_UGC/trunk/UGC",
                "LocalRelativePath": "SSTrunk"
            },
            "AudioBoxUnityWwiseBankPath": "SSTrunk/WwiseBank",
            "SVNWwiseProjectPath":        {
                "RemotePath":        "svn://10.90.62.20/audio/Project/SS/Wwise",
                "LocalRelativePath": "SSWwise"
            },
            "AudioBoxWwiseProjectPath":   "SSWwise/SS/SS.wproj",
        },
    }

    def __init__(self, game_project_job):
        from Source.Job.game_project_job import GameProjectJob
        game_project_job: GameProjectJob
        self._game_project_job = game_project_job
        super().__init__(game_project_job)

    def initialize_game_project_job(self, project_info_dict: dict):
        game_project_root_path: str = project_info_dict["game_project_root_path"]

        # 对SmartSVN进行配置
        if main.is_windows_os():
            appdata_path = os.getenv("APPDATA").replace("\\", "/")
        else:
            appdata_path = f"{os.path.expanduser('~')}/Library/Preferences"
        smartsvn_config_dir_root_path = f"{appdata_path}/SmartSVN"
        if not self.create_directory(f"{smartsvn_config_dir_root_path}/14.4"):
            self.finish_signal.emit("任务中止", "", "error")
            return

        for key, value in project_info_dict.items():
            key: str
            current_file_count = 0
            if not key.lower().startswith("svn") or "path" not in key.lower():
                continue
            if main.is_windows_os() and "macos" in key.lower():
                continue
            elif not main.is_windows_os() and "windows" in key.lower():
                continue
            value: dict
            repository_remote_path: str = value["RemotePath"]
            repository_local_path: str = f"{game_project_root_path}/{value['LocalRelativePath']}"
            user: Optional[str] = value.get("User", "")
            password: Optional[str] = value.get("Password", "")
            self.update_progress_text_signal.emit(f"检出\"{repository_remote_path}\"\n至\"{repository_local_path}\"...")
            self.update_progress_total_count_signal.emit(0)
            self.update_progress_current_count_signal.emit(0)
            self.cleanup_repository(repository_local_path, user, password, True)
            file_count = self.get_repository_file_count(repository_remote_path, user, password, 30)
            if file_count >= 0:
                self.update_progress_total_count_signal.emit(file_count)

            for path in self.checkout_repository(repository_remote_path, repository_local_path, user, password):
                if self.cancel_job:
                    self.cleanup_repository(repository_local_path, user, password, True)
                    self.finish_signal.emit("任务中止", "", "warning")
                    return
                if not path:
                    self.cleanup_repository(repository_local_path, user, password, True)
                    self.finish_signal.emit("任务中止", "", "error")
                    return
                if path.startswith("Checked out revision"):
                    self.update_progress_current_count_signal.emit(file_count)
                if any(path.startswith(action) for action in self.SVN_FILE_ACTION_CHARACTER_LIST):
                    current_file_count += 1
                    if file_count < 0:
                        self.update_progress_total_count_signal.emit(current_file_count)
                    self.update_progress_current_count_signal.emit(current_file_count)
                if path == "":
                    self.finish_signal.emit("任务中止", "", "error")
                    return

            # 将SVN工作副本添加到SmartSVN中
            scan_dir_iterator = os.scandir(smartsvn_config_dir_root_path)
            for dir_entry in scan_dir_iterator:
                dir_entry: os.DirEntry
                if not dir_entry.is_dir():
                    continue

                smartsvn_config_dir_path = dir_entry.path.replace("\\", "/")

                workcopy_path_set = set()

                yaml = YAML()
                yaml.preserve_quotes = True
                yaml.default_flow_style = False

                yaml_object = {}

                smartsvn_projects_yaml_path = f"{smartsvn_config_dir_path}/projects.yml"
                if os.path.isfile(smartsvn_projects_yaml_path):
                    with open(smartsvn_projects_yaml_path, encoding="utf-8") as yaml_file:
                        yaml_object = yaml.load(yaml_file)
                    if not yaml_object:
                        yaml_object = {}

                tree_object = self._get_child_commented_map(yaml_object, "tree")
                root_nodes_object = [] if tree_object.get("nodes") is None else tree_object["nodes"]

                def collect_workcopy_path(nodes_commented_seq: CommentedSeq):
                    for commented_map in nodes_commented_seq:
                        if not isinstance(commented_map, CommentedMap):
                            continue
                        commented_map: CommentedMap
                        if "project" in commented_map.keys():
                            workcopy_path_list = commented_map["project"].get("roots", [])
                            for workcopy_path in workcopy_path_list:
                                workcopy_path = workcopy_path.replace("\\", "/")
                                workcopy_path_set.add(workcopy_path)
                        elif "nodes" in commented_map.keys():
                            collect_workcopy_path(commented_map["nodes"])

                collect_workcopy_path(root_nodes_object)

                if repository_local_path not in workcopy_path_set:
                    if main.is_windows_os():
                        workcopy_root_path = repository_local_path.replace('/', '\\')
                    else:
                        workcopy_root_path = repository_local_path
                    root_path_list = CommentedSeq([SingleQuotedScalarString(workcopy_root_path)])
                    root_path_list.fa.set_flow_style()
                    file_filter_dict = CommentedMap({
                        "viewAssignedToChangeSet": False,
                        "viewRemoteChanged2":      False
                    })
                    file_filter_dict.fa.set_flow_style()
                    text_file_settings_dict = CommentedMap({
                        "encoding": "UTF-8"
                    })
                    text_file_settings_dict.fa.set_flow_style()
                    refresh_settings_dict = CommentedMap({
                        "scanRootOnly": False
                    })
                    refresh_settings_dict.fa.set_flow_style()
                    display_settings_dict = CommentedMap({
                        "layoutId": "transaction-layout-raw"
                    })
                    display_settings_dict.fa.set_flow_style()
                    new_workcopy_dict = {
                        "fileFilter": file_filter_dict,
                        "settings":   {
                            "textFileSettings":    text_file_settings_dict,
                            "actionSettings":      {
                                "refreshSettings":     refresh_settings_dict,
                                "workingCopySettings": {
                                    "eolStyle":             "as-is",
                                    "globalIgnoreOption":   "off",
                                    "globalIgnorePatterns": SingleQuotedScalarString("")
                                }
                            },
                            "uiSettings":          {
                                "mainFrameFileTable": {
                                    "visibleColumnNames": DoubleQuotedScalarString("Ext.\tLocal State\tName\tRelative Directory")
                                }
                            },
                            "transactionSettings": {
                                "displaySettings": display_settings_dict
                            }
                        },
                        "name":       value["LocalRelativePath"],
                        "roots":      root_path_list,
                    }
                    find_sorted_nodes_object = False
                    for node_object in root_nodes_object:
                        if not isinstance(node_object, CommentedMap):
                            continue
                        if "nodes" in node_object.keys() and len(node_object.keys()) == 1:
                            find_sorted_nodes_object = True
                            node_object["nodes"] = [] if node_object.get("nodes") is None else node_object["nodes"]
                            node_object["nodes"].append({
                                "project": new_workcopy_dict
                            })
                            break

                    if not find_sorted_nodes_object:
                        root_nodes_object.insert(0, {
                            "nodes": [{
                                "project": new_workcopy_dict
                            }]
                        })
                    with open(smartsvn_projects_yaml_path, "w", encoding="utf-8") as yaml_file:
                        yaml.dump(yaml_object, yaml_file)

        self._config_smartsvn()

        self.add_project_info_signal.emit(project_info_dict)

        self.finish_signal.emit("结果", "初始化游戏项目完成.", "success")

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

        if not self.create_directory(f"{smartsvn_config_dir_root_path}/14.4"):
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
