import json
import os

from PySide6.QtWidgets import QFrame, QStackedWidget, QVBoxLayout

import main
from qfluentwidgets import Dialog, FluentIcon, TabCloseButtonDisplayMode
from Source.UI.Basic.line_edit_window import LineEditWindow
from Source.UI.Basic.project_tab_bar import ProjectTabBar, ProjectTabItem
from Source.UI.Interface.ProjectInterface.project_tab_window import ProjectTabWindow
from Source.Utility.config_utility import config_utility, ProjectData
from Source.Utility.game_project_utility import GameProjectUtility


class ProjectInterface(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        from Source.main_window import MainWindow
        # noinspection PyTypeChecker
        self._main_window: MainWindow = parent
        self.setObjectName("project_interface")
        self._vbox_layout: QVBoxLayout = QVBoxLayout(self)
        self._init_project_tab_bar()
        self._init_project_tab_window_stack()
        self._init_project_tab_window()
        self._project_title_edit_window: LineEditWindow | None = None

    def get_current_project_id(self) -> str | None:
        if len(self.project_tab_bar.items) == 0:
            return None
        current_tab: ProjectTabItem = self.project_tab_bar.currentTab()
        if not current_tab:
            return None
        return current_tab.routeKey()

    def _init_project_tab_bar(self):
        self.project_tab_bar = ProjectTabBar(self)
        self.project_tab_bar.setMovable(True)
        self.project_tab_bar.setScrollable(True)
        self.project_tab_bar.setTabMaximumWidth(220)
        self.project_tab_bar.setMinimumWidth(70)
        self.project_tab_bar.currentChanged.connect(self.on_project_tab_changed)
        self.project_tab_bar.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.ON_HOVER)
        self.project_tab_bar.tabAddRequested.connect(self.on_project_tab_add_requested)
        self.project_tab_bar.tabCloseRequested.connect(self.on_tab_close_requested)
        self.project_tab_bar.tab_item_swaped_signal.connect(self.on_tab_item_swaped)
        self._vbox_layout.addWidget(self.project_tab_bar)

    def _init_project_tab_window_stack(self):
        self._project_tab_window_stack = QStackedWidget(self, objectName='project_tab_interface_stack')
        self._vbox_layout.addWidget(self._project_tab_window_stack)

    def _init_project_tab_window(self):
        project_data_dict: dict[str, dict[str, str]] = config_utility.get_project_data_dict()
        for project_id, project_data in project_data_dict.items():
            project_id: str
            project_data: dict[str, str]
            project_title: str = project_data[ProjectData.TITLE_CONFIG_NAME]
            project_tab_item: ProjectTabItem = self.project_tab_bar.addTab(project_id, project_title, FluentIcon.GAME)
            project_tab_item.setAutoFillBackground(True)
            project_tab_item.rename_signal.connect(self.on_tab_item_rename_requested)
            project_tab_window: ProjectTabWindow = ProjectTabWindow(project_id, self._main_window)
            self._project_tab_window_stack.addWidget(project_tab_window)

    def close(self):
        if self._project_title_edit_window:
            self._project_title_edit_window.close()

    def on_project_tab_changed(self, index):
        project_id = self.project_tab_bar.items[index].routeKey()

        # noinspection PyTypeChecker
        project_tab_window: ProjectTabWindow = self._project_tab_window_stack.findChild(ProjectTabWindow, project_id)
        project_tab_window.refresh_wwise_project_data()

        self._project_tab_window_stack.setCurrentWidget(self._project_tab_window_stack.findChild(ProjectTabWindow, project_id))

        self._main_window.title_bar.refresh()

    def on_project_tab_add_requested(self):
        self._project_title_edit_window = LineEditWindow("请输入项目名称")
        self._project_title_edit_window.confirm_signal.connect(self.add_tab)

    def on_tab_close_requested(self, close_tab_index: int):
        remove_tab = self.project_tab_bar.items[close_tab_index]
        project_id: str = remove_tab.routeKey()
        project_data: dict[str, str] = config_utility.get_project_data(project_id)
        dialog: Dialog = Dialog("确认删除项目？", f"{project_data['Title']}", self)
        if dialog.exec():
            self._project_tab_window_stack.removeWidget(self._project_tab_window_stack.findChild(ProjectTabWindow, project_id))
            self.project_tab_bar.removeTab(close_tab_index)
            config_utility.remove_project_data(project_id)
            self._main_window.title_bar.refresh()

    def on_tab_item_swaped(self, index: int):
        # print(f"swap_item_index: {index}; current_index: {self._project_tab_bar.currentIndex()}")
        config_utility.swap_project_data(index, self.project_tab_bar.currentIndex())

    def on_tab_item_rename_requested(self, route_key: str):
        project_id: str = route_key
        self._project_title_edit_window = LineEditWindow("请输入项目名称")
        project_data: dict = config_utility.get_project_data(project_id)
        project_title: str = project_data[ProjectData.TITLE_CONFIG_NAME]

        self._project_title_edit_window.route_key = project_id
        self._project_title_edit_window.line_edit.setText(project_title)
        self._project_title_edit_window.rename_signal.connect(self.rename_tab)

    def add_tab(self, project_title: str) -> str:
        project_data_dict: dict[str, dict[str, str]] = config_utility.get_project_data_dict()
        import uuid
        project_id: str = str(uuid.uuid4())
        while project_data_dict and project_id in project_data_dict.keys():
            project_id = str(uuid.uuid4())
        config_utility.add_project_data(project_id, project_title)
        project_tab_item: ProjectTabItem = self.project_tab_bar.addTab(project_id, project_title, FluentIcon.GAME)
        project_tab_item.rename_signal.connect(self.on_tab_item_rename_requested)
        project_tab_window: ProjectTabWindow = ProjectTabWindow(project_id, self._main_window)
        self._project_tab_window_stack.addWidget(project_tab_window)
        return project_id

    def rename_tab(self, route_key: str, title: str):
        project_id: str = route_key
        config_utility.set_project_data_config(project_id, ProjectData.TITLE_CONFIG_NAME, title)
        project_tab_item: ProjectTabItem = self.project_tab_bar.tab(project_id)
        project_tab_item.setText(title)
        # noinspection PyTypeChecker
        project_tab_window: ProjectTabWindow = self._project_tab_window_stack.findChild(ProjectTabWindow, project_id)
        project_tab_window.refresh_wwise_project_data()

    def add_project_info(self, project_info_dict: dict):
        game_project_name: str = project_info_dict["game_project_name"]
        game_project_root_path: str = project_info_dict["game_project_root_path"]
        current_game_project_info_dict: dict = GameProjectUtility.game_project_info_dict[game_project_name]
        project_data_dict: dict[str, dict[str, str]] = config_utility.get_project_data_dict()
        import uuid
        project_id: str = str(uuid.uuid4())
        while project_data_dict and project_id in project_data_dict.keys():
            project_id = str(uuid.uuid4())
        if "AudioBoxUnityWwiseBankPath" in current_game_project_info_dict.keys() or "AudioBoxWwiseProjectPath" in current_game_project_info_dict.keys():
            config_utility.add_project_data(project_id, game_project_name)

        if "AudioBoxUnityWwiseBankPath" in current_game_project_info_dict.keys():
            audio_box_unity_wwise_bank_path = f"{game_project_root_path}/{current_game_project_info_dict['AudioBoxUnityWwiseBankPath']}"
            if os.path.isdir(audio_box_unity_wwise_bank_path):
                config_utility.set_project_data_config(project_id, ProjectData.UNITY_WWISE_BANK_PATH, audio_box_unity_wwise_bank_path)

        if "AudioBoxWwiseProjectPath" in current_game_project_info_dict.keys():
            audio_box_wwise_project_path = f"{game_project_root_path}/{current_game_project_info_dict['AudioBoxWwiseProjectPath']}"
            if os.path.isfile(audio_box_wwise_project_path):
                config_utility.set_project_data_config(project_id, ProjectData.WWISE_PROJECT_PATH, audio_box_wwise_project_path)
                # 将Wwise工程添加到WwiseLauncher中
                if main.is_windows_os():
                    wwise_launcher_wwise_project_path = audio_box_wwise_project_path.replace("/", "\\")
                    appdata_path = os.getenv("APPDATA").replace("\\", "/")
                    wwise_projects_info_json_path = f"{appdata_path}/WwiseLauncher/Json/wwise-projects-info.json"
                    wwise_projects_info_dict: dict = {}
                    if not os.path.isfile(wwise_projects_info_json_path):
                        os.makedirs(os.path.dirname(wwise_projects_info_json_path), exist_ok=True)
                        json_object = json.dumps(wwise_projects_info_dict, indent=4)
                        with open(wwise_projects_info_json_path, "w", encoding="utf-8") as json_file:
                            json_file.write(json_object)

                    with open(wwise_projects_info_json_path, encoding="utf-8") as json_file:
                        wwise_projects_info_dict = json.load(json_file)

                    if wwise_launcher_wwise_project_path not in wwise_projects_info_dict.keys():
                        wwise_projects_info_dict[wwise_launcher_wwise_project_path] = {
                            "lastOpenedWith": ""
                        }

                    json_object = json.dumps(wwise_projects_info_dict, indent=4)
                    with open(wwise_projects_info_json_path, "w", encoding="utf-8") as json_file:
                        json_file.write(json_object)

        if "AudioBoxUnityWwiseBankPath" in current_game_project_info_dict.keys() or "AudioBoxWwiseProjectPath" in current_game_project_info_dict.keys():
            project_tab_item: ProjectTabItem = self.project_tab_bar.addTab(project_id, game_project_name, FluentIcon.GAME)
            project_tab_item.rename_signal.connect(self.on_tab_item_rename_requested)
            project_tab_window = ProjectTabWindow(project_id, self._main_window)
            self._project_tab_window_stack.addWidget(project_tab_window)
            project_tab_window.refresh_wwise_project_data()
            self._main_window.title_bar.refresh()
