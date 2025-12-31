from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout
from qfluentwidgets import FluentIcon, HorizontalSeparator, PushButton, SubtitleLabel

import main
from Source.Job.wproj_job import WprojJob


class WwiseProjectSubWindow(QFrame):
    def __init__(self, project_id: str, parent):
        super().__init__(parent)
        self.project_id: str = project_id
        from Source.main_window import MainWindow
        parent: MainWindow
        self._wproj_job: WprojJob = parent.wproj_job

        self.setStyleSheet("WwiseProjectSubWindow { border: 1px solid rgba(36, 36, 36, 0.2); border-radius: 10px; background-color: rgba(0, 0, 0, 0.06); }")

        self.setMaximumWidth(250)

        self.vbox_layout: QVBoxLayout = QVBoxLayout(self)
        self._init_view()

    def _init_view(self):
        self._title_layout: QHBoxLayout = QHBoxLayout()
        self._title_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.vbox_layout.addLayout(self._title_layout)
        self._title_label: SubtitleLabel = SubtitleLabel(self)
        self._title_label.setText("Wwise工程")
        self._title_layout.addWidget(self._title_label)

        self._separator1: HorizontalSeparator = HorizontalSeparator(self)
        self.vbox_layout.addWidget(self._separator1)

        self._open_wwise_project_button = PushButton(self)
        self._open_wwise_project_button.setText("打开工程")
        wwise_icon_path = f"{main.ROOT_PATH}/Resource/Icon/Wwise.png"
        self._open_wwise_project_button.setIcon(QIcon(wwise_icon_path))
        self._open_wwise_project_button.clicked.connect(lambda: self._wproj_job.open_wwise_project_prepare_action(self.project_id))
        self.vbox_layout.addWidget(self._open_wwise_project_button)

        self._sync_original_dir_structure_button = PushButton(self)
        self._sync_original_dir_structure_button.setText("同步素材目录结构")
        self._sync_original_dir_structure_button.setIcon(FluentIcon.SYNC)
        self._sync_original_dir_structure_button.clicked.connect(self._wproj_job.sync_original_dir_structure_action)
        self.vbox_layout.addWidget(self._sync_original_dir_structure_button)

        self._clean_akd_file_button = PushButton(self)
        self._clean_akd_file_button.setText("清理Akd文件")
        self._clean_akd_file_button.setIcon(FluentIcon.BROOM)
        self._clean_akd_file_button.clicked.connect(lambda: self._wproj_job.clean_akd_file_action(self.project_id))
        self.vbox_layout.addWidget(self._clean_akd_file_button)

        self._clean_unused_sample_button = PushButton(self)
        self._clean_unused_sample_button.setText("清理无用素材")
        self._clean_unused_sample_button.setIcon(FluentIcon.BROOM)
        self._clean_unused_sample_button.clicked.connect(lambda: self._wproj_job.clean_unused_sample_action(self.project_id))
        self.vbox_layout.addWidget(self._clean_unused_sample_button)

        self.vbox_layout.addStretch()
