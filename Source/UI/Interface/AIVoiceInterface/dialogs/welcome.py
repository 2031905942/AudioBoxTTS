"""
Welcome Dialog

This module contains the welcome dialog shown on first use of AI Voice.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QGridLayout, QSizePolicy, QFrame
from qfluentwidgets import (
    BodyLabel, FluentIcon, MessageBoxBase,
    PrimaryPushButton, PushButton, TitleLabel, TextBrowser
)

from Source.Utility.dev_config_utility import dev_config_utility


class AIVoiceWelcomeDialog(MessageBoxBase):
    """首次进入 AI语音 的欢迎弹窗（非模态，不阻塞背景）。"""

    def __init__(self, parent, on_start_guide):
        super().__init__(parent)
        self._on_start_guide = on_start_guide

        title = TitleLabel("欢迎使用，", self)
        # MessageBoxBase 的 viewLayout 会把第一个 widget 纵向拉伸，
        # 这里固定标题高度，避免出现"标题与正文之间超大空白"。
        try:
            title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            title.setFixedHeight(title.sizeHint().height())
        except Exception:
            pass
        self.viewLayout.addWidget(title)

        # 使用 Markdown 提升可读性（Qt6 原生支持 setMarkdown）
        md = (
            "该 **AI 语音合成功能** 基于 IndexTTS2 开源模型，部署在本地电脑，可以把文本合成为自然语音，并支持通过参考音频复刻音色与风格。\n\n"

            "**快速开始** 🎯\n\n"
            "1. ⬇️ 下载依赖和模型并加载\n"
            "2. 👤 选择/创建角色\n"
            "3. 🎧 导入参考音频\n"
            "4. ✍️ 输入合成文本\n"
            "5. 🔊 生成并在历史记录批量试听/保存\n\n"

            "**温馨提示** 💡\n\n"
            "- 建议具备 **NVIDIA 独立显卡** ，并且显卡的显存在 10GB 以上\n"
            "- 确保磁盘空间充足，下载独立依赖和模型分别占约 7GB 空间大小。没事，下载完后有独立按钮支持删除功能。\n"
            "- 首次使用建议点击下方 **开始快速指引** 按钮进入快速指引环节。\n"
        )

        content = TextBrowser(self)
        content.setReadOnly(True)
        content.setOpenExternalLinks(True)
        try:
            content.setFrameShape(QFrame.Shape.NoFrame)
        except Exception:
            pass
        content.setMarkdown(md)

        # 适度放大字号（不引入新颜色/主题）
        try:
            content.setStyleSheet("QTextBrowser{font-size: 12pt;}")
        except Exception:
            pass

        # 尽量一次性展示完整内容：隐藏滚动条并把内容区高度撑开
        try:
            content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        except Exception:
            pass

        try:
            text_width = 720
            content.setMinimumWidth(text_width)
            doc = content.document()
            doc.setTextWidth(text_width)
            doc.adjustSize()
            doc_h = float(doc.size().height())
            content.setFixedHeight(max(260, int(doc_h) + 12))
        except Exception:
            # 最差情况下给一个更大的高度，减少滚动出现
            try:
                content.setMinimumHeight(320)
            except Exception:
                pass

        self.viewLayout.addWidget(content)

        # 提升弹窗整体高度，避免显示原生滚动条
        try:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                h = min(640, int(avail.height() * 0.76))
            else:
                h = 560
            self.widget.setMinimumHeight(max(440, h))
        except Exception:
            pass

        # 清空默认按钮
        try:
            self.buttonLayout.removeWidget(self.yesButton)
            self.buttonLayout.removeWidget(self.cancelButton)
            self.yesButton.hide()
            self.cancelButton.hide()
        except Exception:
            pass

        btn_host = QWidget(self.buttonGroup)
        grid = QGridLayout(btn_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        try:
            guide_icon = getattr(FluentIcon, "GUIDE")
            start_btn = PrimaryPushButton(guide_icon, "开始快速指引", btn_host)
        except Exception:
            start_btn = PrimaryPushButton("开始快速指引", btn_host)
        ok_btn = PushButton("OK，不再显示", btn_host)
        for b in (start_btn, ok_btn):
            b.setMinimumWidth(170)
            b.setMinimumHeight(34)

        grid.addWidget(start_btn, 0, 0)
        grid.addWidget(ok_btn, 0, 1)

        start_btn.clicked.connect(self._handle_start)
        ok_btn.clicked.connect(self._handle_ok)

        try:
            self.buttonGroup.setFixedHeight(24 + 34 + 24)
        except Exception:
            pass
        self.buttonLayout.addWidget(btn_host, 1, Qt.AlignmentFlag.AlignVCenter)

        try:
            self.widget.setMinimumWidth(780)
        except Exception:
            pass

    def _handle_start(self):
        try:
            if callable(self._on_start_guide):
                self._on_start_guide()
        finally:
            self.close()

    def _handle_ok(self):
        # 仅当用户点击"OK，不再显示"时，才写入本地覆盖配置（force=false）
        try:
            dev_config_utility.set_force_ai_voice_welcome_every_time(False)
        except Exception:
            pass
        self.close()
