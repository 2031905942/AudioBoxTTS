# -*- coding: utf-8 -*-
"""
Delete Assets Dialog

This module contains the dialog for deleting model files and environment dependencies.
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


class DeleteAssetsChoiceDialog(MessageBoxBase):
    """删除资源选择弹窗（避免 MessageBox 插入按钮导致重叠）。

    choice:
        - delete_model: 删除模型文件
        - delete_env: 删除环境依赖
        - cancel: 取消
    """

    def __init__(self, parent, save_dir: str, env_action: str = "delete"):
        super().__init__(parent)
        self.choice: str | None = None

        action = str(env_action).lower()

        title_text = "删除依赖和/或模型"
        content_text = (
            "请选择要删除的内容：\n\n"
            f"模型目录: {_wrap_path_for_label(save_dir)}\n"
            "独立环境: Runtime/IndexTTS2/.venv\n\n"
            "删除模型文件后，需重新下载才能使用语音合成功能；\n"
        )

        if action == "download":
            title_text = "依赖缺失"
            content_text = (
                "检测到模型文件已完整，但运行所需的 IndexTTS2 独立环境依赖缺失。\n\n"
                "推荐：点击\"下载环境依赖\"进行安装（不会影响已下载的模型文件）。\n\n"
                f"模型目录: {_wrap_path_for_label(save_dir)}\n"
                "独立环境: Runtime/IndexTTS2/.venv\n\n"
                "如确实不再使用，也可以选择删除模型文件以释放磁盘空间。"
            )

        title = BodyLabel(title_text, self)
        self.viewLayout.addWidget(title)

        content = BodyLabel(content_text, self)
        content.setWordWrap(True)
        self.viewLayout.addWidget(content)

        # 移除默认 yes/cancel，使用自定义布局
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

        # 视觉引导：尽量不要删除 -> 删除按钮用白色，取消按钮用蓝色
        delete_model_btn: QWidget

        env_btn_icon = FluentIcon.DELETE
        env_btn_text = "删除环境依赖"
        env_choice_value = "delete_env"
        if str(env_action).lower() == "download":
            env_btn_icon = FluentIcon.DOWNLOAD
            env_btn_text = "下载环境依赖"
            env_choice_value = "download_env"

        if action == "delete":
            delete_model_btn = PushButton(FluentIcon.DELETE, "删除模型文件", btn_grid_host)
            delete_env_btn = PushButton(env_btn_icon, env_btn_text, btn_grid_host)
            cancel_btn = PrimaryPushButton("取消", btn_grid_host)
        else:
            # 下载依赖场景：保持"下载"为主动作（蓝色）
            delete_model_btn = PushButton(FluentIcon.DELETE, "删除模型文件", btn_grid_host)
            delete_env_btn = PrimaryPushButton(env_btn_icon, env_btn_text, btn_grid_host)
            cancel_btn = PushButton("取消", btn_grid_host)

        for b in (delete_model_btn, delete_env_btn, cancel_btn):
            b.setMinimumWidth(180)
            b.setMinimumHeight(34)

        grid.addWidget(delete_model_btn, 0, 0)
        grid.addWidget(delete_env_btn, 0, 1)
        # 取消按钮单独一行，跨两列，避免窄屏挤压
        grid.addWidget(cancel_btn, 1, 0, 1, 2)

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

        delete_model_btn.clicked.connect(lambda: _pick("delete_model", True))
        delete_env_btn.clicked.connect(lambda: _pick(env_choice_value, False))
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
