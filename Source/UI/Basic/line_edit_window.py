from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, Dialog, LineEdit, PrimaryPushButton, PushButton


class LineEditWindow(QWidget):
    confirm_signal: Signal = Signal(str)
    rename_signal: Signal = Signal(str, str)

    def __init__(self, title: str):
        super().__init__()
        self.setStyleSheet("background-color: white")
        self.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowStaysOnTopHint)

        self.route_key: str = ""

        self._confirm_shortcut: QShortcut = QShortcut(QKeySequence.StandardKey.InsertParagraphSeparator, self)
        self._confirm_shortcut.activated.connect(self.on_confirmed)

        self._cancel_shortcut: QShortcut = QShortcut(QKeySequence.StandardKey.Cancel, self)
        self._cancel_shortcut.activated.connect(self.close)

        self.vbox_layout: QVBoxLayout = QVBoxLayout(self)
        self.hbox_layout: QHBoxLayout = QHBoxLayout()

        self._text_label: BodyLabel = BodyLabel(self)
        self._text_label.setText(title)

        self.line_edit: LineEdit = LineEdit(self)
        self.line_edit.setClearButtonEnabled(True)

        self._confirm_button: PrimaryPushButton = PrimaryPushButton(self)
        self._confirm_button.setText("确认")
        self._confirm_button.setMinimumWidth(100)
        self._confirm_button.clicked.connect(self.on_confirmed)

        self._cancel_button: PushButton = PushButton(self)
        self._cancel_button.setText("取消")
        self._cancel_button.setMinimumWidth(100)
        self._cancel_button.clicked.connect(self.close)

        self.vbox_layout.addWidget(self._text_label)
        self.vbox_layout.addWidget(self.line_edit)
        self.hbox_layout.addWidget(self._confirm_button)
        self.hbox_layout.addWidget(self._cancel_button)
        self.vbox_layout.addLayout(self.hbox_layout)

        self.show()

    def on_confirmed(self):
        if not self.line_edit.text():
            dialog: Dialog = Dialog("提醒", "请输入有效的名称", self)
            return dialog.exec()
        self.confirm_signal.emit(self.line_edit.text())
        self.rename_signal.emit(self.route_key, self.line_edit.text())
        self.close()
