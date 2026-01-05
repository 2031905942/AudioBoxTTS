from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QSizePolicy

from qfluentwidgets import BodyLabel, ProgressBar, PushButton


class ProgressBarWindow(QWidget):
    cancel_signal: Signal = Signal()

    def __init__(self, parent):
        super().__init__()
        self.parent_widget: QWidget = parent
        self.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.timer: QTimer = QTimer(self)
        self.timer.start(20)
        # noinspection PyUnresolvedReferences
        self.timer.timeout.connect(self._refresh_gui)
        self.setStyleSheet("ProgressBarWindow { background-color: white }")
        self.vbox_layout = QVBoxLayout(self)
        self.hbox_layout = QHBoxLayout()
        self._progress_bar = ProgressBar(self)
        self._text = "处理中..."
        self._text_label = BodyLabel(self)
        self._text_label.setText(self._text)
        self._text_label.setWordWrap(True)
        self._text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._show_counter = True
        self._total_count: int = 0
        self._current_count: int = 0
        self._cancel_button = PushButton(self)
        self._cancel_button.setText("取消")
        self._cancel_button.setDisabled(False)
        self._cancel_button.clicked.connect(self.on_canceled)

        self.hbox_layout.addWidget(self._text_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.hbox_layout.addWidget(self._cancel_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.vbox_layout.addLayout(self.hbox_layout)
        self.vbox_layout.addWidget(self._progress_bar)

        # 固定宽度，避免因长日志文本导致窗口“无限变宽”超出屏幕
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            width = min(560, int(avail.width() * 0.78))
        else:
            width = 560

        self.setFixedWidth(max(360, width))
        self.resize(self.width(), 110)
        self.move(
            self.parent_widget.x() + (self.parent_widget.width() - self.width()) / 2,
            self.parent_widget.y() + (self.parent_widget.height() - self.height()) / 2,
        )
        self.show()

    def set_text(self, text: str):
        self._text = text

    def set_total_count(self, total_count: int):
        self._total_count = max(0, total_count)
        self._progress_bar.setMaximum(self._total_count)

    def set_show_counter(self, show: bool):
        self._show_counter = bool(show)

    def set_current_count(self, current_count: int):
        self._current_count = min(self._total_count, max(0, current_count))

    def set_enable_cancel(self, enable: bool):
        self._cancel_button.setDisabled(not enable)

    def on_canceled(self):
        self._cancel_button.setDisabled(True)
        self.cancel_signal.emit()

    def _refresh_gui(self):
        self._progress_bar.setValue(self._current_count)
        if self._show_counter and self._total_count > 0:
            self._text_label.setText(f"{self._text}\n{self._current_count}/{self._total_count}")
        else:
            self._text_label.setText(self._text)
