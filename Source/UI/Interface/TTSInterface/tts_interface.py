# from PySide6.QtWidgets import QFrame, QVBoxLayout
#
# from Source.UI.Interface.TTSInterface.tts_generate_window import TTSGenerateWindow
#
#
# class TTSInterface(QFrame):
#     def __init__(self, parent):
#         super().__init__(parent)
#         from Source.main_window import MainWindow
#         # noinspection PyTypeChecker
#         self._main_window: MainWindow = parent
#         self.setObjectName("tts_interface")
#         self._vbox_layout: QVBoxLayout = QVBoxLayout(self)
#         self._init_tts_generate_window()
#         # self._project_title_edit_window: LineEditWindow | None = None
#
#     def refresh(self):
#         self._tts_generate_window.refresh()
#
#     def _init_tts_generate_window(self):
#         self._tts_generate_window: TTSGenerateWindow = TTSGenerateWindow(self._main_window)
#         self._vbox_layout.addWidget(self._tts_generate_window)
