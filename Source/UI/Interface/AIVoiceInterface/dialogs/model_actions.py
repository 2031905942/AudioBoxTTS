"""
Model Actions Dialog

This module contains the dialog for local model actions.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QSizePolicy
from qfluentwidgets import (
    BodyLabel, FluentIcon, MessageBoxBase,
    PushButton, TransparentToolButton
)


class LocalModelActionsDialog(MessageBoxBase):
    """"使用本地模型"弹窗：包含"下载依赖和模型 / 加载模型"两个按钮。"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 顶部栏：标题 + 右上角关闭（×）
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title = BodyLabel("本地模型（IndexTTS2）", header)
        header_layout.addWidget(title, 0)
        header_layout.addStretch(1)

        try:
            close_icon = getattr(FluentIcon, "CLOSE")
        except Exception:
            close_icon = None
        try:
            close_btn = TransparentToolButton(close_icon or FluentIcon.CLOSE, header)
        except Exception:
            close_btn = TransparentToolButton(FluentIcon.DOCUMENT, header)
        close_btn.setToolTip("关闭")
        close_btn.setFixedSize(32, 32)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)

        self.viewLayout.addWidget(header)

        content = BodyLabel(
            "首次使用请先下载依赖和模型,下载完成后再加载模型到显存。\n"
            "若显存小于8GB则无法启用本地模型，显存10-12GB建议启用 FP16（半精度）模式以节省显存。",
            self,
        )
        content.setWordWrap(True)
        self.viewLayout.addWidget(content)

        # FP16（半精度）开关：由外部（AIVoiceInterface）根据机器配置智能决定默认值
        fp16_row = QWidget(self)
        fp16_layout = QHBoxLayout(fp16_row)
        fp16_layout.setContentsMargins(0, 0, 0, 0)
        fp16_layout.setSpacing(10)

        try:
            # 使用 qfluentwidgets 的 SwitchButton（更美观）
            from qfluentwidgets import SwitchButton

            self.fp16_checkbox = SwitchButton(fp16_row)
            try:
                self.fp16_checkbox.setOnText("FP16")
                self.fp16_checkbox.setOffText("FP16")
            except Exception:
                pass
            self.fp16_checkbox.setToolTip("FP16 通常更快、更省显存，质量损失很小。显存较小（例如 8GB）建议开启。")
        except Exception:
            self.fp16_checkbox = None

        self.fp16_hint_label = BodyLabel("", fp16_row)
        self.fp16_hint_label.setWordWrap(True)
        try:
            self.fp16_hint_label.setStyleSheet("color: #666666;")
        except Exception:
            pass

        if self.fp16_checkbox is not None:
            fp16_layout.addWidget(self.fp16_checkbox, 0)
        fp16_layout.addWidget(self.fp16_hint_label, 1)
        self.viewLayout.addWidget(fp16_row)

        # 清空默认按钮
        try:
            self.buttonLayout.removeWidget(self.yesButton)
            self.buttonLayout.removeWidget(self.cancelButton)
            self.yesButton.hide()
            self.cancelButton.hide()
        except Exception:
            pass

        btn_grid_host = QWidget(self.buttonGroup)
        grid = QGridLayout(btn_grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.download_btn = PushButton(FluentIcon.DOWNLOAD, "下载依赖和模型", btn_grid_host)
        self.load_model_btn = PushButton(FluentIcon.PLAY, "加载模型", btn_grid_host)

        for b in (self.download_btn, self.load_model_btn):
            b.setMinimumHeight(34)
            b.setMinimumWidth(180)

        grid.addWidget(self.download_btn, 0, 0)
        grid.addWidget(self.load_model_btn, 0, 1)

        try:
            self.buttonGroup.setFixedHeight(24 + 34 + 12 + 34 + 24)
        except Exception:
            pass

        self.buttonLayout.addWidget(btn_grid_host, 1, Qt.AlignmentFlag.AlignVCenter)

        try:
            self.widget.setMinimumWidth(660)
        except Exception:
            pass
