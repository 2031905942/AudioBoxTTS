"""
Environment Dialogs

This module contains dialogs related to environment checks and setup.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QGridLayout
from qfluentwidgets import (
    BodyLabel, FluentIcon, MessageBoxBase,
    PrimaryPushButton, PushButton
)


class EnvMissingInstallDialog(MessageBoxBase):
    """环境缺失弹窗（两按钮网格布局，避免 MessageBox 按钮重叠）。"""

    def __init__(self, parent, details: str):
        super().__init__(parent)
        self.choice: str | None = None  # install/cancel

        title = BodyLabel("下载独立的环境依赖", self)
        self.viewLayout.addWidget(title)

        content = BodyLabel(
            "当前设备配置能够满足运行要求（可在终端查看检测输出），\n"
            "检测到运行所需的 Python 依赖未下载。\n"
            f"({details})\n\n"
            "是否立即下载依赖？下载过程可以去做其他事情~",
            self,
        )
        content.setWordWrap(True)
        self.viewLayout.addWidget(content)

        # 清空默认按钮布局里的两个按钮
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

        install_btn = PrimaryPushButton(FluentIcon.DOWNLOAD, "下载依赖", btn_grid_host)
        cancel_btn = PushButton("取消", btn_grid_host)

        for b in (install_btn, cancel_btn):
            b.setMinimumWidth(180)
            b.setMinimumHeight(34)

        grid.addWidget(install_btn, 0, 0)
        grid.addWidget(cancel_btn, 0, 1)

        try:
            self.buttonGroup.setFixedHeight(24 + 34 + 24)
        except Exception:
            pass

        self.buttonLayout.addWidget(btn_grid_host, 1, Qt.AlignmentFlag.AlignVCenter)

        def _pick(v: str, accept: bool):
            self.choice = v
            if accept:
                self.accept()
            else:
                self.reject()

        install_btn.clicked.connect(lambda: _pick("install", True))
        cancel_btn.clicked.connect(lambda: _pick("cancel", False))

        try:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                w = min(820, int(avail.width() * 0.82))
            else:
                w = 780
            self.widget.setMinimumWidth(max(620, w))
        except Exception:
            self.widget.setMinimumWidth(720)


class IndexTTSPreflightDialog(MessageBoxBase):
    """IndexTTS2 下载前设备预检弹窗。

    - 若存在阻断项：仅允许关闭
    - 若仅存在建议项：允许继续/取消
    """

    def __init__(self, parent, report_text: str, can_continue: bool):
        super().__init__(parent)
        self.choice: str | None = None  # continue/cancel/close

        title = BodyLabel("运行设备检测", self)
        self.viewLayout.addWidget(title)

        content = BodyLabel(report_text, self)
        content.setWordWrap(True)
        self.viewLayout.addWidget(content)

        # 清空默认按钮布局里的两个按钮
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

        if can_continue:
            continue_btn = PrimaryPushButton(FluentIcon.ACCEPT, "继续下载", btn_grid_host)
            cancel_btn = PushButton("取消", btn_grid_host)

            for b in (continue_btn, cancel_btn):
                b.setMinimumWidth(180)
                b.setMinimumHeight(34)

            grid.addWidget(continue_btn, 0, 0)
            grid.addWidget(cancel_btn, 0, 1)

            def _pick(v: str, accept: bool):
                self.choice = v
                if accept:
                    self.accept()
                else:
                    self.reject()

            continue_btn.clicked.connect(lambda: _pick("continue", True))
            cancel_btn.clicked.connect(lambda: _pick("cancel", False))

            try:
                self.buttonGroup.setFixedHeight(24 + 34 + 24)
            except Exception:
                pass
        else:
            close_btn = PushButton("关闭", btn_grid_host)
            close_btn.setMinimumWidth(180)
            close_btn.setMinimumHeight(34)

            grid.addWidget(close_btn, 0, 0)

            def _close():
                self.choice = "close"
                self.reject()

            close_btn.clicked.connect(_close)
            try:
                self.buttonGroup.setFixedHeight(24 + 34 + 24)
            except Exception:
                pass

        self.buttonLayout.addWidget(btn_grid_host, 1, Qt.AlignmentFlag.AlignVCenter)

        try:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                w = min(920, int(avail.width() * 0.86))
            else:
                w = 820
            self.widget.setMinimumWidth(max(680, w))
        except Exception:
            self.widget.setMinimumWidth(760)
