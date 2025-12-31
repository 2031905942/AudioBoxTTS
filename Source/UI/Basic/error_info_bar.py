from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from qfluentwidgets import InfoBar, InfoBarPosition


class ErrorInfoBar:
    INFO_BAR_TITLE = "错误"

    def __init__(self, content: str, parent: QWidget):
        InfoBar.error(title=ErrorInfoBar.INFO_BAR_TITLE, content=content, orient=Qt.Horizontal, position=InfoBarPosition.BOTTOM_RIGHT, duration=600000, parent=parent)
