# coding:utf-8
import json
import os
import pathlib
from typing import Optional

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QStackedWidget

import changelog
import main
from Source.Job.work_environment_job import WorkEnvironmentJob
from Source.UI.Basic.changelog_window import ChangelogWindow
from Source.UI.Basic.file_list_setting_card import FileListSettingCard
from Source.Utility.config_utility import ConfigUtility, ProjectData, config_utility
from Source.Utility.sample_utility import SampleUtility
from main import APP_VERSION
from qfluentwidgets import ConfigItem, FluentIcon, FolderListValidator, HorizontalSeparator, LargeTitleLabel, OptionsConfigItem, OptionsSettingCard, OptionsValidator, \
    PushSettingCard, \
    SettingCardGroup, \
    SmoothScrollArea, TabBar, \
    TabCloseButtonDisplayMode, VBoxLayout, qconfig


class SettingInterface(SmoothScrollArea):

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName('setting_interface')
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.setStyleSheet(" QFrame { background-color: white; border-radius: 10px; }")

        from Source.main_window import MainWindow
        # noinspection PyTypeChecker
        self.main_window: MainWindow = parent

        self._changelog_window: Optional[ChangelogWindow] = None

        self._frame: QFrame = QFrame(self)
        self.setWidget(self._frame)
        self._init_layout()

    def _init_layout(self):
        self._layout: VBoxLayout = VBoxLayout(self._frame)

        self._init_project_setting_frame()

        self._init_global_setting_frame()

        self._layout.addStretch()

    def _init_project_setting_frame(self):

        self._project_setting_frame: QFrame = QFrame(self._frame)
        self._project_setting_frame.setStyleSheet("QFrame { border: 1px solid rgba(36, 36, 36, 0.1); border-radius: 10px; background-color: rgba(0, 0, 0, 0.08); }")
        self._layout.addWidget(self._project_setting_frame)

        self._project_setting_frame_layout: VBoxLayout = VBoxLayout(self._project_setting_frame)

        self._init_project_setting_frame_tab_bar()

        self._project_setting_frame_widget_stack: QStackedWidget = QStackedWidget(self._project_setting_frame, objectName='project_setting_frame_widget_stack')
        self._project_setting_frame_layout.addWidget(self._project_setting_frame_widget_stack)

    def _init_project_setting_frame_tab_bar(self):
        self.project_setting_frame_tab_bar: TabBar = TabBar(self._project_setting_frame)
        self.project_setting_frame_tab_bar.setScrollable(True)
        self.project_setting_frame_tab_bar.setAddButtonVisible(False)
        self.project_setting_frame_tab_bar.setTabMaximumWidth(175)
        self.project_setting_frame_tab_bar.setMinimumWidth(70)
        self.project_setting_frame_tab_bar.currentChanged.connect(self.on_project_setting_frame_tab_changed)
        self.project_setting_frame_tab_bar.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.NEVER)
        self._project_setting_frame_layout.addWidget(self.project_setting_frame_tab_bar)

    def close(self):
        if self._changelog_window:
            self._changelog_window.close()

    def refresh_project_setting_frame(self):
        while len(self.project_setting_frame_tab_bar.items) > 0:
            self.project_setting_frame_tab_bar.removeTab(0)
        project_data_dict: dict = config_utility.get_project_data_dict()
        for project_id, project_data in project_data_dict.items():
            project_id: str
            project_data: dict
            project_title: str = project_data[ProjectData.TITLE_CONFIG_NAME]
            self.project_setting_frame_tab_bar.addTab(project_id, project_title, FluentIcon.GAME)

        if len(project_data_dict) > 0:
            self._project_setting_frame.show()
        else:
            self._project_setting_frame.hide()

    def _init_global_setting_frame(self):
        self._global_setting_frame: QFrame = QFrame(self._frame)
        self._global_setting_frame.setStyleSheet(
                "QFrame { border: 1px solid rgba(36, 36, 36, 0.1); border-radius: 10px; background-color: rgba(0, 0, 0, 0.08); } LargeTitleLabel { border: 0px; background-color: transparent;}")
        self._layout.addWidget(self._global_setting_frame)

        self._global_setting_frame_layout: VBoxLayout = VBoxLayout(self._global_setting_frame)

        self._global_setting_label: LargeTitleLabel = LargeTitleLabel(self._global_setting_frame)
        self._global_setting_label.setText("全局设置")
        self._global_setting_frame_layout.addWidget(self._global_setting_label)

        self._global_setting_label_separator: HorizontalSeparator = HorizontalSeparator(self._global_setting_frame)
        self._global_setting_frame_layout.addWidget(self._global_setting_label_separator)
        self._global_setting_frame_layout.addSpacing(10)

        self._init_wwise_authoring_group()
        self._init_sample_group()
        self._init_about_group()

    def _init_wwise_authoring_group(self):
        self._wwise_authoring_frame: QFrame = QFrame(self._global_setting_frame)
        self._wwise_authoring_frame.setStyleSheet("QFrame { border: 1px solid rgba(36, 36, 36, 0.2); border-radius: 10px; background-color: rgba(0, 0, 0, 0.06); }")
        self._global_setting_frame_layout.addWidget(self._wwise_authoring_frame)

        self._wwise_authoring_layout: VBoxLayout = VBoxLayout(self._wwise_authoring_frame)

        self._wwise_authoring_group: SettingCardGroup = SettingCardGroup("Wwise设计工具", self._wwise_authoring_frame)

        wwise_authoring_list: Optional[list[str]] = config_utility.get_config(ConfigUtility.WWISE_AUTHORING_LIST_CONFIG_NAME)
        if not wwise_authoring_list:
            wwise_authoring_list = []
        remove_wwise_authoring_list: set[str] = set()
        for wwise_authoring_path in wwise_authoring_list:
            if main.is_windows_os() and not os.path.isfile(wwise_authoring_path) or not main.is_windows_os() and not os.path.isdir(wwise_authoring_path):
                remove_wwise_authoring_list.add(wwise_authoring_path)
        wwise_authoring_list = list(set(wwise_authoring_list) - remove_wwise_authoring_list)
        config_utility.set_config(ConfigUtility.WWISE_AUTHORING_LIST_CONFIG_NAME, wwise_authoring_list)
        self._wwise_authoring_list = ConfigItem("WwiseAuthoring", "WwiseAuthoringPath", wwise_authoring_list, FolderListValidator())

        if len(wwise_authoring_list) > 0:
            dir_path = os.path.dirname(wwise_authoring_list[0])
        else:
            dir_path = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]

        if main.is_windows_os():
            name_filter = "Wwise设计工具应用 (Wwise.exe)"
        else:
            name_filter = "Wwise设计工具应用 (Wwise.app)"

        file_dialogue_config = {
            "title":       "请选择Wwise设计工具",
            "dir_path":    dir_path,
            "name_filter": name_filter
        }
        self._wwise_authoring_list_card = FileListSettingCard(self.main_window, self._wwise_authoring_list, "Wwise设计工具列表", file_dialogue_config=file_dialogue_config)
        self._wwise_authoring_list_card.file_list_changed.connect(self._on_wwise_authoring_list_changed)
        self._wwise_authoring_list_card.setExpand(True)
        self._wwise_authoring_group.addSettingCard(self._wwise_authoring_list_card)
        self._wwise_authoring_layout.addWidget(self._wwise_authoring_group)

    def _init_sample_group(self):
        self._sample_frame: QFrame = QFrame(self._global_setting_frame)
        self._sample_frame.setStyleSheet("QFrame { border: 1px solid rgba(36, 36, 36, 0.2); border-radius: 10px; background-color: rgba(0, 0, 0, 0.06); }")
        self._global_setting_frame_layout.addWidget(self._sample_frame)

        self._sample_layout: VBoxLayout = VBoxLayout(self._sample_frame)

        self._sample_group: SettingCardGroup = SettingCardGroup("素材", self._sample_frame)

        normalize_target_loudness: int | None = config_utility.get_config(SampleUtility.NORMALIZE_TARGET_LOUDNESS_CONFIG_NAME)
        if not normalize_target_loudness:
            normalize_target_loudness = SampleUtility.DEFAULT_NORMALIZED_LOUDNESS
        self._normalize_target_loudness_options_validator = OptionsValidator(SampleUtility.LOUDNESS_STANDARD_DICT.values())
        self._normalize_target_loudness = OptionsConfigItem("Sample", SampleUtility.NORMALIZE_TARGET_LOUDNESS_CONFIG_NAME, normalize_target_loudness, self._normalize_target_loudness_options_validator)

        self._normalize_target_loudness_card = OptionsSettingCard(self._normalize_target_loudness, FluentIcon.MIX_VOLUMES, "标准化目标响度(dB)", texts=SampleUtility.LOUDNESS_STANDARD_DICT.keys(),
                                                                  parent=self._sample_group)
        self._normalize_target_loudness_card.optionChanged.connect(self._on_normalize_target_loudness_card_option_changed)
        self._sample_group.addSettingCard(self._normalize_target_loudness_card)
        self._sample_layout.addWidget(self._sample_group)

    def _init_about_group(self):
        self._about_frame: QFrame = QFrame(self._global_setting_frame)
        self._about_frame.setStyleSheet("QFrame { border: 1px solid rgba(36, 36, 36, 0.2); border-radius: 10px; background-color: rgba(0, 0, 0, 0.06); }")
        self._global_setting_frame_layout.addWidget(self._about_frame)

        self._about_layout: VBoxLayout = VBoxLayout(self._about_frame)

        self._about_group: SettingCardGroup = SettingCardGroup("关于", self._about_frame)

        self._config_path_card = PushSettingCard("打开应用配置文件", FluentIcon.SAVE, "应用配置文件路径", config_utility.config_file_path, self._about_group)
        self._config_path_card.clicked.connect(self._on_config_path_card_clicked)
        self._about_group.addSettingCard(self._config_path_card)

        self._changelog_card = PushSettingCard("更新日志", FluentIcon.INFO, f"当前版本: {APP_VERSION}", f"开发者: Maybe (E-Mail: maybetan@moonton.com).", self._about_group)
        self._changelog_card.clicked.connect(self._on_changelog_card_clicked)
        self._about_group.addSettingCard(self._changelog_card)

        self._about_layout.addWidget(self._about_group)

    def _on_config_path_card_clicked(self):
        QDesktopServices.openUrl(f"file:///{config_utility.config_file_path}")

    def _on_changelog_card_clicked(self):
        display_log = ""
        for version, log in changelog.CHANGELOG.items().__reversed__():
            display_log = f"{display_log}\n\n{version}\n{log}" if display_log != "" else f"{version}\n{log}"
        self._changelog_window = ChangelogWindow(display_log)
        self._changelog_window.close_signal.connect(self._on_changelog_window_closed)

    def _on_changelog_window_closed(self):
        if not self._changelog_window:
            return
        self._changelog_window.deleteLater()
        self._changelog_window = None

    def _on_normalize_target_loudness_card_option_changed(self, options_config_item: OptionsConfigItem):
        normalize_target_loudness: int = options_config_item.value
        config_utility.set_config(SampleUtility.NORMALIZE_TARGET_LOUDNESS_CONFIG_NAME, normalize_target_loudness)

    def _on_wwise_authoring_list_changed(self, wwise_authoring_list: list[str]):
        config_utility.set_config(ConfigUtility.WWISE_AUTHORING_LIST_CONFIG_NAME, wwise_authoring_list)

    def on_project_setting_frame_tab_changed(self, index):
        # project_id = self.project_setting_frame_tab_bar.items[index].routeKey()
        pass

    def add_wwise_authoring_path(self):
        if main.is_windows_os():
            wwise_authoring_list: Optional[list[str]] = config_utility.get_config(ConfigUtility.WWISE_AUTHORING_LIST_CONFIG_NAME)
            if not wwise_authoring_list:
                wwise_authoring_list = []

            file_utility = self.main_window.wproj_job.file_utility
            wwise_authoring_file_path_list = file_utility.get_files(WorkEnvironmentJob.WWISE_AUTHORING_ROOT_DIR_PATH_WINDOWS, file_name_list=["Wwise.exe"])
            for wwise_authoring_file_path in wwise_authoring_file_path_list:
                if wwise_authoring_file_path not in wwise_authoring_list:
                    wwise_authoring_list.append(wwise_authoring_file_path)
                    wwise_authoring_list.sort()
                    config_utility.set_config(ConfigUtility.WWISE_AUTHORING_LIST_CONFIG_NAME, wwise_authoring_list)
                    self._wwise_authoring_list_card._add_file_item(wwise_authoring_file_path)
                    self._wwise_authoring_list_card.file_list.append(wwise_authoring_file_path)
                    qconfig.set(self._wwise_authoring_list_card.config_item, wwise_authoring_list)
                    qconfig.set(self._wwise_authoring_list, wwise_authoring_list)

                # 添加到WwiseLauncher中
                # wwise_authoring_root_path = str(pathlib.Path(wwise_authoring_file_path).parent).replace("\\", "/")
                # wwise_authoring_root_path = wwise_authoring_root_path[0: len(wwise_authoring_root_path) - len(r"\Authoring\x64\Release\bin")]
                # appdata_path = os.getenv("APPDATA").replace("\\", "/")
                # known_installs_json_path = f"{appdata_path}/WwiseLauncher/Json/knownInstalls.json"
                # known_install_list: list[str] = []
                # if not os.path.isfile(known_installs_json_path):
                #     os.makedirs(os.path.dirname(known_installs_json_path), exist_ok=True)
                #     json_object = json.dumps(known_install_list, indent=4)
                #     with open(known_installs_json_path, "w", encoding="utf-8") as json_file:
                #         json_file.write(json_object)
                #
                # with open(known_installs_json_path, encoding="utf-8") as json_file:
                #     known_install_list = json.load(json_file)
                #
                # if wwise_authoring_root_path not in known_install_list:
                #     known_install_list.append(wwise_authoring_root_path.replace("/", "\\"))
                #     known_install_list.sort()
                #
                # json_object = json.dumps(known_install_list, indent=4)
                # with open(known_installs_json_path, "w", encoding="utf-8") as json_file:
                #     json_file.write(json_object)
