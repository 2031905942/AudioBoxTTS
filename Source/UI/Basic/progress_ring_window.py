from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import BodyLabel, IndeterminateProgressRing, PushButton


class ProgressRingWindow(QWidget):
    cancel_signal: Signal = Signal()

    def __init__(self, parent):
        super().__init__()
        self.parent_widget: QWidget = parent
        self.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowStaysOnTopHint)

        self.setStyleSheet("ProgressRingWindow { background-color: white }")
        self.vbox_layout = QVBoxLayout(self)
        self.hbox_layout = QHBoxLayout()

        self._spinner = IndeterminateProgressRing(self)
        self._spinner.setFixedSize(30, 30)
        self._text = "处理中..."
        self._text_label = BodyLabel(self)
        self._text_label.setText(self._text)
        self._cancel_button = PushButton(self)
        self._cancel_button.setText("取消")
        self._cancel_button.setDisabled(False)
        self._cancel_button.clicked.connect(self.on_canceled)

        self.hbox_layout.addWidget(self._spinner, alignment=Qt.AlignHCenter | Qt.AlignmentFlag.AlignLeft)
        self.hbox_layout.addWidget(self._text_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.hbox_layout.addWidget(self._cancel_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.vbox_layout.addLayout(self.hbox_layout)
        self.resize(400, 80)
        self.move(self.parent_widget.x() + (self.parent_widget.width() - self.width()) / 2, self.parent_widget.y() + (self.parent_widget.height() - self.height()) / 2)
        self.show()

    def set_text(self, text: str):
        self._text = text
        self._text_label.setText(self._text)

    def set_enable_cancel(self, enable: bool):
        self._cancel_button.setDisabled(not enable)

    def on_canceled(self):
        self._cancel_button.setDisabled(True)
        self.cancel_signal.emit()
