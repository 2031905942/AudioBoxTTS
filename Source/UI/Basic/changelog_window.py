from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from qfluentwidgets import BodyLabel, ScrollArea


class ChangelogWindow(QWidget):
    close_signal = Signal()

    def __init__(self, changelog: str):
        super().__init__()

        self.setWindowTitle("更新日志")
        self.setStyleSheet("background-color: white")

        self._layout: QVBoxLayout = QVBoxLayout(self)

        self._changelog_label = BodyLabel(changelog, self)
        self._changelog_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._changelog_scroll_area = ScrollArea()
        self._changelog_scroll_area.setWidget(self._changelog_label)
        self._layout.addWidget(self._changelog_scroll_area)

        self._cancel_shortcut = QShortcut(QKeySequence.StandardKey.Cancel, self)
        self._cancel_shortcut.activated.connect(self.close)

        self.setFixedSize(1280, 720)

        self.show()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.close_signal.emit()
        event.accept()
