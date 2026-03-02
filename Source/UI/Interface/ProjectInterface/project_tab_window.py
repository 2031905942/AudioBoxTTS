from pathlib import Path

from PySide6.QtCore import QDir, QFile, QFileInfo, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QPushButton, QVBoxLayout

from qfluentwidgets import FluentIcon, HorizontalSeparator, LargeTitleLabel, PushSettingCard, TransparentPushButton
from Source.Job.wproj_job import WprojJob
from Source.UI.Basic.error_info_bar import ErrorInfoBar
from Source.UI.Interface.ProjectInterface.external_source_sub_window import ExternalSourceSubWindow
from Source.UI.Interface.ProjectInterface.soundbank_sub_window import SoundbankSubWindow
from Source.UI.Interface.ProjectInterface.wwise_project_sub_window import WwiseProjectSubWindow
from Source.Utility.config_utility import config_utility, ProjectData


class ProjectTabWindow(QFrame):
    def __init__(self, route_key: str, parent):
        super().__init__(parent)
        self.setObjectName(route_key)
        from Source.main_window import MainWindow
        # noinspection PyTypeChecker
        self._main_window: MainWindow = parent
        self.project_id: str = route_key
        self.wwise_version: str | None = None
        self.wproj_job: WprojJob = self._main_window.wproj_job

        self.setStyleSheet("ProjectTabWindow { border: 1px solid rgba(36, 36, 36, 0.1); border-radius: 10px; background-color: rgba(0, 0, 0, 0.08); }")

        self.vbox_layout: QVBoxLayout = QVBoxLayout(self)

        self._init_project_title_label()
        self._separator1: HorizontalSeparator = HorizontalSeparator(self)
        self.vbox_layout.addWidget(self._separator1)
        self.vbox_layout.addSpacing(10)
        self._init_wwise_project_path_push_setting_card()
        self._init_unity_wwise_bank_path_push_setting_card()
        self._init_function_layout()
        self.vbox_layout.addStretch()
        self.refresh_wwise_project_data()

    def refresh_wwise_project_data(self):
        project_data: dict[str, str] = config_utility.get_project_data(self.project_id)
        project_title: str = project_data.get(ProjectData.TITLE_CONFIG_NAME)
        self._project_title.setText(project_title)

        wwise_project_path: str = project_data.get(ProjectData.WWISE_PROJECT_PATH)
        self._update_open_wwise_project_root_button_state(wwise_project_path)
        if wwise_project_path:
            wproj_root_element = self.wproj_job.read_wproj_file(wwise_project_path)
            self._wwise_project_sub_window.show()
            if wproj_root_element is not None:
                self.wwise_version: str | None = WprojJob.get_wwise_version(wproj_root_element)
                if self.wwise_version:
                    self._wwise_version_display_button.setText(f"Wwise版本: {self.wwise_version}")
                    self._wwise_version_display_button.setIcon(FluentIcon.INFO)

                    def on_wwise_version_display_button_double_click(_):
                        QDesktopServices.openUrl(f"file:///{Path(wwise_project_path).parent}")

                    self._wwise_version_display_button.mouseDoubleClickEvent = on_wwise_version_display_button_double_click
        else:
            self._wwise_project_sub_window.hide()

        self._soundbank_sub_window.refresh_language_list()

    def _init_project_title_label(self):
        self._project_title_layout: QHBoxLayout = QHBoxLayout()
        self._project_title_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self._project_title: LargeTitleLabel = LargeTitleLabel(self)
        self._wwise_version_display_button: TransparentPushButton = TransparentPushButton(self)
        self._wwise_version_display_button.setCheckable(False)
        self._project_title_layout.addWidget(self._project_title)
        self._project_title_layout.addStretch()
        self._project_title_layout.addWidget(self._wwise_version_display_button)
        self.vbox_layout.addLayout(self._project_title_layout)

    def _init_wwise_project_path_push_setting_card(self):
        self._wwise_project_path_push_setting_card = PushSettingCard("选择Wwise工程文件", FluentIcon.TILES, "Wwise工程", "*.wproj", self)
        self._wwise_project_path_push_setting_card.clicked.connect(self._on_wwise_project_path_push_setting_card_clicked)

        self._open_wwise_project_root_button: QPushButton = QPushButton("打开Wwise工程根目录", self._wwise_project_path_push_setting_card)
        self._open_wwise_project_root_button.setCheckable(False)
        self._open_wwise_project_root_button.setEnabled(False)
        self._open_wwise_project_root_button.clicked.connect(self._on_open_wwise_project_root_button_clicked)

        card_layout = self._wwise_project_path_push_setting_card.hBoxLayout
        insert_index = card_layout.count() - 1
        card_layout.insertSpacing(insert_index, 8)
        card_layout.insertWidget(insert_index + 1, self._open_wwise_project_root_button, 0, Qt.AlignmentFlag.AlignRight)

        project_data: dict = config_utility.get_project_data(self.project_id)
        if project_data:
            wproj_file_path = project_data.get(ProjectData.WWISE_PROJECT_PATH, "")
            if wproj_file_path:
                self._wwise_project_path_push_setting_card.setContent(wproj_file_path)
                self._update_open_wwise_project_root_button_state(wproj_file_path)
        self.vbox_layout.addWidget(self._wwise_project_path_push_setting_card)

    def _init_unity_wwise_bank_path_push_setting_card(self):
        self._unity_wwise_bank_path_push_setting_card = PushSettingCard("选择Unity工程声音库目录", FluentIcon.GAME, "Unity工程声音库目录", "/WwiseBank", self)
        self._unity_wwise_bank_path_push_setting_card.clicked.connect(self._on_unity_wwise_bank_path_push_setting_card_clicked)
        project_data: dict = config_utility.get_project_data(self.project_id)
        if project_data:
            unity_wwise_bank_path = project_data.get(ProjectData.UNITY_WWISE_BANK_PATH, "")
            if unity_wwise_bank_path:
                self._unity_wwise_bank_path_push_setting_card.setContent(unity_wwise_bank_path)
        self.vbox_layout.addWidget(self._unity_wwise_bank_path_push_setting_card)

    def _init_function_layout(self):
        self._function_layout: QHBoxLayout = QHBoxLayout()
        self._soundbank_sub_window: SoundbankSubWindow = SoundbankSubWindow(self.project_id, self._main_window)
        self._function_layout.addWidget(self._soundbank_sub_window)

        self._wwise_project_sub_window: WwiseProjectSubWindow = WwiseProjectSubWindow(self.project_id, self._main_window)
        self._function_layout.addWidget(self._wwise_project_sub_window)

        self._external_source_sub_window = ExternalSourceSubWindow(self.project_id, self._main_window)
        self._function_layout.addWidget(self._external_source_sub_window)

        self.vbox_layout.addLayout(self._function_layout)

        self._function_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def _on_wwise_project_path_push_setting_card_clicked(self):
        wproj_file_dialog: QFileDialog = QFileDialog(self)
        wproj_file_dialog.setWindowTitle("请选择Wwise工程文件")
        set_dir: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        wproj_file_dialog.setDirectory(set_dir)
        wproj_file_path: str = ""
        project_data: dict = config_utility.get_project_data(self.project_id)
        if project_data:
            wproj_file_path = project_data.get(ProjectData.WWISE_PROJECT_PATH, "")

        if wproj_file_path and QFile.exists(wproj_file_path):
            wproj_file_info: QFileInfo = QFileInfo(wproj_file_path)
            set_dir = wproj_file_info.dir().path()
            wproj_file_name: str = wproj_file_info.fileName()
            wproj_file_dialog.setDirectory(set_dir)
            wproj_file_dialog.selectFile(wproj_file_name)

        wproj_file_dialog.setNameFilter("Wwise工程文件 (*.wproj)")
        wproj_file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        wproj_file_dialog.setViewMode(QFileDialog.ViewMode.List)
        if wproj_file_dialog.exec():
            wproj_file_path = wproj_file_dialog.selectedFiles()[0]
            config_utility.set_project_data_config(self.project_id, ProjectData.WWISE_PROJECT_PATH, wproj_file_path)
            self._wwise_project_path_push_setting_card.setContent(wproj_file_path)
            self.refresh_wwise_project_data()
            self._main_window.title_bar.refresh()

    def _on_open_wwise_project_root_button_clicked(self):
        project_data: dict = config_utility.get_project_data(self.project_id)
        wproj_file_path: str = ""
        if project_data:
            wproj_file_path = project_data.get(ProjectData.WWISE_PROJECT_PATH, "")

        wwise_project_root_path = Path(wproj_file_path).parent if wproj_file_path else None
        if not wwise_project_root_path or not wwise_project_root_path.exists():
            ErrorInfoBar("Wwise工程根目录不存在或不可访问", self)
            self._update_open_wwise_project_root_button_state(wproj_file_path)
            return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(wwise_project_root_path))):
            ErrorInfoBar("打开Wwise工程根目录失败", self)

    def _update_open_wwise_project_root_button_state(self, wproj_file_path: str | None):
        is_valid_wproj_file = bool(wproj_file_path and QFile.exists(wproj_file_path))
        self._open_wwise_project_root_button.setEnabled(is_valid_wproj_file)

    def _on_unity_wwise_bank_path_push_setting_card_clicked(self):
        unity_wwise_bank_path_file_dialog: QFileDialog = QFileDialog(self)
        unity_wwise_bank_path_file_dialog.setWindowTitle("请选择Unity工程声音库")
        set_dir: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        unity_wwise_bank_path: str = ""
        project_data: dict = config_utility.get_project_data(self.project_id)
        if project_data:
            unity_wwise_bank_path = project_data.get(ProjectData.UNITY_WWISE_BANK_PATH, "")

        if unity_wwise_bank_path and QDir(unity_wwise_bank_path).exists():
            set_dir = unity_wwise_bank_path
        unity_wwise_bank_path_file_dialog.setDirectory(set_dir)

        unity_wwise_bank_path_file_dialog.setFileMode(QFileDialog.FileMode.Directory)
        unity_wwise_bank_path_file_dialog.setViewMode(QFileDialog.ViewMode.List)
        if unity_wwise_bank_path_file_dialog.exec():
            unity_wwise_bank_path = unity_wwise_bank_path_file_dialog.selectedFiles()[0]
            config_utility.set_project_data_config(self.project_id, ProjectData.UNITY_WWISE_BANK_PATH, unity_wwise_bank_path)
            self._unity_wwise_bank_path_push_setting_card.setContent(unity_wwise_bank_path)
