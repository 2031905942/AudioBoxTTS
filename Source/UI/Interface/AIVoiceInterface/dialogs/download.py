# -*- coding: utf-8 -*-
"""
Download Model Choice Dialog

This module contains the dialog for selecting model download method.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QGridLayout
from qfluentwidgets import (
    BodyLabel, FluentIcon, MessageBoxBase,
    PrimaryPushButton, PushButton
)


def _wrap_path_for_label(path: str) -> str:
    """给路径插入零宽断点，避免对话框因长路径被撑宽。"""
    if not path:
        return ""
    # Allow line breaks after separators without changing what user sees.
    return path.replace("\\", "\\\u200b").replace("/", "/\u200b")


class DownloadModelChoiceDialog(MessageBoxBase):
    """下载模型方式选择弹窗（四个按钮，两行布局避免重叠）。"""

    def __init__(self, parent, save_dir: str):
        super().__init__(parent)
        self.choice: str | None = None  # mirror/direct/delete_env/cancel

        title = BodyLabel("准备下载模型", self)
        self.viewLayout.addWidget(title)

        content = BodyLabel(
            "环境依赖检测通过。\n\n"
            f"即将下载模型文件到:\n{_wrap_path_for_label(save_dir)}\n\n"
            "文件大小约 7GB，下载过程可以去做其他事情~请选择下载方式：\n"
            "若在公司网络环境，则具备外网环境，两种下载方式均可使用；\n"
            "若在家用网络环境，推荐使用\"镜像下载\"方式，速度更快更稳定。",
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

        # 自定义按钮（两行 2x2）
        btn_grid_host = QWidget(self.buttonGroup)
        grid = QGridLayout(btn_grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        mirror_btn = PrimaryPushButton(FluentIcon.DOWNLOAD, "国内镜像下载", btn_grid_host)
        direct_btn = PrimaryPushButton(FluentIcon.DOWNLOAD, "直连下载(公司网络可用)", btn_grid_host)
        delete_env_btn = PushButton(FluentIcon.DELETE, "删除环境依赖", btn_grid_host)
        cancel_btn = PushButton("取消", btn_grid_host)

        for b in (mirror_btn, direct_btn, delete_env_btn, cancel_btn):
            b.setMinimumWidth(170)
            b.setMinimumHeight(34)

        grid.addWidget(mirror_btn, 0, 0)
        grid.addWidget(direct_btn, 0, 1)
        grid.addWidget(delete_env_btn, 1, 0)
        grid.addWidget(cancel_btn, 1, 1)

        # 让 buttonGroup 有足够高度容纳两行按钮
        try:
            self.buttonGroup.setFixedHeight(24 + 34 + 12 + 34 + 24)
        except Exception:
            pass

        self.buttonLayout.addWidget(btn_grid_host, 1, Qt.AlignmentFlag.AlignVCenter)

        def _pick(v: str, accept: bool):
            self.choice = v
            if accept:
                self.accept()
            else:
                self.reject()

        mirror_btn.clicked.connect(lambda: _pick("mirror", True))
        direct_btn.clicked.connect(lambda: _pick("direct", True))
        delete_env_btn.clicked.connect(lambda: _pick("delete_env", False))
        cancel_btn.clicked.connect(lambda: _pick("cancel", False))

        # 控制弹窗宽度，避免路径/文本挤压按钮
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
