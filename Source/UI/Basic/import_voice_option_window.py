import os

from PySide6.QtCore import QStandardPaths, Qt, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget

from Source.Utility.config_utility import config_utility
from qfluentwidgets import BodyLabel, FluentIcon, HorizontalSeparator, ListWidget, PrimaryPushButton, PushButton, PushSettingCard


class ImportVoiceOptionWindow(QWidget):
    accept_signal = Signal()
    cancel_signal = Signal()

    def __init__(self, parameter_dict: dict):
        super().__init__()

        self.project_id: str = parameter_dict["project_id"]
        self.dir_path: str = parameter_dict["dir_path"]
        self.voice_excel_file_path = ""
        self.voice_excel_file_parent_path = ""
        self.import_language_list = []
        self.reference_language = parameter_dict["reference_language"]

        self._language_list: [str] = parameter_dict["language_list"]

        self.setWindowTitle("入库语音素材设置窗口")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowMaximizeButtonHint)
        self.setStyleSheet("background-color: white")

        self._layout = QVBoxLayout(self)

        self._init_language_option_note_label_layout()

        self._list_widget = ListWidget(self)
        self._list_widget.setAlternatingRowColors(True)
        for language in self._language_list:
            item = QListWidgetItem(language)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._list_widget.addItem(item)
        self._layout.addWidget(self._list_widget)

        self._separator1 = HorizontalSeparator(self)
        self._layout.addWidget(self._separator1)

        self._layout.addSpacing(10)

        self._init_voice_excel_note_label_layout()
        self._init_voice_excel_path_push_setting_card()

        self._separator2 = HorizontalSeparator(self)
        self._layout.addWidget(self._separator2)

        self._layout.addSpacing(10)

        self._init_button()

        # self.resize(800, 800)
        self.show()

    def _init_language_option_note_label_layout(self):
        self._language_option_note_label_layout = QHBoxLayout()
        self._language_option_note_label_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._language_option_note_label = BodyLabel(self)
        self._language_option_note_label.setText("检测到语音素材\n请选择语音素材的入库语言(可多选)\n如果不选择任何语言, 则语音素材将不会执行入库操作")
        self._language_option_note_label_layout.addWidget(self._language_option_note_label)
        self._layout.addLayout(self._language_option_note_label_layout)

    def _init_voice_excel_note_label_layout(self):
        self._voice_excel_note_label_layout = QHBoxLayout()
        self._voice_excel_note_label_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._voice_excel_note_label = BodyLabel(self)
        self._voice_excel_note_label.setText("请选择录音工作簿(可选)\n如果选择了录音工作簿, 则入库语音素材时将会同步录音工作簿中标记相应语音事件的台本的修订列状态")
        self._voice_excel_note_label_layout.addWidget(self._voice_excel_note_label)
        self._layout.addLayout(self._voice_excel_note_label_layout)

    def _init_voice_excel_path_push_setting_card(self):
        self._voice_excel_path_push_setting_card = PushSettingCard("选择录音工作簿", FluentIcon.FEEDBACK, "录音工作簿", "", self)
        self._voice_excel_path_push_setting_card.clicked.connect(self._on_voice_excel_path_push_setting_card_clicked)
        self._layout.addWidget(self._voice_excel_path_push_setting_card)

    def _init_button(self):
        self._button_layout = QHBoxLayout()
        self._layout.addLayout(self._button_layout)

        self._accept_button = PrimaryPushButton(self)
        self._accept_button.setText("确认")
        self._accept_button.setIcon(FluentIcon.ACCEPT)
        self._accept_button.clicked.connect(self._on_accept_button_clicked)
        self._button_layout.addWidget(self._accept_button)

        self._cancel_button = PushButton(self)
        self._cancel_button.setText("取消")
        self._cancel_button.setIcon(FluentIcon.CANCEL)
        self._cancel_button.clicked.connect(self._on_cancel_button_clicked)
        self._button_layout.addWidget(self._cancel_button)

    def _on_voice_excel_path_push_setting_card_clicked(self):
        voice_excel_file_dialog: QFileDialog = QFileDialog(self)
        voice_excel_file_dialog.setWindowTitle("请选择录音工作簿")
        from Source.Job.wproj_job import WprojJob
        last_selected_voice_excel_file_parent_path = config_utility.get_config(WprojJob.LAST_SELECTED_IMPORT_VOICE_EXCEL_FILE_PARENT_PATH_CONFIG_NAME, self.project_id)

        if last_selected_voice_excel_file_parent_path and os.path.isdir(last_selected_voice_excel_file_parent_path):
            set_directory: str = last_selected_voice_excel_file_parent_path
        else:
            set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]

        voice_excel_file_dialog.setDirectory(set_directory)
        last_selected_voice_excel_file_name: str = config_utility.get_config(WprojJob.LAST_SELECTED_IMPORT_VOICE_EXCEL_FILE_NAME_CONFIG_NAME, self.project_id)
        if last_selected_voice_excel_file_name:
            last_selected_voice_excel_file_path = f"{set_directory}/{last_selected_voice_excel_file_name}"
            if os.path.isfile(last_selected_voice_excel_file_path):
                voice_excel_file_dialog.selectFile(last_selected_voice_excel_file_name)
        voice_excel_file_dialog.setNameFilter("Excel文件 (*.xlsx)")
        voice_excel_file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        voice_excel_file_dialog.setViewMode(QFileDialog.ViewMode.List)

        if voice_excel_file_dialog.exec():
            self.voice_excel_file_path = voice_excel_file_dialog.selectedFiles()[0]
            _voice_excel_file_dir = voice_excel_file_dialog.directory()
            self.voice_excel_file_parent_path = _voice_excel_file_dir.path()
        else:
            self.voice_excel_file_path = ""
            self.voice_excel_file_parent_path = ""
        self._voice_excel_path_push_setting_card.setContent(self.voice_excel_file_path)

    def _on_accept_button_clicked(self):
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                self.import_language_list.append(item.text())
        self.accept_signal.emit()
        self.close()

    def _on_cancel_button_clicked(self):
        self.cancel_signal.emit()
        self.close()
