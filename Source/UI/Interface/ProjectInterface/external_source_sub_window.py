from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout
from qfluentwidgets import FluentIcon, HorizontalSeparator, PushButton, SubtitleLabel

from Source.Job.external_source_job import ExternalSourceJob
from Source.Job.wproj_job import WprojJob


class ExternalSourceSubWindow(QFrame):
    def __init__(self, project_id: str, parent):
        super().__init__(parent)
        self.project_id: str = project_id
        from Source.main_window import MainWindow
        parent: MainWindow
        self._wproj_job: WprojJob = parent.wproj_job
        self._external_source_job: ExternalSourceJob = parent.external_source_job

        self.setStyleSheet("ExternalSourceSubWindow { border: 1px solid rgba(36, 36, 36, 0.2); border-radius: 10px; background-color: rgba(0, 0, 0, 0.06); }")

        self.setMaximumWidth(250)

        self.vbox_layout: QVBoxLayout = QVBoxLayout(self)
        self._init_view()

    def _init_view(self):
        self._title_layout: QHBoxLayout = QHBoxLayout()
        self._title_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.vbox_layout.addLayout(self._title_layout)
        self._title_label: SubtitleLabel = SubtitleLabel(self)
        self._title_label.setText("外部源")
        self._title_layout.addWidget(self._title_label)

        self._separator1: HorizontalSeparator = HorizontalSeparator(self)
        self.vbox_layout.addWidget(self._separator1)

        self._open_external_source_dir_button = PushButton(self)
        self._open_external_source_dir_button.setText("打开外部源目录")
        self._open_external_source_dir_button.setIcon(FluentIcon.FOLDER)
        self._open_external_source_dir_button.clicked.connect(lambda: self._wproj_job.open_external_source_dir_action(self.project_id))
        self.vbox_layout.addWidget(self._open_external_source_dir_button)

        '''
        self._sync_external_source_list_button = PushButton(self)
        self._sync_external_source_list_button.setText("刷新外部源列表")
        self._sync_external_source_list_button.setIcon(FluentIcon.SYNC)
        self._sync_external_source_list_button.clicked.connect(lambda: self._wproj_job.sync_external_source_list_action(self.project_id))
        self.vbox_layout.addWidget(self._sync_external_source_list_button)

        self._open_external_source_list_button = PushButton(self)
        self._open_external_source_list_button.setText("查看外部源列表")
        self._open_external_source_list_button.setIcon(FluentIcon.DOCUMENT)
        self._open_external_source_list_button.clicked.connect(lambda: self._wproj_job.open_external_source_list_action(self.project_id))
        self.vbox_layout.addWidget(self._open_external_source_list_button)
        '''

        self._convert_external_source_button = PushButton(self)
        self._convert_external_source_button.setText("转码外部源")
        self._convert_external_source_button.setIcon(FluentIcon.ALBUM)
        self._convert_external_source_button.clicked.connect(lambda: self._external_source_job.convert_project_external_source_action(self.project_id))
        self.vbox_layout.addWidget(self._convert_external_source_button)

        self.vbox_layout.addStretch()
