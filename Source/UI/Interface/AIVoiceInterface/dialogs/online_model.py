"""
Online Model Dialog

This module contains the dialog for online model selection and API management.
"""

from qfluentwidgets import BodyLabel, MessageBoxBase


class OnlineModelDialog(MessageBoxBase):
    """"使用线上模型"弹窗（占位）：后续接入 API 管理与模型选择逻辑。"""

    def __init__(self, parent=None):
        super().__init__(parent)

        title = BodyLabel("线上模型", self)
        self.viewLayout.addWidget(title)

        content = BodyLabel(
            "这里将用于：\n"
            "- 管理第三方 TTS API（Key/Token/区域等）\n"
            "- 选择/绑定对应的线上模型（音色/声音复刻）\n\n"
            "该弹窗内部逻辑稍后实现。",
            self,
        )
        content.setWordWrap(True)
        self.viewLayout.addWidget(content)

        # 仅保留一个关闭按钮
        try:
            self.yesButton.setText("关闭")
            self.cancelButton.hide()
        except Exception:
            pass

        try:
            self.widget.setMinimumWidth(620)
        except Exception:
            pass
