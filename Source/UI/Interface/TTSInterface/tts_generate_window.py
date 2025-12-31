# from PySide6.QtCore import Qt
# from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout
#
# from Source.Job.wproj_job import WprojJob
# from Source.UI.Interface.TTSInterface.tts_voice_detail_sub_window import TTSVoiceDetailSubWindow
# from Source.UI.Interface.TTSInterface.tts_voice_list_sub_window import TTSVoiceListSubWindow
# from qfluentwidgets import HorizontalSeparator, LargeTitleLabel
#
#
# class TTSGenerateWindow(QFrame):
#     def __init__(self, parent):
#         super().__init__(parent)
#         self.setObjectName("tts_generate_window")
#         from Source.main_window import MainWindow
#         # noinspection PyTypeChecker
#         self._main_window: MainWindow = parent
#         self.wproj_job: WprojJob = self._main_window.wproj_job
#
#         self.setStyleSheet("TTSGenerateWindow { border: 1px solid rgba(36, 36, 36, 0.1); border-radius: 10px; background-color: rgba(0, 0, 0, 0.08); }")
#
#         self.vbox_layout: QVBoxLayout = QVBoxLayout(self)
#
#         self._init_title_label()
#         self._separator1: HorizontalSeparator = HorizontalSeparator(self)
#         self.vbox_layout.addWidget(self._separator1)
#         self.vbox_layout.addSpacing(10)
#         self._init_main_layout()
#
#     def refresh(self):
#         self.tts_voice_list_sub_window.refresh()
#         self.tts_voice_detail_sub_window.refresh()
#
#     def _init_title_label(self):
#         self._title_layout: QHBoxLayout = QHBoxLayout()
#         self._title_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
#         self._title: LargeTitleLabel = LargeTitleLabel(self)
#         self._title.setText("文本转语音")
#         self._title_layout.addWidget(self._title)
#         self._title_layout.addStretch()
#         self.vbox_layout.addLayout(self._title_layout)
#
#     def _init_main_layout(self):
#         self._main_layout: QHBoxLayout = QHBoxLayout()
#         self.tts_voice_list_sub_window = TTSVoiceListSubWindow(self._main_window, self)
#         self._main_layout.addWidget(self.tts_voice_list_sub_window)
#
#         self.tts_voice_detail_sub_window: TTSVoiceDetailSubWindow = TTSVoiceDetailSubWindow(self._main_window, self)
#         self._main_layout.addWidget(self.tts_voice_detail_sub_window)
#
#         self.vbox_layout.addLayout(self._main_layout)
#
#         self._main_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
