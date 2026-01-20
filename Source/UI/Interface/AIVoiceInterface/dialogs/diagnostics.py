"""
Diagnostics Dialog

This module contains the model diagnostics information dialog.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget, QHBoxLayout
from qfluentwidgets import BodyLabel, PlainTextEdit, PushButton


class ModelDiagnosticsDialog(QDialog):
    """模型诊断信息窗口（可关闭，用于调试）。"""

    def __init__(self, parent, title: str, details: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        try:
            self.setMinimumWidth(720)
            self.setMinimumHeight(520)
        except Exception:
            pass

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = BodyLabel(title, self)
        layout.addWidget(header)

        # 使用只读文本框承载详细信息（便于复制）
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
