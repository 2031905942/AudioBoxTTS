from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition


class ResultInfoBar:
    def __init__(self, info_bar_type: str, title: str, content: str, parent: QWidget):
        if info_bar_type == "success":
            InfoBar.success(title=title, content=content, orient=Qt.Horizontal, position=InfoBarPosition.TOP, duration=5000, parent=parent)
        elif info_bar_type == "warning":
            InfoBar.warning(title=title, content=content, orient=Qt.Horizontal, position=InfoBarPosition.TOP, duration=10000, parent=parent)
        elif info_bar_type == "error":
            InfoBar.error(title=title, content=content, duration=5000, orient=Qt.Horizontal, position=InfoBarPosition.TOP, parent=parent)
