"""Text Report Dialog

Minimal dialog for showing long, copyable multi-line reports.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget, QHBoxLayout
from qfluentwidgets import BodyLabel, PlainTextEdit, PushButton


class TextReportDialog(QDialog):
    """通用文本报告窗口（只读，可复制）。"""

    def __init__(self, parent, title: str, details: str):
        super().__init__(parent)
        self.setWindowTitle(title)

        try:
            self.setMinimumWidth(760)
            self.setMinimumHeight(560)
        except Exception:
            pass

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = BodyLabel(title, self)
        layout.addWidget(header)

        text = PlainTextEdit(self)
        text.setReadOnly(True)
        text.setPlainText(details)
        layout.addWidget(text, 1)

        btn_row = QWidget(self)
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()
        close_btn = PushButton("关闭", btn_row)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addWidget(btn_row)
