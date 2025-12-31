from lxml.etree import Element
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QFrame, QHBoxLayout, QListWidgetItem, QVBoxLayout

from qfluentwidgets import FluentIcon, HorizontalSeparator, ListWidget, PushButton, StrongBodyLabel, SubtitleLabel
from Source.Job.soundbank_job import SoundBankJob
from Source.Job.wproj_job import WprojJob
from Source.Utility.config_utility import config_utility, ProjectData


class SoundbankSubWindow(QFrame):
    def __init__(self, project_id: str, parent):
        super().__init__(parent)
        self.project_id: str = project_id
        from Source.main_window import MainWindow
        parent: MainWindow
        self.language_check_dict: {
            str: bool
        } = {}
        self._wproj_job: WprojJob = parent.wproj_job
        self._soundbank_job: SoundBankJob = parent.soundbank_job

        self.setStyleSheet("SoundbankSubWindow { border: 1px solid rgba(36, 36, 36, 0.2); border-radius: 10px; background-color: rgba(0, 0, 0, 0.06); }")

        self.setMaximumWidth(250)
        self.vbox_layout: QVBoxLayout = QVBoxLayout(self)
        self._init_language_check_list_view()

    def refresh_language_list(self):
        project_data: dict[str, str] = config_utility.get_project_data(self.project_id)
        wwise_project_path: str = project_data.get(ProjectData.WWISE_PROJECT_PATH)
        if wwise_project_path:
            wproj_root_element: Element | None = self._wproj_job.read_wproj_file(wwise_project_path)
            if wproj_root_element is not None:
                self.show()
                language_check_dict: dict | None = config_utility.get_project_language_check_dict_config(self.project_id)
                language_list: [str] = WprojJob.get_language(wproj_root_element)
                if not language_check_dict:
                    language_check_dict = {}
                    for language in language_list:
                        language: str
                        language_check_dict[language] = False
                    self.language_check_dict = language_check_dict
                    config_utility.set_project_language_check_dict_config(self.project_id, self.language_check_dict)
                elif language_check_dict.keys() != language_list:
                    new_language_check_dict: dict = {}
                    for language in language_list:
                        language: str
                        if language in language_check_dict.keys():
                            new_language_check_dict[language] = language_check_dict[language]
                        else:
                            new_language_check_dict[language] = False
                    self.language_check_dict = new_language_check_dict
                    config_utility.set_project_language_check_dict_config(self.project_id, new_language_check_dict)
                else:
                    self.language_check_dict = language_check_dict
                self._refresh_language_check_list_widget()
            else:
                self.hide()
        else:
            self.hide()

    def _init_language_check_list_view(self):
        self._soundbank_title_layout: QHBoxLayout = QHBoxLayout()
        self._soundbank_title_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.vbox_layout.addLayout(self._soundbank_title_layout)
        self._soundbank_label: SubtitleLabel = SubtitleLabel(self)
        self._soundbank_label.setText("声音库")
        self._soundbank_title_layout.addWidget(self._soundbank_label)

        self._separator1: HorizontalSeparator = HorizontalSeparator(self)
        self.vbox_layout.addWidget(self._separator1)

        self._language_check_list_label: StrongBodyLabel = StrongBodyLabel(self)
        self._language_check_list_label.setText("语言列表")
        self.vbox_layout.addWidget(self._language_check_list_label)

        self._language_check_list_widget: ListWidget = ListWidget(self)
        self._language_check_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._language_check_list_widget.itemChanged.connect(self._on_language_item_changed)
        self.vbox_layout.addWidget(self._language_check_list_widget)

        self._separator2: HorizontalSeparator = HorizontalSeparator(self)
        self.vbox_layout.addWidget(self._separator2)

        self.vbox_layout.addStretch()

        self._sync_soundbank_button = PushButton(self)
        self._sync_soundbank_button.setText("同步声音库")
        self._sync_soundbank_button.setIcon(FluentIcon.SYNC)
        self._sync_soundbank_button.clicked.connect(lambda: self._soundbank_job.sync_soundbank_action(self.project_id))
        self.vbox_layout.addWidget(self._sync_soundbank_button)

        self._clean_soundbank_button = PushButton(self)
        self._clean_soundbank_button.setText("清理打包声音库目录")
        self._clean_soundbank_button.setIcon(FluentIcon.BROOM)
        self._clean_soundbank_button.clicked.connect(lambda: self._soundbank_job.clean_generated_soundbanks_dir_action(self.project_id))
        self.vbox_layout.addWidget(self._clean_soundbank_button)

    def _refresh_language_check_list_widget(self):
        self._language_check_list_widget.clear()
        if self.language_check_dict:
            for language, check_state in self.language_check_dict.items():
                item: QListWidgetItem = QListWidgetItem(language)
                if check_state:
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
                self._language_check_list_widget.addItem(item)

    def _on_language_item_changed(self, item: QListWidgetItem):
        selected_item_list = self._language_check_list_widget.selectedItems()
        for selected_item in selected_item_list:
            selected_item.setCheckState(self._language_check_list_widget.currentItem().checkState())
        self.language_check_dict[item.text()] = item.checkState() == Qt.CheckState.Checked
        config_utility.set_project_language_check_dict_config(self.project_id, self.language_check_dict)
