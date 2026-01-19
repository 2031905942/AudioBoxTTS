"""
AI 语音界面 - IndexTTS2

"""
import time

import os

from typing import Optional

from PySide6.QtCore import QStandardPaths, QUrl, QRunnable, QThreadPool, QObject, Signal, Slot, Qt, QTimer, QEvent, QRect
from PySide6.QtGui import QGuiApplication, QShortcut, QKeySequence, QAction
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QVBoxLayout, QWidget, QSizePolicy, QStackedLayout, QStackedWidget, QLabel, QDialog
)
from qfluentwidgets import (
    BodyLabel, CardWidget, FluentIcon, InfoBar, InfoBarPosition,
    MessageBox, MessageBoxBase, PlainTextEdit, PrimaryPushButton, ProgressBar, PushButton, RadioButton,
    Slider, StrongBodyLabel, TitleLabel,
    ToolTipFilter, ToolTipPosition, TransparentToolButton,
    TeachingTip, TeachingTipTailPosition,
    TextBrowser, TabCloseButtonDisplayMode,
)

from Source.Utility.indextts_preflight_utility import (
    IndexTTSPreflightUtility,
)

from Source.Utility.indextts_utility import IndexTTSUtility
from Source.Utility.config_utility import config_utility, ProjectData
from Source.Utility.dev_config_utility import dev_config_utility
from Source.UI.Interface.AIVoiceInterface.character_manager import CharacterManager, Character
from Source.UI.Interface.AIVoiceInterface.character_dialog import CharacterDialog
from Source.UI.Interface.AIVoiceInterface.character_list_widget import CharacterListWidget
from Source.UI.Interface.AIVoiceInterface.batch_delete_characters_dialog import BatchDeleteCharactersDialog
from Source.UI.Interface.AIVoiceInterface.audio_player_widget import ReferenceAudioPlayerWidget, ResultAudioPlayerWidget
from Source.UI.Interface.AIVoiceInterface.history_window import AIVoiceHistoryWindow
from Source.Utility.tts_history_utility import tts_history_store, TTSHistoryStore
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.UI.Basic.project_tab_bar import ProjectTabBar, ProjectTabItem


class EnvCheckSignals(QObject):
    """环境检测信号类"""
    finished = Signal(bool, str)  # is_ready, message


class EnvCheckWorker(QRunnable):
    """环境检测后台任务"""
    
    def __init__(self):
        super().__init__()
        self.signals = EnvCheckSignals()
    
    def run(self):
        """在后台线程执行环境检测"""
        try:
            from Source.Job.indextts_env_job import IndexTTSEnvJob
            is_ready, msg = IndexTTSEnvJob.check_env_ready()
            self.signals.finished.emit(is_ready, msg)
        except Exception as e:
            self.signals.finished.emit(False, f"检测失败: {str(e)}")


class DragDropOverlay(QWidget):
    """全界面拖拽遮罩层。

    目的：
    - 拦截拖拽事件，避免输入框等子控件抢占 drop（把路径写进文本框）。
    - 在遮罩层上绘制橙色虚线框 + 图标 + 提示文本。
    """

    audio_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setVisible(False)
        # 透明背景，但仍然接收 drag/drop 事件
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    @staticmethod
    def _is_audio_url(event) -> Optional[str]:
        if not event.mimeData().hasUrls():
            return None
        urls = event.mimeData().urls()
        if not urls:
            return None
        file_path = urls[0].toLocalFile()
        if not file_path:
            return None
        if file_path.lower().endswith((".wav", ".mp3", ".flac", ".ogg")):
            return file_path
        return None

    def dragEnterEvent(self, event):
        file_path = self._is_audio_url(event)
        if file_path:
            event.acceptProposedAction()
            self.show()
            self.raise_()
            self.update()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        file_path = self._is_audio_url(event)
        if file_path:
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.hide()
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        file_path = self._is_audio_url(event)
        self.hide()
        self.update()
        if file_path:
            event.acceptProposedAction()
            self.audio_dropped.emit(file_path)
            return
        event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isVisible():
            return

        from PySide6.QtGui import QPainter, QPen, QColor, QFont

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 橙色虚线框
        pen = QPen(QColor("#ff6b00"), 3, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 107, 0, 20))
        rect = self.rect().adjusted(8, 8, -8, -8)
        painter.drawRoundedRect(rect, 12, 12)

        # 中心图标 + 文本
        icon_size = 44
        icon = None
        try:
            icon = FluentIcon.MUSIC.icon()
        except Exception:
            icon = None

        cx = self.rect().center().x()
        cy = self.rect().center().y()

        if icon is not None:
            pm = icon.pixmap(icon_size, icon_size)
            painter.drawPixmap(cx - icon_size // 2, cy - icon_size // 2 - 28, pm)

        painter.setPen(QColor("#ff6b00"))
        font = QFont()
        font.setPointSize(11)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(self.rect().adjusted(16, 0, -16, 0), Qt.AlignmentFlag.AlignCenter,
                         "拖拽音频文件到此处导入参考音频")

        painter.setPen(QColor(120, 120, 120))
        font2 = QFont()
        font2.setPointSize(9)
        font2.setBold(False)
        painter.setFont(font2)
        sub_rect = self.rect().adjusted(16, 28, -16, 0)
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, "支持 wav / mp3 / flac / ogg")


class _ModalInputBlockerOverlay(QWidget):
    """透明输入拦截层：用于让 TeachingTip 流程表现为“模态”。

    设计目标：
    - 不增加视觉元素（完全透明）
    - 阻断主窗口内除 TeachingTip 外的点击/键盘操作
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setVisible(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._spotlight_target: QWidget | None = None
        self._spotlight_rect = None
        self._spotlight_radius = 10
        self._spotlight_margin = 8

        try:
            parent.installEventFilter(self)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self.setGeometry(self.parentWidget().rect())
        except Exception:
            pass
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass
        try:
            self.setFocus()
        except Exception:
            pass

    def set_spotlight_target(self, target: QWidget | None, margin: int = 8, radius: int = 10):
        """设置需要高亮的目标区域（镂空显示）。"""
        self._spotlight_target = target
        self._spotlight_margin = int(margin)
        self._spotlight_radius = int(radius)
        self._recompute_spotlight_rect()
        self.update()

    def _recompute_spotlight_rect(self):
        if self._spotlight_target is None:
            self._spotlight_rect = None
            return
        try:
            # 目标控件的全局矩形映射到 overlay 坐标
            top_left = self._spotlight_target.mapToGlobal(self._spotlight_target.rect().topLeft())
            bottom_right = self._spotlight_target.mapToGlobal(self._spotlight_target.rect().bottomRight())
            local_tl = self.mapFromGlobal(top_left)
            local_br = self.mapFromGlobal(bottom_right)
            r = QRect(local_tl, local_br).normalized()
            r = r.adjusted(-self._spotlight_margin, -self._spotlight_margin, self._spotlight_margin, self._spotlight_margin)
            self._spotlight_rect = r
        except Exception:
            self._spotlight_rect = None

    def eventFilter(self, obj, event):
        if obj == self.parentWidget():
            try:
                if event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
                    self.setGeometry(self.parentWidget().rect())
                    self._recompute_spotlight_rect()
            except Exception:
                pass
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        super().paintEvent(event)

        from PySide6.QtGui import QPainter, QColor, QPainterPath

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 说明：之前用 CompositionMode_Clear 在部分 Windows/显卡组合下会表现为“白板遮挡”，
        # 看不到高亮区域内容。这里改为只绘制“暗层路径减去高亮区域”，避免依赖 Clear 合成模式。
        try:
            if self._spotlight_rect is None:
                painter.fillRect(self.rect(), QColor(0, 0, 0, 140))
                return

            dim_path = QPainterPath()
            dim_path.addRect(self.rect())

            hole = QPainterPath()
            hole.addRoundedRect(self._spotlight_rect, self._spotlight_radius, self._spotlight_radius)

            dim_path = dim_path.subtracted(hole)
            painter.fillPath(dim_path, QColor(0, 0, 0, 140))
        except Exception:
            # 最差情况下也保证是“整体压暗”
            painter.fillRect(self.rect(), QColor(0, 0, 0, 140))

    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        event.accept()

    def keyPressEvent(self, event):
        event.accept()

    def keyReleaseEvent(self, event):
        event.accept()


class DownloadModelChoiceDialog(MessageBoxBase):
    """下载模型方式选择弹窗（四个按钮，两行布局避免重叠）。"""

    def __init__(self, parent, save_dir: str):
        super().__init__(parent)
        self.choice: str | None = None  # mirror/direct/delete_env/cancel

        title = BodyLabel("准备下载模型", self)
        self.viewLayout.addWidget(title)

        content = BodyLabel(
            "环境依赖检测通过。\n\n"
            f"即将下载模型文件到:\n{AIVoiceInterface._wrap_path_for_label(save_dir)}\n\n"
            "文件大小约 7GB，下载过程可以去做其他事情~请选择下载方式：\n"
            "若在公司网络环境，则具备外网环境，两种下载方式均可使用；\n"
            "若在家用网络环境，推荐使用“镜像下载”方式，速度更快更稳定。",
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


class LocalModelActionsDialog(MessageBoxBase):
    """“使用本地模型”弹窗：包含“下载依赖和模型 / 加载模型”两个按钮。"""

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
            "若显存较小（例如 8GB），建议启用 FP16（半精度）模式以节省显存。",
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


class OnlineModelDialog(MessageBoxBase):
    """“使用线上模型”弹窗（占位）：后续接入 API 管理与模型选择逻辑。"""

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


class AIVoiceWelcomeDialog(MessageBoxBase):
    """首次进入 AI语音 的欢迎弹窗（非模态，不阻塞背景）。"""

    def __init__(self, parent, on_start_guide):
        super().__init__(parent)
        self._on_start_guide = on_start_guide

        title = TitleLabel("欢迎使用，", self)
        # MessageBoxBase 的 viewLayout 会把第一个 widget 纵向拉伸，
        # 这里固定标题高度，避免出现“标题与正文之间超大空白”。
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
        # 仅当用户点击“OK，不再显示”时，才写入本地覆盖配置（force=false）
        try:
            dev_config_utility.set_force_ai_voice_welcome_every_time(False)
        except Exception:
            pass
        self.close()


class AIVoiceQuickGuideStepDialog(MessageBoxBase):
    """快速指引 - 单步弹窗（支持 下一步/跳过）。"""

    def __init__(self, parent, step_title: str, step_desc: str, step_index: int, step_total: int):
        super().__init__(parent)
        self.choice: str | None = None  # next/skip

        title = TitleLabel(f"快速指引（{step_index}/{step_total}）", self)
        self.viewLayout.addWidget(title)

        subtitle = StrongBodyLabel(step_title, self)
        self.viewLayout.addWidget(subtitle)

        content = BodyLabel(step_desc, self)
        content.setWordWrap(True)
        self.viewLayout.addWidget(content)

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
            next_icon = getattr(FluentIcon, "RIGHT_ARROW")
            next_btn = PrimaryPushButton(next_icon, "下一步", btn_host)
        except Exception:
            try:
                next_icon = getattr(FluentIcon, "ARROW_RIGHT")
                next_btn = PrimaryPushButton(next_icon, "下一步", btn_host)
            except Exception:
                next_btn = PrimaryPushButton("下一步", btn_host)
        skip_btn = PushButton("跳过", btn_host)

        for b in (next_btn, skip_btn):
            b.setMinimumWidth(150)
            b.setMinimumHeight(34)

        grid.addWidget(next_btn, 0, 0)
        grid.addWidget(skip_btn, 0, 1)

        next_btn.clicked.connect(self._handle_next)
        skip_btn.clicked.connect(self._handle_skip)

        try:
            self.buttonGroup.setFixedHeight(24 + 34 + 24)
        except Exception:
            pass
        self.buttonLayout.addWidget(btn_host, 1, Qt.AlignmentFlag.AlignVCenter)

        try:
            self.widget.setMinimumWidth(760)
        except Exception:
            pass

    def _handle_next(self):
        self.choice = "next"
        self.accept()

    def _handle_skip(self):
        self.choice = "skip"
        self.reject()


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
            f"模型目录: {AIVoiceInterface._wrap_path_for_label(save_dir)}\n"
            "独立环境: Runtime/IndexTTS2/.venv\n\n"
            "删除模型文件后，需重新下载才能使用语音合成功能；\n"
        )

        if action == "download":
            title_text = "依赖缺失"
            content_text = (
                "检测到模型文件已完整，但运行所需的 IndexTTS2 独立环境依赖缺失。\n\n"
                "推荐：点击“下载环境依赖”进行安装（不会影响已下载的模型文件）。\n\n"
                f"模型目录: {AIVoiceInterface._wrap_path_for_label(save_dir)}\n"
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
            # 下载依赖场景：保持“下载”为主动作（蓝色）
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


class AIVoiceInterface(QFrame):
    """AI 语音界面（IndexTTS2 版）v2.1

    新布局：
    - 顶部：TabBar（与项目页面同步）
    - 角色列表卡片（可展开/收起，网格布局）
    - 中部：三栏布局（音色参考 | 合成文本 | 生成结果）
    - 底部：情感控制
    """

    def __init__(self, parent):
        super().__init__(parent)
        from Source.main_window import MainWindow
        # noinspection PyTypeChecker
        self._main_window: MainWindow = parent

        self.setObjectName("ai_voice_interface")

        # AI 语音页的底色（各大组件/卡片之外的背景）
        try:
            self.setAutoFillBackground(True)
        except Exception:
            pass
        try:
            self.setStyleSheet("#ai_voice_interface { background-color: #e5e5e5; }")
        except Exception:
            pass

        # 当前项目ID
        self._current_project_id: Optional[str] = None

        # 按项目隔离的管理器字典
        self._character_managers: dict[str, CharacterManager] = {}
        self._history_stores: dict[str, TTSHistoryStore] = {}

        # 角色管理器（当前项目的，会根据Tab切换而变化）
        self._character_manager: Optional[CharacterManager] = None

        # 记录主窗口“当前项目”快照，供 TabBar 初始化后对齐
        try:
            self._preferred_project_id: Optional[str] = self._main_window.get_current_project_id()
        except Exception:
            self._preferred_project_id = None

        # 播放器
        self._player: Optional[QMediaPlayer] = None
        self._audio_output: Optional[QAudioOutput] = None
        
        # 参考音频播放器（独立）
        self._ref_player: Optional[QMediaPlayer] = None
        self._ref_audio_output: Optional[QAudioOutput] = None

        # 环境检测状态
        self._env_check_pending = False
        self._env_check_request_id = 0
        self._env_check_worker = None
        
        # 环境/模型是否就绪
        self._env_ready = False
        self._model_ready = False

        # 生成状态：用于区分“模型加载完成”和“语音合成完成”都走 job_completed(True)
        self._synthesis_in_progress = False

        # 启用拖拽支持
        self.setAcceptDrops(True)
        self._drag_overlay = DragDropOverlay(self)
        self._drag_overlay.audio_dropped.connect(self._on_audio_dropped)
        self._drag_overlay.hide()

        self._init_ui()
        self._connect_signals()

        # 首次使用引导（运行期缓存，避免多次弹出/被 GC）
        self._welcome_dialog = None
        self._quick_guide_dialog = None
        self._quick_guide_step_index = 0
        self._welcome_shown_runtime = False

        # 历史记录窗口（非模态）
        self._history_window = None
        self._history_pending = None

    @staticmethod
    def _wrap_path_for_label(path: str) -> str:
        """给路径插入零宽断点，避免对话框因长路径被撑宽。"""
        if not path:
            return ""
        # Allow line breaks after separators without changing what user sees.
        return path.replace("\\", "\\\u200b").replace("/", "/\u200b")

    @staticmethod
    def _tune_message_box(msg: MessageBox) -> None:
        """统一 MessageBox 宽度与按钮尺寸，避免按钮文字显示不全。"""
        try:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                min_w = min(760, int(avail.width() * 0.78))
                max_w = int(avail.width() * 0.90)
            else:
                min_w, max_w = 720, 980

            msg.setMinimumWidth(max(560, min_w))
            msg.setMaximumWidth(max_w)
        except Exception:
            pass

        # 统一按钮尺寸
        for btn in (getattr(msg, "yesButton", None), getattr(msg, "cancelButton", None)):
            if btn is None:
                continue
            try:
                btn.setMinimumWidth(150)
                btn.setMinimumHeight(34)
            except Exception:
                pass

        # 处理插入到 buttonLayout 的额外按钮
        try:
            layout = getattr(msg, "buttonLayout", None)
            if layout is not None:
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    w = item.widget() if item is not None else None
                    if w is None:
                        continue
                    try:
                        w.setMinimumWidth(150)
                        w.setMinimumHeight(34)
                    except Exception:
                        pass
        except Exception:
            pass

    def dragEnterEvent(self, event):
        """处理拖拽进入事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.wav', '.mp3', '.flac', '.ogg')):
                event.acceptProposedAction()
                # 显示全界面遮罩层（拦截 drop，避免文本框等抢占）
                try:
                    self._drag_overlay.setGeometry(self.rect())
                    self._drag_overlay.show()
                    self._drag_overlay.raise_()
                except Exception:
                    pass
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        """处理拖拽离开事件"""
        try:
            self._drag_overlay.hide()
        except Exception:
            pass
        self.update()

    def dropEvent(self, event):
        """处理拖拽放下事件"""
        # 理论上 drop 会被 overlay 接走；这里兜底处理
        try:
            self._drag_overlay.hide()
        except Exception:
            pass
        self.update()
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.wav', '.mp3', '.flac', '.ogg')):
                self._on_audio_dropped(file_path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            self._drag_overlay.setGeometry(self.rect())
        except Exception:
            pass

    def _init_ui(self):
        """初始化 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 12, 20, 12)
        main_layout.setSpacing(12)

        # ========== TabBar（与项目页面同步）==========
        self._create_tab_bar(main_layout)

        # ========== 顶部：角色列表 + 模型选择 ==========
        self._create_top_section(main_layout)

        # ========== 中部三栏布局 ==========
        self._create_main_content(main_layout)

        # ========== 底部情感控制 ==========
        self._create_emotion_panel(main_layout)

        # 添加弹性空间
        main_layout.addStretch()

    def _create_tab_bar(self, parent_layout: QVBoxLayout):
        """创建项目TabBar（只读，与项目页面同步）"""
        self._ai_voice_tab_bar = ProjectTabBar(self)
        self._ai_voice_tab_bar.setMovable(False)  # 不允许拖拽
        self._ai_voice_tab_bar.setScrollable(True)
        self._ai_voice_tab_bar.setTabMaximumWidth(220)
        self._ai_voice_tab_bar.setMinimumWidth(70)
        self._ai_voice_tab_bar.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.NEVER)  # 不显示关闭按钮
        self._ai_voice_tab_bar.setAddButtonVisible(False)  # 不显示添加按钮
        self._ai_voice_tab_bar.currentChanged.connect(self._on_ai_voice_tab_changed)
        parent_layout.addWidget(self._ai_voice_tab_bar)

        # 创建 Tab 后立即从项目列表初始化（保证后续 _create_top_section 有可用的 _character_manager）
        self.init_tabs_from_projects()

        # 对齐到主窗口当前项目；若不可用则回退到第一个项目
        preferred = str(getattr(self, "_preferred_project_id", None) or "")
        if preferred and self._find_tab_index(preferred) >= 0:
            try:
                self.on_project_tab_switched(preferred)
            except Exception:
                pass
            # on_project_tab_switched 会触发 currentChanged -> _switch_to_project
            return

        if len(self._ai_voice_tab_bar.items) > 0:
            try:
                self._ai_voice_tab_bar.setCurrentIndex(0)
            except Exception:
                pass
            try:
                self._switch_to_project(self._ai_voice_tab_bar.items[0].routeKey())
            except Exception:
                pass
            return

        # 没有任何项目时：回退到旧的全局角色/历史存储，保持页面可用
        try:
            self._character_manager = CharacterManager()
        except Exception:
            self._character_manager = None

    def _on_ai_voice_tab_changed(self, index: int):
        """AI语音页面Tab切换时调用"""
        if index < 0 or index >= len(self._ai_voice_tab_bar.items):
            return
        project_id = self._ai_voice_tab_bar.items[index].routeKey()
        self._switch_to_project(project_id)

        # 同步“项目”页选中（避免两边项目不一致）
        try:
            p = getattr(self._main_window, "project_interface", None)
            bar = getattr(p, "project_tab_bar", None)
            if bar is not None:
                target_index = -1
                try:
                    for i, item in enumerate(getattr(bar, "items", [])):
                        if item.routeKey() == project_id:
                            target_index = int(i)
                            break
                except Exception:
                    target_index = -1

                if target_index >= 0:
                    cur = int(bar.currentIndex())
                    if cur != int(target_index):
                        bar.setCurrentIndex(int(target_index))
        except Exception:
            pass

    def _switch_to_project(self, project_id: str):
        """切换到指定项目"""
        if self._current_project_id == project_id:
            # 防止“Tab 重建/字典重建”后仍持有旧 manager，导致 UI 显示串台
            try:
                mgr = self._character_managers.get(project_id)
                if mgr is not None and self._character_manager is mgr:
                    return
            except Exception:
                return

        self._current_project_id = project_id

        # 获取或创建该项目的 CharacterManager
        if project_id not in self._character_managers:
            self._character_managers[project_id] = CharacterManager.create_for_project(project_id)
        self._character_manager = self._character_managers[project_id]

        # 让角色列表控件切到当前项目的数据源（否则 UI 仍绑定旧 manager）
        try:
            w = getattr(self, "character_list_widget", None)
            if w is not None and hasattr(w, "set_character_manager"):
                w.set_character_manager(self._character_manager)
        except Exception:
            pass

        # 获取或创建该项目的 TTSHistoryStore
        if project_id not in self._history_stores:
            self._history_stores[project_id] = TTSHistoryStore.create_for_project(project_id)

        # 更新角色列表（仅当 UI 已创建）
        try:
            if hasattr(self, "character_list_widget"):
                self._refresh_character_list()
        except Exception:
            pass

        # 清空生成结果（仅当输出区已创建）
        try:
            if hasattr(self, "_output_stack"):
                self._clear_output_state()
        except Exception:
            pass

        # 若历史窗口已打开，同步刷新（按当前项目 store）
        try:
            self._refresh_history_window_if_open()
        except Exception:
            pass

    def _clear_output_state(self):
        """清空生成结果状态"""
        try:
            self._output_wav_paths = ["", "", ""]
            for w in getattr(self, "output_player_widgets", []):
                w.set_audio_path("")
                try:
                    w.set_loading(False)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self._set_output_empty_state(True)
        except Exception:
            pass

    def _get_current_history_store(self) -> TTSHistoryStore:
        """获取当前项目的历史记录存储"""
        if self._current_project_id and self._current_project_id in self._history_stores:
            return self._history_stores[self._current_project_id]
        return tts_history_store  # 回退到全局的（向后兼容）

    # ==================== 项目同步接口 ====================

    def on_project_tab_added(self, project_id: str, title: str):
        """项目Tab添加时调用"""
        # 添加TabBar项
        tab_item = self._ai_voice_tab_bar.addTab(project_id, title, FluentIcon.MICROPHONE)
        tab_item.setAutoFillBackground(True)

        # 预创建该项目的管理器
        if project_id not in self._character_managers:
            self._character_managers[project_id] = CharacterManager.create_for_project(project_id)
        if project_id not in self._history_stores:
            self._history_stores[project_id] = TTSHistoryStore.create_for_project(project_id)

    def on_project_tab_removed(self, project_id: str):
        """项目Tab删除时调用"""
        # 查找并移除TabBar项
        index = self._find_tab_index(project_id)
        if index >= 0:
            self._ai_voice_tab_bar.removeTab(index)

        # 清理管理器
        self._character_managers.pop(project_id, None)
        self._history_stores.pop(project_id, None)

        # 如果删除的是当前项目，切换到第一个项目
        if self._current_project_id == project_id:
            self._current_project_id = None
            if len(self._ai_voice_tab_bar.items) > 0:
                first_project_id = self._ai_voice_tab_bar.items[0].routeKey()
                self._switch_to_project(first_project_id)
            else:
                try:
                    self._character_manager = CharacterManager()
                except Exception:
                    self._character_manager = None
                try:
                    w = getattr(self, "character_list_widget", None)
                    if w is not None and self._character_manager is not None and hasattr(w, "set_character_manager"):
                        w.set_character_manager(self._character_manager)
                    if hasattr(self, "character_list_widget"):
                        self._refresh_character_list()
                except Exception:
                    pass

    def on_project_tab_renamed(self, project_id: str, new_title: str):
        """项目Tab重命名时调用"""
        tab_item = self._ai_voice_tab_bar.tab(project_id)
        if tab_item:
            tab_item.setText(new_title)

    def on_project_tab_switched(self, project_id: str):
        """项目Tab切换时调用（来自项目页面的切换）"""
        index = self._find_tab_index(project_id)
        if index < 0:
            return

        # 关键修复：即便 index == currentIndex，也要确保内部 manager/UI 已绑定到该 project
        if index != self._ai_voice_tab_bar.currentIndex():
            self._ai_voice_tab_bar.setCurrentIndex(index)
            return

        # currentChanged 不会触发时（例如启动时默认 index 已是 0），这里手动切一次
        try:
            self._switch_to_project(project_id)
        except Exception:
            pass

    def on_project_tabs_swapped(self, index1: int, index2: int):
        """项目Tab顺序交换时调用"""
        # TabBar 不支持直接交换：这里选择重建一次，保证顺序与“项目”页一致。
        # 备注：即使不重建，上面的 _on_ai_voice_tab_changed 也已按 project_id 同步，避免 index 错配。
        try:
            current_project_id = str(getattr(self._main_window, "get_current_project_id")() or "")
        except Exception:
            current_project_id = ""

        try:
            self.init_tabs_from_projects()
        except Exception:
            return

        if current_project_id:
            try:
                self.on_project_tab_switched(current_project_id)
            except Exception:
                pass
        elif len(self._ai_voice_tab_bar.items) > 0:
            try:
                self._ai_voice_tab_bar.setCurrentIndex(0)
            except Exception:
                pass

    def _find_tab_index(self, project_id: str) -> int:
        """查找项目ID对应的Tab索引"""
        for i, item in enumerate(self._ai_voice_tab_bar.items):
            if item.routeKey() == project_id:
                return i
        return -1

    def init_tabs_from_projects(self):
        """从项目数据初始化所有Tab（启动时调用）"""
        # 清空旧 tab，避免重复初始化（阻止 currentChanged 回调触发切换逻辑）
        try:
            self._ai_voice_tab_bar.blockSignals(True)
        except Exception:
            pass

        try:
            while len(self._ai_voice_tab_bar.items) > 0:
                self._ai_voice_tab_bar.removeTab(0)
        except Exception:
            pass

        # 重建数据容器，避免保留已删除项目的数据
        try:
            self._character_managers = {}
            self._history_stores = {}
            self._character_manager = None
            self._current_project_id = None
        except Exception:
            pass

        project_data_dict = config_utility.get_project_data_dict()
        for project_id, project_data in project_data_dict.items():
            project_title = project_data.get(ProjectData.TITLE_CONFIG_NAME, "未命名")
            tab_item = self._ai_voice_tab_bar.addTab(project_id, project_title, FluentIcon.MICROPHONE)
            tab_item.setAutoFillBackground(True)

            # 预创建管理器
            self._character_managers[project_id] = CharacterManager.create_for_project(project_id)
            self._history_stores[project_id] = TTSHistoryStore.create_for_project(project_id)
        # 当前项目由 _create_tab_bar 或外部信号决定

        try:
            self._ai_voice_tab_bar.blockSignals(False)
        except Exception:
            pass
    
    def _create_top_section(self, parent_layout: QVBoxLayout):
        """创建顶部区域（角色列表 + 模型选择）"""
        top_widget = QWidget(self)
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(16)
        
        # === 左侧：角色列表（占 2/3 宽度）===
        # 兜底：确保一定有一个 manager（即使没有项目）
        if self._character_manager is None:
            try:
                self._character_manager = CharacterManager()
            except Exception:
                self._character_manager = None

        self.character_list_widget = CharacterListWidget(self._character_manager, self)
        self.character_list_widget.character_selected.connect(self._on_character_selected)
        self.character_list_widget.character_edit_requested.connect(self._on_character_edit)
        self.character_list_widget.character_delete_requested.connect(self._on_character_delete)
        self.character_list_widget.add_character_requested.connect(self._on_add_character)
        self.character_list_widget.import_from_wwise_requested.connect(self._on_import_from_wwise)
        try:
            self.character_list_widget.batch_delete_requested.connect(self._on_batch_delete_characters)
        except Exception:
            pass
        top_layout.addWidget(self.character_list_widget, 2)  # stretch factor 2
        
        # === 右侧：模型选择面板（占 1/3 宽度）===
        self._create_model_control_panel(top_layout)
        
        parent_layout.addWidget(top_widget)
    
    def _create_model_control_panel(self, parent_layout: QHBoxLayout):
        """创建模型选择面板"""
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor
        from PySide6.QtCore import QSize
        
        # 使用 CardWidget 包装
        panel = CardWidget(self)
        # 供 TeachingTip/spotlight 锚定“模型选择”整个区域（而非单按钮）
        self.model_control_panel_card = panel
        
        # 移除手动设置的阴影和背景色，使用 CardWidget 的默认主题样式
        # 这样可以保证在不同主题（亮/暗）下显示一致，且不会过亮
        
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 14)
        panel_layout.setSpacing(12)
        
        # 标题（模型加载后可点击查看诊断信息）
        self.model_control_title_btn = PushButton("模型选择", panel)
        self.model_control_title_btn.setEnabled(False)
        self.model_control_title_btn.setToolTip("")
        self.model_control_title_btn.setStyleSheet(
            """
            PushButton {
                border: none;
                padding: 0px;
                background: transparent;
                text-align: left;
            }
            PushButton:disabled {
                border: none;
                padding: 0px;
                background: transparent;
            }
            PushButton:hover:!disabled {
                text-decoration: underline;
            }
            """
        )
        try:
            self.model_control_title_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        except Exception:
            pass
        self.model_control_title_btn.clicked.connect(self._on_model_title_clicked)
        panel_layout.addWidget(self.model_control_title_btn)
        
        # 标记当前是否为删除模式
        self._is_delete_mode = False

        # 统一按钮样式（避免图标与文字重叠）
        self._model_btn_icon_size = QSize(16, 16)
        # 视觉降噪：使用更扁平、清爽的样式
        self._download_btn_style_download = """
            PushButton {
                border-radius: 14px;
                padding: 9px 16px;
                padding-left: 44px;
                font-size: 13px;
                font-weight: 500;
                background-color: transparent;
                border: 1px solid #e0e0e0;
            }
            PushButton:hover {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
            }
        """
        self._download_btn_style_delete = """
            PushButton {
                border-radius: 14px;
                padding: 9px 16px;
                padding-left: 44px;
                font-size: 13px;
                font-weight: 500;
                background-color: #fff4ce;
                border: 1px solid #d4a72c;
            }
            PushButton:hover {
                background-color: #ffe7a3;
            }
        """
        self._load_btn_style = """
            PushButton {
                border-radius: 14px;
                padding: 9px 16px;
                padding-left: 44px;
                font-size: 13px;
                font-weight: 500;
                background-color: transparent;
                border: 1px solid #e0e0e0;
            }
            PushButton:hover {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
            }
        """
        self._load_btn_style_unload = """
            PushButton {
                border-radius: 14px;
                padding: 9px 16px;
                padding-left: 44px;
                font-size: 13px;
                font-weight: 500;
                background-color: #e8f3ff;
                border: 1px solid #4f8edc;
                color: #2b6cb0;
            }
            PushButton:hover {
                background-color: #d7ecff;
            }
        """

        # 面板入口按钮：使用本地 / 使用线上
        try:
            local_icon = getattr(FluentIcon, "COMPUTER", None) or FluentIcon.DOWNLOAD
        except Exception:
            local_icon = FluentIcon.DOWNLOAD
        try:
            online_icon = getattr(FluentIcon, "CLOUD", None) or getattr(FluentIcon, "GLOBE", None) or FluentIcon.DOCUMENT
        except Exception:
            online_icon = FluentIcon.DOCUMENT

        self.use_local_model_btn = PushButton(local_icon, "使用本地模型", panel)
        self.use_local_model_btn.setMinimumHeight(40)
        self.use_local_model_btn.setIconSize(self._model_btn_icon_size)
        self.use_local_model_btn.setToolTip("打开本地 IndexTTS2 模型管理（下载/加载）")
        self.use_local_model_btn.setStyleSheet(self._download_btn_style_download)
        panel_layout.addWidget(self.use_local_model_btn)

        self.use_online_model_btn = PushButton(online_icon, "使用线上模型", panel)
        self.use_online_model_btn.setMinimumHeight(40)
        self.use_online_model_btn.setIconSize(self._model_btn_icon_size)
        self.use_online_model_btn.setToolTip("打开线上 API 管理与模型选择")
        self.use_online_model_btn.setStyleSheet(self._load_btn_style)
        panel_layout.addWidget(self.use_online_model_btn)

        # 本地模型弹窗懒创建：避免启动阶段构造 MessageBoxBase 引发“启动即弹窗”
        self._local_model_dialog = None
        self.download_btn = None
        self.load_model_btn = None
        
        panel_layout.addStretch()
        
        parent_layout.addWidget(panel, 1)  # stretch factor 1

    def _create_main_content(self, parent_layout: QVBoxLayout):
        """创建中部布局"""
        content = QWidget(self)
        # 改为垂直布局：上部分是参考音频，下部分是文本和结果
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # === 上部分：音色参考音频 (独占一行) ===
        self._create_reference_audio_card(content_layout)

        # === 下部分：合成文本 + 生成结果 (左右并排，各占 1/2) ===
        bottom_row = QWidget(content)
        bottom_layout = QHBoxLayout(bottom_row)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(12)

        # 左侧：合成文本
        self._create_text_input_card(bottom_layout)

        # 右侧：生成音频结果
        self._create_output_card(bottom_layout)
        
        content_layout.addWidget(bottom_row, 1) # 下半部分占据主要空间

        parent_layout.addWidget(content, 1)

    def _create_reference_audio_card(self, parent_layout: QVBoxLayout):
        """创建音色参考音频卡片"""
        # 使用新的 AudioPlayerWidget (开启紧凑模式)
        self.ref_player_widget = ReferenceAudioPlayerWidget("Voice Reference", self)
        # self.ref_player_widget.audio_dropped.connect(self._on_audio_dropped)
        try:
            self.ref_player_widget.upload_requested.connect(self._on_import_audio)
        except Exception:
            pass

        try:
            self.ref_player_widget.clear_requested.connect(self._on_clear_reference_audio)
        except Exception:
            pass
        
        # 移除“导入参考音频”加号按钮：上传交互由空状态提示/点击区域承担
        
        parent_layout.addWidget(self.ref_player_widget)

    def _on_clear_reference_audio(self):
        """清空当前角色的参考音频，并恢复空状态显示。"""
        if getattr(self, "_synthesis_in_progress", False):
            InfoBar.info(
                title="正在生成",
                content="生成进行中，暂不可更换/移除参考音频",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return
        character = self._character_manager.selected_character
        if not character:
            try:
                self.ref_player_widget.set_audio_path("")
            except Exception:
                pass
            self._update_generate_btn_state()
            return

        try:
            self._character_manager.update_reference_audio(character.id, "")
        except Exception:
            pass

        self._update_reference_audio_display()
        self._update_generate_btn_state()
        try:
            self.character_list_widget.update_reference_state(character.id, False)
        except Exception:
            pass

    def _create_text_input_card(self, parent_layout: QHBoxLayout):
        """创建合成文本输入卡片"""
        card = CardWidget(self)
        card.setMinimumWidth(300)
        card.setMinimumHeight(200)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # 标题
        title = BodyLabel("合成文本", card)
        card_layout.addWidget(title)

        # 文本输入框（使用 qfluentwidgets 组件）
        self.text_edit = PlainTextEdit(card)
        self.text_edit.setPlaceholderText("在此输入要合成的文本内容...")
        self.text_edit.setMinimumHeight(120)
        # 防止拖拽文件写入文本框：拖拽导入统一由界面 overlay 接管
        try:
            self.text_edit.setAcceptDrops(False)
            # QPlainTextEdit / QTextEdit 的 viewport 可能仍然接收 drop
            vp = getattr(self.text_edit, "viewport", None)
            if callable(vp):
                v = vp()
                if v is not None:
                    v.setAcceptDrops(False)
        except Exception:
            pass
        card_layout.addWidget(self.text_edit, 1)

        # 生成按钮：放到合成文本卡片内部（输入框下方）
        self.generate_btn = PrimaryPushButton(FluentIcon.SEND, "生成音频（Alt+Enter）", card)
        self.generate_btn.setEnabled(False)
        self.generate_btn.setMinimumHeight(38)
        try:
            self.generate_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        except Exception:
            pass
        card_layout.addWidget(self.generate_btn)

        # 调整占比：改为 1，使三栏等宽 (1:1:1)
        parent_layout.addWidget(card, 1)

    def _create_output_card(self, parent_layout: QHBoxLayout):
        """创建生成音频结果卡片"""
        container = CardWidget(self)
        container.setMinimumWidth(200)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 16)
        container_layout.setSpacing(12)

        # 标题栏：右上角历史记录按钮（占位）
        header = QWidget(container)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 0)
        header_layout.setSpacing(8)

        header_title = BodyLabel("生成结果", header)
        header_layout.addWidget(header_title)
        header_layout.addStretch(1)

        try:
            history_icon = getattr(FluentIcon, "HISTORY")
        except Exception:
            history_icon = FluentIcon.DOCUMENT

        self._history_btn = TransparentToolButton(history_icon, header)
        self._history_btn.setToolTip("历史记录")
        self._history_btn.setEnabled(True)
        self._history_btn.setFixedSize(32, 32)
        header_layout.addWidget(self._history_btn, 0, Qt.AlignmentFlag.AlignRight)
        try:
            self._history_btn.clicked.connect(self._on_open_history)
        except Exception:
            pass

        container_layout.addWidget(header)
        
        # 上半部分：播放器 (AudioPlayerWidget 也是 CardWidget，这里嵌套使用或调整)
        # 为了保持样式一致，我们直接使用 AudioPlayerWidget 作为上半部分，
        # 但 AudioPlayerWidget 本身有边框和阴影。
        # 方案：AudioPlayerWidget 放在 container 内部，去掉 container 的 padding
        
        # 上半部分：空状态/播放器（切换）
        self._output_stack_host = QWidget(container)
        self._output_stack = QStackedLayout(self._output_stack_host)
        self._output_stack.setContentsMargins(0, 0, 0, 0)

        # 空状态：仅显示一个音符图标（居中）
        empty_view = QWidget(self._output_stack_host)
        empty_layout = QVBoxLayout(empty_view)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._output_empty_icon = QLabel(empty_view)
        try:
            self._output_empty_icon.setPixmap(FluentIcon.MUSIC.icon().pixmap(22, 22))
        except Exception:
            self._output_empty_icon.setText("♪")
        self._output_empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self._output_empty_icon)

        # 非空态：展示 3 个候选样本播放器
        outputs_view = QWidget(self._output_stack_host)
        outputs_layout = QVBoxLayout(outputs_view)
        outputs_layout.setContentsMargins(16, 0, 16, 0)
        outputs_layout.setSpacing(8)

        self._output_wav_paths = ["", "", ""]
        self.output_player_widgets = []

        for i in range(3):
            # 标题将随 wav 文件名变化；空态时使用不带序号的占位标题
            w = ResultAudioPlayerWidget("音频", outputs_view)
            w.add_tool_button(
                FluentIcon.DOWNLOAD,
                "保存音频",
                (lambda _=False, idx=i: self._on_download_audio(self._output_wav_paths[idx])),
            )
            outputs_layout.addWidget(w)
            self.output_player_widgets.append(w)

        self._output_stack.addWidget(empty_view)
        self._output_stack.addWidget(outputs_view)
        self._output_stack.setCurrentIndex(0)  # 默认空状态

        container_layout.addWidget(self._output_stack_host)
        container_layout.addStretch()
        
        parent_layout.addWidget(container, 1)

    def _set_output_empty_state(self, empty: bool):
        """切换生成结果区域空状态（未生成时仅显示音符图标）。"""
        try:
            cur = -1
            try:
                cur = int(self._output_stack.currentIndex())
            except Exception:
                cur = -1

            if empty:
                try:
                    self._output_stack.setCurrentIndex(0)
                except Exception:
                    pass
                return
            self._output_stack.setCurrentIndex(1)
            # 非空态会显著增加内容高度：主动让主窗口增高，避免控件被挤压造成“视觉重叠”
            self._grow_window_to_fit_contents()
        except Exception:
            pass

    def _clear_output_results(self) -> None:
        """清空生成结果区域（3 个样本卡片 + 内部路径数组），并回到空态音符。"""
        try:
            self._output_wav_paths = ["", "", ""]
        except Exception:
            pass

        # 先释放媒体句柄，避免 Windows 下删除/改名卡住
        try:
            for w in getattr(self, "output_player_widgets", []) or []:
                try:
                    if hasattr(w, "release_media"):
                        w.release_media()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            for w in getattr(self, "output_player_widgets", []) or []:
                try:
                    w.set_audio_path("")
                except Exception:
                    pass
                try:
                    w.set_loading(False)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            self._set_output_empty_state(True)
        except Exception:
            pass

    def _sync_output_results_after_rename(self, character_id: str, old_name: str, new_name: str) -> None:
        """角色改名成功后，同步生成结果区域中已展示的样本路径/标题。

        目标：输出区展示的 3 条若来自该角色目录，则将其映射到新目录/新文件名。
        """
        try:
            store = self._get_current_history_store()
            old_dir = str(store.get_character_dir(character_id, old_name) or "")
            new_dir = str(store.get_character_dir(character_id, new_name) or "")
        except Exception:
            return

        def _is_under_dir(path: str, base_dir: str) -> bool:
            try:
                if not path or not base_dir:
                    return False
                return os.path.commonpath([os.path.abspath(path), os.path.abspath(base_dir)]) == os.path.abspath(base_dir)
            except Exception:
                return False

        new_paths: list[str] = ["", "", ""]
        try:
            cur_paths = list(getattr(self, "_output_wav_paths", []) or [])
        except Exception:
            cur_paths = []

        # 保持长度为 3
        while len(cur_paths) < 3:
            cur_paths.append("")

        for i in range(3):
            p = str(cur_paths[i] or "")
            if not p:
                continue

            # 只处理位于旧角色目录下的输出
            if not _is_under_dir(p, old_dir):
                # 可能已经是新路径（或不属于该角色），原样保留
                if os.path.exists(p):
                    new_paths[i] = p
                continue

            base = os.path.basename(p)
            candidates: list[str] = []

            # 1) 优先：目录改为 new_dir，文件名前缀 old_name -> new_name
            try:
                if base.startswith(f"{old_name}_"):
                    candidates.append(os.path.join(new_dir, f"{new_name}_" + base[len(old_name) + 1 :]))
            except Exception:
                pass

            # 2) 兜底：仅替换目录（若文件名本身未改/已改）
            try:
                candidates.append(os.path.join(new_dir, base))
            except Exception:
                pass

            # 3) 最后兜底：按序号猜测（常见规则：<name>_1.wav.._3.wav）
            try:
                candidates.append(os.path.join(new_dir, f"{new_name}_{i + 1}.wav"))
            except Exception:
                pass

            chosen = ""
            for c in candidates:
                try:
                    if c and os.path.exists(c):
                        chosen = c
                        break
                except Exception:
                    continue

            new_paths[i] = chosen

        # 应用到状态与控件
        try:
            self._output_wav_paths = new_paths
        except Exception:
            pass

        try:
            widgets = list(getattr(self, "output_player_widgets", []) or [])
        except Exception:
            widgets = []

        for i in range(min(3, len(widgets))):
            try:
                widgets[i].set_audio_path(new_paths[i])
            except Exception:
                pass

        try:
            any_ok = any(p and os.path.exists(p) for p in new_paths)
        except Exception:
            any_ok = False
        try:
            self._set_output_empty_state(not bool(any_ok))
        except Exception:
            pass

    def _grow_window_to_fit_contents(self):
        """当内容区展开时，让主窗口向外增高以容纳内容。

        Qt 默认不会因为子控件 show/hide 自动调整顶层窗口尺寸；
        这里在关键交互点触发一次增高，避免布局被压缩导致控件观感重叠。
        """
        try:
            win = getattr(self, "_main_window", None) or self.window()
            if win is None:
                return

            # 触发布局重算
            try:
                if self.layout() is not None:
                    self.layout().activate()
            except Exception:
                pass

            # 缓存一次“窗口额外高度”（标题栏/导航栏等），避免随着 resize 反复漂移导致越长越高
            if not hasattr(self, "_window_extra_h_cache"):
                try:
                    extra0 = int(win.height()) - int(self.height())
                    self._window_extra_h_cache = max(0, min(600, extra0))
                except Exception:
                    self._window_extra_h_cache = 0

            hint_h = 0
            try:
                hint_h = max(int(self.sizeHint().height()), int(self.minimumSizeHint().height()))
            except Exception:
                hint_h = int(self.height())

            # 估算非 client 区与外围控件占用的高度差
            extra_h = 0
            try:
                extra_h = int(getattr(self, "_window_extra_h_cache", 0) or 0)
            except Exception:
                extra_h = 0

            desired_h = int(hint_h + extra_h + 16)
            if desired_h > int(win.height()):
                win.resize(int(win.width()), desired_h)
        except Exception:
            pass

    def _create_emotion_panel(self, parent_layout: QVBoxLayout):
        """创建情感控制面板"""
        card = CardWidget(self)
        # 供 TeachingTip/spotlight 锚定“情感控制”整个区域（而非单选按钮）
        self.emotion_control_panel_card = card
        card.setMinimumWidth(600)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # 标题
        title = BodyLabel("情感控制", card)
        card_layout.addWidget(title)

        # 模式选择
        mode_layout = QHBoxLayout()
        self.emo_mode_same = RadioButton("与音色参考音频相同", card)
        self.emo_mode_same.setChecked(True)
        self.emo_mode_vector = RadioButton("使用情感向量控制", card)
        mode_layout.addWidget(self.emo_mode_same)
        mode_layout.addWidget(self.emo_mode_vector)
        mode_layout.addStretch()
        card_layout.addLayout(mode_layout)

        # 情感向量控制面板（默认隐藏）
        self.vector_panel = QWidget(card)
        vector_layout = QGridLayout(self.vector_panel)
        vector_layout.setContentsMargins(0, 8, 0, 0)
        vector_layout.setSpacing(8)

        # 8 个情感滑块（水平排列，每行4个）
        self.emo_sliders = {}
        emo_labels = IndexTTSUtility.EMO_LABELS
        for i, label in enumerate(emo_labels):
            row, col = i // 4, (i % 4)
            
            # 创建单个滑块容器
            slider_widget = QWidget(self.vector_panel)
            slider_layout = QHBoxLayout(slider_widget)
            slider_layout.setContentsMargins(0, 0, 0, 0)
            slider_layout.setSpacing(4)
            
            lbl = BodyLabel(f"{label}:", slider_widget)
            lbl.setFixedWidth(40)
            slider_layout.addWidget(lbl)
            
            slider = Slider(Qt.Orientation.Horizontal, slider_widget)
            slider.setRange(0, 100)
            slider.setValue(0)
            slider.setMinimumWidth(80)
            slider_layout.addWidget(slider, 1)
            
            value_label = BodyLabel("0", slider_widget)
            value_label.setFixedWidth(25)
            slider.valueChanged.connect(lambda v, vl=value_label: vl.setText(str(v)))
            slider_layout.addWidget(value_label)
            
            vector_layout.addWidget(slider_widget, row, col)
            self.emo_sliders[label] = slider

        self.vector_panel.setVisible(False)
        card_layout.addWidget(self.vector_panel)

        parent_layout.addWidget(card)

    def _connect_signals(self):
        """连接信号槽"""
        # 模型控制（面板入口）
        try:
            self.use_local_model_btn.clicked.connect(self._on_use_local_model_clicked)
        except Exception:
            pass
        try:
            self.use_online_model_btn.clicked.connect(self._on_use_online_model_clicked)
        except Exception:
            pass

        # 本地模型弹窗内按钮：在弹窗创建时再绑定（避免此时按钮尚未创建）

        # 参考音频 (已在创建组件时连接)
        # self.import_audio_btn.clicked.connect(self._on_import_audio)
        # self.ref_play_btn.clicked.connect(self._on_play_reference)

        # 生成音频
        self.generate_btn.clicked.connect(self._on_generate_clicked)

        # 快捷键：Alt+Enter 生成（焦点在输入框时也可用）
        try:
            sc1 = QShortcut(QKeySequence(Qt.KeyboardModifier.AltModifier | Qt.Key.Key_Return), self)
            sc1.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc1.activated.connect(lambda: self._on_generate_clicked() if self.generate_btn.isEnabled() else None)

            sc2 = QShortcut(QKeySequence(Qt.KeyboardModifier.AltModifier | Qt.Key.Key_Enter), self)
            sc2.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc2.activated.connect(lambda: self._on_generate_clicked() if self.generate_btn.isEnabled() else None)
        except Exception:
            pass
        # self.output_play_btn.clicked.connect(self._on_play_output)
        # self.download_audio_btn.clicked.connect(self._on_download_audio)

        # 情感模式切换
        self.emo_mode_same.toggled.connect(self._on_emo_mode_changed)
        self.emo_mode_vector.toggled.connect(self._on_emo_mode_changed)

        # IndexTTSJob 信号
        self._main_window.indextts_job.progress_updated.connect(self._on_progress_updated)
        self._main_window.indextts_job.job_completed.connect(self._on_job_completed)
        try:
            self._main_window.indextts_job.variant_generated.connect(self._on_variant_generated)
        except Exception:
            pass
        try:
            self._main_window.indextts_job.variant_progress.connect(self._on_variant_progress)
        except Exception:
            pass
        
        # IndexTTSDownloadJob 信号
        self._main_window.indextts_download_job.job_completed.connect(self._on_download_job_completed)

    def _ensure_local_model_dialog(self) -> LocalModelActionsDialog | None:
        """确保本地模型弹窗已创建，并绑定按钮槽函数。"""
        dlg = getattr(self, "_local_model_dialog", None)
        if dlg is not None:
            return dlg
        try:
            dlg = LocalModelActionsDialog(self._main_window)
            self._local_model_dialog = dlg
            self.download_btn = dlg.download_btn
            self.load_model_btn = dlg.load_model_btn
            
            # FP16 开关引用（可能不存在，需判空）
            self.fp16_checkbox = getattr(dlg, "fp16_checkbox", None)
            self.fp16_hint_label = getattr(dlg, "fp16_hint_label", None)

            # 统一样式保持一致
            try:
                self.download_btn.setMinimumHeight(40)
                self.download_btn.setIconSize(self._model_btn_icon_size)
                self.download_btn.setToolTip("下载 IndexTTS2 所需的依赖和模型文件（约 5GB）")
                self.download_btn.setStyleSheet(self._download_btn_style_download)
            except Exception:
                pass
            try:
                self.load_model_btn.setMinimumHeight(40)
                self.load_model_btn.setIconSize(self._model_btn_icon_size)
                self.load_model_btn.setToolTip("加载模型到显存（首次约需 20-30 秒）")
                self.load_model_btn.setStyleSheet(self._load_btn_style)
            except Exception:
                pass

            # 绑定按钮槽（避免重复连接）
            try:
                from PySide6.QtCore import Qt

                self.download_btn.clicked.connect(self._on_download_clicked, Qt.ConnectionType.UniqueConnection)
                self.load_model_btn.clicked.connect(self._on_load_model_clicked, Qt.ConnectionType.UniqueConnection)
            except Exception:
                try:
                    self.download_btn.clicked.connect(self._on_download_clicked)
                except Exception:
                    pass
                try:
                    self.load_model_btn.clicked.connect(self._on_load_model_clicked)
                except Exception:
                    pass

            # 绑定 FP16 开关：仅当用户手动切换时才写入持久化配置
            try:
                if self.fp16_checkbox is not None:
                    def _on_fp16_toggled(checked: bool):
                        try:
                            config_utility.set_config("AIVoice.IndexTTS2.UseFP16", bool(checked))
                        except Exception:
                            pass
                        try:
                            self._refresh_fp16_hint_text()
                        except Exception:
                            pass

                    # SwitchButton 使用 checkedChanged；部分控件也可能是 toggled
                    try:
                        self.fp16_checkbox.checkedChanged.connect(_on_fp16_toggled)
                    except Exception:
                        self.fp16_checkbox.toggled.connect(_on_fp16_toggled)
            except Exception:
                pass

            # 初始化 FP16 默认值与提示文案
            try:
                self._apply_fp16_default(auto_only=True)
            except Exception:
                pass

            # 创建完成后，用当前快照刷新一次按钮显示（避免仍停留在默认样式/文案）
            try:
                self._update_download_btn_state(
                    bool(getattr(self, "_env_ok_fast", False)),
                    bool(getattr(self, "_model_files_ok", False)),
                )
            except Exception:
                pass
            try:
                self._update_model_status()
            except Exception:
                pass
            return dlg
        except Exception:
            return None

    # ==================== 角色管理 ====================
    def _is_character_name_unique(self, name: str, *, exclude_id: str | None = None) -> bool:
        try:
            candidate = str(name or "").strip()
        except Exception:
            candidate = ""
        if not candidate:
            return False

        # Prevent clobbering temp_output/logs
        try:
            store = self._get_current_history_store()
            safe_dir = os.path.basename(store.get_character_dir("", candidate))
            if str(safe_dir).strip().lower() == "logs":
                return False
        except Exception:
            pass

        try:
            candidate_key = candidate.lower()
        except Exception:
            candidate_key = candidate

        for c in self._character_manager.characters:
            try:
                if exclude_id and str(getattr(c, "id", "")) == str(exclude_id):
                    continue
                n = str(getattr(c, "name", "") or "").strip()
                if not n:
                    continue
                if n.lower() == candidate_key:
                    return False
            except Exception:
                continue
        return True
        
    def _recommend_fp16(self) -> tuple[bool, str]:
        """根据主机配置智能推荐 FP16 开关。"""
        smi = {}
        try:
            smi = self._run_nvidia_smi() or {}
        except Exception:
            smi = {}
        
        def _to_int(x):
            try:
                return int(float(str(x).strip()))
            except Exception:
                return None
        
        total_mb = _to_int(smi.get("mem_total_mb"))
        free_mb = _to_int(smi.get("mem_free_mb"))
        gpu_name = str(smi.get("gpu_name") or "").strip()
        
        # 无法识别 GPU：保守默认关闭，但提示用户按需开启
        if not total_mb:
            return False, "未检测到 NVIDIA 显卡信息：默认关闭。若加载失败/显存不足，可开启 FP16。"
        
        total_gb = total_mb / 1024.0
        free_gb = (free_mb / 1024.0) if free_mb is not None else None
        
        # 经验阈值：
        # - 8GB 及以下：强烈建议 FP16
        # - 12GB：通常建议 FP16（尤其是空闲不足时）
        # - 16GB+：可默认关闭
        if total_mb <= 8192:
            reason = f"检测到 GPU {gpu_name or ''} 显存约 {total_gb:.1f}GB：建议开启 FP16 以降低显存占用。"
            if free_gb is not None:
                reason += f" 当前空闲约 {free_gb:.1f}GB。"
            return True, reason
        
        if total_mb <= 12288:
            if free_mb is not None and free_mb < 9000:
                return True, f"检测到显存约 {total_gb:.1f}GB（空闲偏紧约 {free_gb:.1f}GB）：建议开启 FP16。"
            return True, f"检测到显存约 {total_gb:.1f}GB：开启 FP16 通常更稳、更省显存。"
        
        # 16GB 及以上
        if free_mb is not None and free_mb < 12000:
            return True, f"虽然总显存约 {total_gb:.1f}GB，但当前空闲仅约 {free_gb:.1f}GB：建议开启 FP16。"
        return False, f"检测到显存约 {total_gb:.1f}GB：默认关闭 FP16（需要更省显存时可开启）。"
    
    def _refresh_fp16_hint_text(self) -> None:
        lbl = getattr(self, "fp16_hint_label", None)
        if lbl is None:
            return
        
        saved = self._get_fp16_saved_preference()
        rec, reason = self._recommend_fp16()
        if saved is None:
            lbl.setText(f"自动推荐：{'开启' if rec else '关闭'}。{reason}")
        else:
            lbl.setText(f"已按你的设置：{'开启' if saved else '关闭'}。{reason}")
    
    def _apply_fp16_default(self, *, auto_only: bool = True) -> None:
        """将 FP16 默认值应用到弹窗开关。
        
        auto_only=True：仅当用户没有保存偏好时才自动设置。
        """
        cb = getattr(self, "fp16_checkbox", None)
        if cb is None:
            return
        
        saved = self._get_fp16_saved_preference()
        if auto_only and (saved is not None):
            # 用户有明确偏好：不自动覆盖
            try:
                cb.setChecked(bool(saved))
            except Exception:
                pass
            self._refresh_fp16_hint_text()
            return
        
        rec, _ = self._recommend_fp16()
        try:
            cb.setChecked(bool(rec) if saved is None else bool(saved))
        except Exception:
            pass
        self._refresh_fp16_hint_text()

    def _on_add_character(self):
        """添加新角色"""
        if not self._character_manager.can_add:
            InfoBar.warning(
                title="角色数量已达上限",
                content=f"最多只能创建 {CharacterManager.MAX_CHARACTERS} 个角色",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        dialog = CharacterDialog(self._main_window)
        if dialog.exec():
            name, avatar_path = dialog.get_data()
            if name:
                if not self._is_character_name_unique(str(name)):
                    InfoBar.error(
                        title="昵称不可用",
                        content="角色昵称必须唯一，且不能使用 logs 作为昵称",
                        parent=self,
                        position=InfoBarPosition.TOP,
                        duration=3500,
                    )
                    return
                character = self._character_manager.add(name, avatar_path)
                if character:
                    self._refresh_character_list()
                    self._select_character(character.id)
                    InfoBar.success(
                        title="角色创建成功",
                        content=f"已创建角色: {name}",
                        parent=self,
                        position=InfoBarPosition.TOP,
                        duration=2000
                    )

    def _on_character_selected(self, character_id: str):
        """角色被选中 - 选中并置顶"""
        # 选中并置顶
        self._character_manager.select_and_move_to_top(character_id)
        # 刷新列表
        self._refresh_character_list()
        # 更新参考音频显示
        self._update_reference_audio_display()
        # 更新生成按钮状态
        self._update_generate_btn_state()
        # 刷新历史窗口（若已打开）
        try:
            self._refresh_history_window_if_open()
        except Exception:
            pass

    def _on_character_edit(self, character_id: str):
        """编辑角色"""
        character = self._character_manager.get_by_id(character_id)
        if not character:
            return

        old_name = str(getattr(character, "name", "") or "")

        dialog = CharacterDialog(
            self._main_window,
            character_name=character.name,
            avatar_path=character.avatar_path
        )
        if dialog.exec():
            name, avatar_path = dialog.get_data()
            if name:
                if (str(name).strip() != old_name.strip()) and (not self._is_character_name_unique(str(name), exclude_id=character_id)):
                    InfoBar.error(
                        title="昵称不可用",
                        content="角色昵称必须唯一，且不能使用 logs 作为昵称",
                        parent=self,
                        position=InfoBarPosition.TOP,
                        duration=3500,
                    )
                    return
                self._character_manager.update(
                    character_id,
                    name=name,
                    avatar_path=avatar_path
                )

                # 同步更新 temp_output 下的角色目录与样本文件名
                try:
                    if str(name) and str(name) != old_name:
                        # Windows 下若 wav 正在被播放器占用，目录改名会失败（表现为只新建空目录）
                        try:
                            win = getattr(self, "_history_window", None)
                            if win is not None and hasattr(win, "release_all_media"):
                                win.release_all_media()
                        except Exception:
                            pass
                        try:
                            for w in getattr(self, "output_player_widgets", []) or []:
                                if hasattr(w, "release_media"):
                                    w.release_media()
                        except Exception:
                            pass
                        # 没有任何历史缓存时不应提示“改名失败”
                        has_old_cache = False
                        try:
                            from Source.Utility.tts_history_utility import _sanitize_component

                            safe_old = _sanitize_component(old_name)
                            desired_old = os.path.join(self._get_current_history_store().base_dir, safe_old)
                            has_old_cache = bool(safe_old and os.path.isdir(desired_old))
                        except Exception:
                            has_old_cache = False

                        ok = bool(self._get_current_history_store().rename_character_cache(character_id, old_name, str(name)))
                        if has_old_cache and (not ok):
                            InfoBar.warning(
                                title="历史缓存改名失败",
                                content="可能有音频仍在播放/占用文件，建议停止播放或关闭历史窗口后重试",
                                parent=self,
                                position=InfoBarPosition.TOP,
                                duration=4500,
                            )
                        else:
                            # 同步刷新生成结果区域显示的文件名/路径
                            try:
                                self._sync_output_results_after_rename(character_id, old_name, str(name))
                            except Exception:
                                pass
                except Exception:
                    pass

                self._refresh_character_list()
                try:
                    self._refresh_history_window_if_open()
                except Exception:
                    pass
                InfoBar.success(
                    title="角色更新成功",
                    content=f"已更新角色: {name}",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=2000
                )

    def _on_character_delete(self, character_id: str):
        """删除角色"""
        character = self._character_manager.get_by_id(character_id)
        if not character:
            return

        msg = MessageBox(
            "确认删除",
            f"确定要删除角色「{character.name}」吗？\n删除后将从列表中移除。",
            self._main_window
        )
        if msg.exec():
            # 删除角色时，一并清理 temp_output 下该角色的音频文件夹
            try:
                # Windows 下若 wav 正在被播放器占用，删除会失败（表现为只删掉 history.jsonl 或无变化）
                try:
                    win = getattr(self, "_history_window", None)
                    if win is not None and hasattr(win, "release_all_media"):
                        win.release_all_media()
                except Exception:
                    pass
                try:
                    for w in getattr(self, "output_player_widgets", []) or []:
                        if hasattr(w, "release_media"):
                            w.release_media()
                except Exception:
                    pass
                # 参考音频播放器也可能占用文件
                try:
                    if hasattr(self, "ref_player_widget") and hasattr(self.ref_player_widget, "release_media"):
                        self.ref_player_widget.release_media()
                except Exception:
                    pass

                removed = int(self._get_current_history_store().delete_character_cache(character_id, str(getattr(character, "name", "") or "")))
                if removed < 0:
                    InfoBar.warning(
                        title="缓存删除可能失败",
                        content="可能有音频仍在播放/占用文件，建议停止播放或关闭历史窗口后再删除",
                        parent=self,
                        position=InfoBarPosition.TOP,
                        duration=4500,
                    )
            except Exception:
                pass
            self._character_manager.delete(character_id)
            self._refresh_character_list()

            # 删除角色后：切换到新的选中角色并清空生成结果区域（避免残留已被删除的 wav）
            try:
                next_id = self._character_manager.selected_id
                if next_id:
                    self._select_character(next_id)
                else:
                    self._update_reference_audio_display()
                    self._update_generate_btn_state()
            except Exception:
                pass
            try:
                self._clear_output_results()
            except Exception:
                pass

            try:
                self._refresh_history_window_if_open()
            except Exception:
                pass
            InfoBar.success(
                title="角色已删除",
                content=f"已删除角色: {character.name}",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000
            )

    def _on_batch_delete_characters(self):
        """批量删除角色（带选择对话框）。"""
        try:
            characters = list(self._character_manager.characters or [])
        except Exception:
            characters = []

        if not characters:
            InfoBar.info(
                title="没有可删除的角色",
                content="当前项目没有角色",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=1800,
            )
            return

        dlg = BatchDeleteCharactersDialog(self._main_window, characters)
        if not dlg.exec():
            return

        selected_ids = dlg.get_selected_ids()
        if not selected_ids:
            InfoBar.info(
                title="未选择角色",
                content="请先勾选要删除的角色",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=1800,
            )
            return

        msg = MessageBox(
            "确认批量删除",
            f"确定要删除选中的 {len(selected_ids)} 个角色吗？\n删除后将从列表中移除。",
            self._main_window,
        )
        if not msg.exec():
            return

        # 删除前尽量释放媒体句柄（Windows 删除/改名需要）
        try:
            win = getattr(self, "_history_window", None)
            if win is not None and hasattr(win, "release_all_media"):
                win.release_all_media()
        except Exception:
            pass
        try:
            for w in getattr(self, "output_player_widgets", []) or []:
                if hasattr(w, "release_media"):
                    w.release_media()
        except Exception:
            pass
        try:
            if hasattr(self, "ref_player_widget") and hasattr(self.ref_player_widget, "release_media"):
                self.ref_player_widget.release_media()
        except Exception:
            pass

        failed_cache = 0
        deleted = 0
        for cid in selected_ids:
            ch = None
            try:
                ch = self._character_manager.get_by_id(cid)
            except Exception:
                ch = None
            if ch is None:
                continue

            try:
                removed = int(self._get_current_history_store().delete_character_cache(cid, str(getattr(ch, "name", "") or "")))
                if removed < 0:
                    failed_cache += 1
            except Exception:
                pass

            try:
                if self._character_manager.delete(cid):
                    deleted += 1
            except Exception:
                pass

        self._refresh_character_list()
        try:
            next_id = self._character_manager.selected_id
            if next_id:
                self._select_character(next_id)
            else:
                self._update_reference_audio_display()
                self._update_generate_btn_state()
        except Exception:
            pass
        try:
            self._clear_output_results()
        except Exception:
            pass

        try:
            self._refresh_history_window_if_open()
        except Exception:
            pass

        if failed_cache > 0:
            InfoBar.warning(
                title="部分缓存删除失败",
                content=f"有 {failed_cache} 个角色的缓存目录可能仍被占用，可停止播放/关闭历史窗口后再重试删除缓存。",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4500,
            )

        InfoBar.success(
            title="批量删除完成",
            content=f"已删除 {deleted} 个角色",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2200,
        )

    def _on_import_from_wwise(self):
        """从Wwise项目导入角色"""
        # 检查是否有当前项目
        if not self._current_project_id:
            InfoBar.warning(
                title="未选择项目",
                content="请先在项目页面创建或选择一个项目",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        # 显示处理中提示
        InfoBar.info(
            title="正在扫描",
            content="正在从Wwise项目中发现角色...",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000
        )

        try:
            from Source.Utility.wwise_character_discovery import discover_leaf_work_units_from_project
            from Source.UI.Interface.AIVoiceInterface.wwise_workunit_import_dialog import WwiseWorkUnitImportDialog

            # 发现叶子 WorkUnit
            candidates = discover_leaf_work_units_from_project(self._current_project_id)
            if not candidates:
                InfoBar.warning(
                    title="未发现 WorkUnit",
                    content="未在 Actor-Mixer Hierarchy 下找到可导入的最低层 WorkUnit",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3200,
                )
                return

            # 弹窗让用户选择要导入的 WorkUnit
            dlg = WwiseWorkUnitImportDialog(self._main_window, candidates=candidates)
            if not dlg.exec():
                return
            selected_units = dlg.get_selected_candidates()
            if not selected_units:
                InfoBar.info(
                    title="未选择",
                    content="未选择任何 WorkUnit，已取消导入",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=2200,
                )
                return

            # 记录导入前已有名称，用于导入后自动定位一个新角色
            try:
                existed = {str(c.name or "").strip() for c in self._character_manager.characters}
            except Exception:
                existed = set()

            characters_data = []
            for u in selected_units:
                characters_data.append(
                    {
                        "name": str(u.name or "").strip(),
                        "reference_audio_path": str(u.reference_voice_path or "").strip(),
                        "avatar_path": "",
                    }
                )

            result = self._character_manager.batch_import(characters_data, skip_existing=True)
            if result.get("imported", 0) > 0:
                self._refresh_character_list()

                # 自动选中一个新导入的角色，方便直接看到 reference_audio 是否带入
                try:
                    for u in selected_units:
                        n = str(u.name or "").strip()
                        if n and n not in existed:
                            c = self._character_manager.get_by_name(n)
                            if c is not None:
                                self._select_character(c.id)
                                break
                except Exception:
                    pass

            from Source.UI.Interface.AIVoiceInterface.import_result_dialog import ImportResultDialog
            ImportResultDialog(
                self._main_window,
                imported=int(result.get("imported", 0)),
                skipped=int(result.get("skipped", 0)),
                failed=int(result.get("failed", 0)),
            ).exec()

        except ValueError as e:
            # 项目配置错误（如未配置Wwise项目路径）
            InfoBar.error(
                title="配置错误",
                content=str(e),
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000
            )
        except FileNotFoundError as e:
            # Wwise项目文件不存在
            InfoBar.error(
                title="文件不存在",
                content=str(e),
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000
            )
        except Exception as e:
            # 其他错误
            InfoBar.error(
                title="导入失败",
                content=f"从Wwise导入角色时出错: {str(e)}",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000
            )
            import traceback
            traceback.print_exc()

    def _select_character(self, character_id: str):
        """选中角色（不置顶）"""
        self._character_manager.select(character_id)
        
        # 更新角色列表选中状态
        self.character_list_widget.update_selection(character_id)
        
        # 更新参考音频显示
        self._update_reference_audio_display()
        
        # 更新生成按钮状态
        self._update_generate_btn_state()

        # 刷新历史窗口（若已打开）
        try:
            self._refresh_history_window_if_open()
        except Exception:
            pass

    def _refresh_history_window_if_open(self):
        win = getattr(self, "_history_window", None)
        if win is None:
            return
        try:
            if not win.isVisible():
                return
        except Exception:
            pass
        character = self._character_manager.selected_character
        if character is None:
            try:
                win.set_character("", "")
            except Exception:
                pass
            return
        try:
            if hasattr(win, "set_history_store"):
                win.set_history_store(self._get_current_history_store())
            win.set_character(character.id, character.name)
        except Exception:
            pass

    def _on_open_history(self):
        """打开非模态历史记录窗口（按当前所选角色过滤）。"""
        character = self._character_manager.selected_character
        if character is None:
            InfoBar.info(
                title="未选择角色",
                content="请先选择一个角色再查看历史记录",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return

        win = getattr(self, "_history_window", None)
        if win is None:
            win = AIVoiceHistoryWindow(
                self._main_window,
                download_callback=self._on_download_audio,
                history_store=self._get_current_history_store(),
            )
            self._history_window = win
        try:
            if hasattr(win, "set_history_store"):
                win.set_history_store(self._get_current_history_store())
            win.set_character(character.id, character.name)
        except Exception:
            pass
        try:
            win.show()
            win.raise_()
            win.activateWindow()
        except Exception:
            pass

    def _refresh_character_list(self):
        """刷新角色列表"""
        try:
            if hasattr(self.character_list_widget, "set_character_manager") and (self._character_manager is not None):
                self.character_list_widget.set_character_manager(self._character_manager)
            else:
                self.character_list_widget.refresh()
        except Exception:
            try:
                self.character_list_widget.refresh()
            except Exception:
                pass
        # 更新参考音频显示
        self._update_reference_audio_display()

    def _update_reference_audio_display(self):
        """更新参考音频显示"""
        character = self._character_manager.selected_character
        
        if not character:
            self.ref_player_widget.set_audio_path("")
            return
        
        if character.reference_audio_path and os.path.exists(character.reference_audio_path):
            self.ref_player_widget.set_audio_path(character.reference_audio_path)
        else:
            self.ref_player_widget.set_audio_path("")

    # ==================== 模型选择 ====================

    def _on_download_clicked(self):
        """下载或删除依赖和模型"""
        if getattr(self, "_synthesis_in_progress", False):
            InfoBar.info(
                title="正在生成",
                content="生成进行中，暂不可执行该操作",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return
        audiobox_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        save_dir = os.path.join(audiobox_root, "checkpoints")
        
        # 保存路径以防万一
        self._pending_save_dir = save_dir

        # 下载模式：首次点击前做一次设备预检（删除模式不拦截）
        if not getattr(self, "_is_delete_mode", False):
            if not self._run_indextts_preflight_before_download(save_dir):
                return

        # 若模型齐全但环境缺失：提供“下载环境依赖”入口（保持弹窗样式一致）
        if getattr(self, "_model_files_ok", False) and (not getattr(self, "_env_ok_fast", False)):
            self._show_fix_env_dialog(save_dir)
            return

        if self._is_delete_mode:
            # 删除模式：让用户选择删除模型 or 删除依赖
            self._show_delete_assets_dialog(save_dir)
            return

        # 下载模式：环境检测在“使用本地模型”打开时已触发；这里直接复用结果。
        if getattr(self, "_env_check_pending", False):
            InfoBar.info(
                title="正在检测环境",
                content="请稍候，环境检测完成后再继续",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2500,
            )
            return

        last_ready = getattr(self, "_env_check_last_ready", None)
        last_msg = str(getattr(self, "_env_check_last_msg", "") or "")

        if last_ready is True:
            self._download_model_files(save_dir)
            return

        if last_ready is False and last_msg:
            dialog = EnvMissingInstallDialog(self._main_window, last_msg)
            res = dialog.exec()
            if res and dialog.choice == "install":
                self._pending_save_dir = save_dir
                try:
                    from PySide6.QtCore import Qt

                    self._main_window.indextts_env_job.job_completed.connect(
                        self._on_env_job_finished, Qt.ConnectionType.UniqueConnection
                    )
                except Exception:
                    try:
                        self._main_window.indextts_env_job.job_completed.connect(self._on_env_job_finished)
                    except Exception:
                        pass
                self._main_window.indextts_env_job.install_action()
            return

        # 兜底：若还没有任何检测结果，则回退为交互式检测流程
        self._start_async_env_check(save_dir, show_install_dialog_on_missing=True, on_ready="download")

    def _run_indextts_preflight_before_download(self, save_dir: str) -> bool:
        """IndexTTS2 下载前设备预检。

        - 通过：不打扰，直接进入下载流程
        - 有建议项：弹窗提示，允许继续/取消
        - 有阻断项：弹窗提示并阻止继续（避免下载后无法运行或下载失败）
        """

        if getattr(self, "_indextts_preflight_checked", False):
            return True

        result = IndexTTSPreflightUtility.run_check(save_dir)

        # 结构化输出到运行时终端（便于排查用户环境问题）
        try:
            print(IndexTTSPreflightUtility.format_terminal_block(result), flush=True)
        except Exception:
            pass

        if result.has_blockers:
            report = IndexTTSPreflightUtility.format_report_text(result)
            dialog = IndexTTSPreflightDialog(self._main_window, report, can_continue=False)
            dialog.exec()
            return False

        if result.has_warnings:
            report = IndexTTSPreflightUtility.format_report_text(result)
            dialog = IndexTTSPreflightDialog(self._main_window, report, can_continue=True)
            res = dialog.exec()
            if res and dialog.choice == "continue":
                self._indextts_preflight_checked = True
                return True
            return False

        self._indextts_preflight_checked = True
        return True

    def _show_fix_env_dialog(self, save_dir: str):
        """环境缺失但模型齐全时的弹窗入口：提供“下载环境依赖”按钮。"""
        dialog = DeleteAssetsChoiceDialog(self._main_window, save_dir, env_action="download")
        res = dialog.exec()

        if dialog.choice == "download_env":
            QTimer.singleShot(100, self._download_env_only)
            return

        if res and dialog.choice == "delete_model":
            self._delete_model_files(save_dir)

    def _show_delete_assets_dialog(self, save_dir: str):
        """删除入口弹窗：将“删除模型”和“删除依赖”分离为两个按键。"""
        # 检查模型是否已加载
        if self._main_window.indextts_job.is_model_loaded:
            InfoBar.warning(
                title="请先卸载模型",
                content="模型正在使用中，请先卸载模型后再删除",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        dialog = DeleteAssetsChoiceDialog(self._main_window, save_dir)
        res = dialog.exec()

        if dialog.choice == "delete_env":
            # 新弹窗已经是确认，因此跳过二次确认
            QTimer.singleShot(100, lambda: self._delete_env_only(skip_confirm=True))
            return

        if res and dialog.choice == "delete_model":
            self._delete_model_files(save_dir)

    def _download_env_only(self):
        """仅安装 IndexTTS2 独立环境依赖（Runtime/IndexTTS2/.venv）。"""
        try:
            from PySide6.QtCore import Qt

            self._main_window.indextts_env_job.job_completed.connect(
                self._on_env_job_finished, Qt.ConnectionType.UniqueConnection
            )
        except Exception:
            try:
                self._main_window.indextts_env_job.job_completed.connect(self._on_env_job_finished)
            except Exception:
                pass

        self._main_window.indextts_env_job.install_action()

    def _start_async_env_check(
        self,
        save_dir: str,
        *,
        show_install_dialog_on_missing: bool = True,
        on_ready: str = "download",
    ):
        """异步检查环境。

        Args:
            save_dir: 模型目录
            show_install_dialog_on_missing: 环境缺失时是否弹出“下载依赖”对话框
            on_ready: 环境就绪后的动作："download" 触发下载流程；"none" 仅更新状态
        """
        if self._env_check_pending:
            return

        self._env_check_pending = True
        self._env_check_request_id += 1
        request_id = self._env_check_request_id

        try:
            if getattr(self, "download_btn", None) is not None:
                self.download_btn.setEnabled(False)
                self.download_btn.setText("正在检测环境...")
        except Exception:
            pass

        worker = EnvCheckWorker()
        # Keep a strong reference to avoid Python GC interrupting signal delivery.
        try:
            worker.setAutoDelete(False)
        except Exception:
            pass
        self._env_check_worker = worker

        worker.signals.finished.connect(
            lambda is_ready, msg: self._on_env_check_finished(
                request_id,
                is_ready,
                msg,
                save_dir,
                show_install_dialog_on_missing=bool(show_install_dialog_on_missing),
                on_ready=str(on_ready or "download"),
            )
        )
        QThreadPool.globalInstance().start(worker)

        # Watchdog: avoid being stuck forever if worker is blocked.
        QTimer.singleShot(20000, lambda: self._on_env_check_timeout(request_id))

    def _on_env_check_timeout(self, request_id: int):
        if not self._env_check_pending:
            return
        if request_id != self._env_check_request_id:
            return

        self._env_check_pending = False
        self._env_check_worker = None
        try:
            if getattr(self, "download_btn", None) is not None:
                self.download_btn.setEnabled(True)
        except Exception:
            pass
        self._check_env_and_model()

        InfoBar.warning(
            title="环境检测超时",
            content="环境检测耗时过长，请稍后重试或直接点击“安装并下载”。",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=4500
        )

    def _on_env_check_finished(
        self,
        request_id: int,
        is_ready: bool,
        msg: str,
        save_dir: str,
        *,
        show_install_dialog_on_missing: bool = True,
        on_ready: str = "download",
    ):
        """环境检测完成回调"""
        if request_id != self._env_check_request_id:
            return

        self._env_check_pending = False
        self._env_check_worker = None
        try:
            if getattr(self, "download_btn", None) is not None:
                self.download_btn.setEnabled(True)
        except Exception:
            pass
        # 检查当前状态（如果文件已存在，则更新为删除模式；否则保持下载模式）
        self._check_env_and_model()

        # 缓存最近一次检测结果，供“下载依赖和模型”点击时复用
        try:
            self._env_check_last_ready = bool(is_ready)
            self._env_check_last_msg = str(msg or "")
        except Exception:
            self._env_check_last_ready = bool(is_ready)
            self._env_check_last_msg = ""
        
        if not is_ready:
            if not bool(show_install_dialog_on_missing):
                return

            # 提示安装环境（自定义布局，保证按钮不重叠；样式与“下载模型”窗口一致）
            dialog = EnvMissingInstallDialog(self._main_window, msg)
            res = dialog.exec()
            if res and dialog.choice == "install":
                self._pending_save_dir = save_dir

                # 连接信号，等待环境安装完成
                try:
                    from PySide6.QtCore import Qt

                    self._main_window.indextts_env_job.job_completed.connect(
                        self._on_env_job_finished, Qt.ConnectionType.UniqueConnection
                    )
                except Exception:
                    try:
                        self._main_window.indextts_env_job.job_completed.connect(self._on_env_job_finished)
                    except Exception:
                        pass

                # 启动环境安装
                self._main_window.indextts_env_job.install_action()
            return

        # 环境已就绪
        if str(on_ready).lower() == "download":
            # 进入模型下载流程
            self._download_model_files(save_dir)
            return

        # on_ready == none: 仅更新状态，不触发下载
        return

    def _on_env_job_finished(self, success: bool):
        """环境安装完成回调"""
        # 安装/卸载完成后，刷新按钮与生成状态
        self._check_env_and_model()
        self._update_generate_btn_state()

        if success:
            # 环境安装成功，继续下载模型
            if hasattr(self, '_pending_save_dir') and self._pending_save_dir:
                # 稍微延迟一下，让用户看清上一个成功的提示
                QTimer.singleShot(500, lambda: self._download_model_files(self._pending_save_dir))
                self._pending_save_dir = None
        else:
            # 失败了，清理状态
            self._pending_save_dir = None

    def _download_model_files(self, save_dir: str):
        """下载模型文件"""
        # 安全检查：如果路径为空，使用默认路径
        if not save_dir:
            audiobox_root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
            save_dir = os.path.join(audiobox_root, "checkpoints")

        # 检测是否已完整
        is_complete, missing = IndexTTSUtility.check_model_files(save_dir)
        if is_complete:
            InfoBar.success(
                title="模型已就绪",
                content="依赖和模型文件已完整",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            # 刷新按钮状态：模型齐全后还需结合环境是否存在
            self._check_env_and_model()
            return

        dialog = DownloadModelChoiceDialog(self._main_window, save_dir)
        res = dialog.exec()

        if dialog.choice == "delete_env":
            QTimer.singleShot(100, self._delete_env_only)
            return

        if res:
            use_mirror = (dialog.choice != "direct")
            self._main_window.indextts_download_job.download_action(save_dir, use_mirror=use_mirror)

    def _delete_env_only(self, skip_confirm: bool = False):
        """仅删除 IndexTTS2 独立环境（Runtime/IndexTTS2/.venv），不删除模型文件。"""
        # 检查模型是否已加载
        if self._main_window.indextts_job.is_model_loaded:
            InfoBar.warning(
                title="请先卸载模型",
                content="模型正在使用中，请先卸载模型后再删除环境依赖",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        if not skip_confirm:
            msg = MessageBox(
                "删除环境依赖",
                "确定要删除 IndexTTS2 独立环境吗？\n\n"
                "将删除: Runtime/IndexTTS2/.venv\n\n"
                "模型文件（checkpoints）不会被删除。",
                self._main_window
            )
            msg.yesButton.setText("确认删除")
            msg.cancelButton.setText("取消")
            self._tune_message_box(msg)

            if not msg.exec():
                return

        self._main_window.indextts_env_job.uninstall_action()
        self._env_ready = False
        self._update_generate_btn_state()

        # 卸载结束后刷新界面状态（避免按钮文案不更新）
        try:
            from PySide6.QtCore import Qt

            self._main_window.indextts_env_job.job_completed.connect(
                self._on_env_job_finished, Qt.ConnectionType.UniqueConnection
            )
        except Exception:
            try:
                self._main_window.indextts_env_job.job_completed.connect(self._on_env_job_finished)
            except Exception:
                pass

    def _delete_model_files(self, save_dir: str):
        """删除模型文件（不删除独立环境依赖）。"""
        # 检查模型是否已加载
        if self._main_window.indextts_job.is_model_loaded:
            InfoBar.warning(
                title="请先卸载模型",
                content="模型正在使用中，请先卸载模型后再删除",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        # 注意：确认弹窗在 _show_delete_assets_dialog 中已经执行，这里不再二次确认。

        # 收集要删除的文件
        files_to_delete = []
        for filename in IndexTTSUtility.get_required_files():
            file_path = os.path.join(save_dir, filename)
            if os.path.exists(file_path):
                files_to_delete.append(file_path)
        
        # 添加可选的 feat 文件
        for feat_file in ["feat1.pt", "feat2.pt"]:
            file_path = os.path.join(save_dir, feat_file)
            if os.path.exists(file_path):
                files_to_delete.append(file_path)
        
        # 添加要删除的文件夹（模型下载产生的目录）
        dirs_to_delete = []
        for dir_name in ["qwen0.6bemo4-merge", "hf_cache", "amphion", "facebook"]:
            dir_path = os.path.join(save_dir, dir_name)
            if os.path.exists(dir_path):
                dirs_to_delete.append(dir_path)
        
        # 显示进度弹窗 (用于文件删除阶段)
        progress_window = ProgressBarWindow(self._main_window)
        progress_window.set_text("正在删除模型文件...")
        progress_window.set_total_count(len(files_to_delete) + len(dirs_to_delete))
        progress_window.set_enable_cancel(False)  # 删除操作不可取消
        
        # 执行文件删除
        try:
            import shutil
            from PySide6.QtWidgets import QApplication
            deleted_count = 0
            
            # 1. 删除文件
            for i, file_path in enumerate(files_to_delete):
                try:
                    filename = os.path.basename(file_path)
                    progress_window.set_text(f"正在删除文件: {filename}")
                    progress_window.set_current_count(deleted_count)
                    QApplication.processEvents()  # 刷新 UI
                    
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"删除文件失败: {file_path}, 错误: {e}")
            
            # 2. 删除文件夹
            for dir_path in dirs_to_delete:
                try:
                    dirname = os.path.basename(dir_path)
                    progress_window.set_text(f"正在删除目录: {dirname}")
                    progress_window.set_current_count(deleted_count)
                    QApplication.processEvents()
                    
                    shutil.rmtree(dir_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"删除目录失败: {dir_path}, 错误: {e}")
            
            progress_window.set_current_count(len(files_to_delete) + len(dirs_to_delete))
            progress_window.set_text("文件删除完成，准备卸载依赖...")
            QApplication.processEvents()

            # 检查目录是否为空，如果为空则删除目录
            if os.path.exists(save_dir) and not os.listdir(save_dir):
                os.rmdir(save_dir)

            progress_window.close()

            # 仅删除模型文件：保留独立环境，以便后续重新下载模型更快。
            self._check_env_and_model()
            self._update_generate_btn_state()

        except Exception as e:
            progress_window.close()
            InfoBar.error(
                title="删除失败",
                content=str(e),
                parent=self,
                position=InfoBarPosition.TOP,
                duration=5000
            )
            
            # 更新按钮状态
            self._check_env_and_model()
            self._env_ready = False
            self._update_generate_btn_state()

    def _update_download_btn_state(self, env_ok: bool, model_ok: bool):
        """更新下载/删除按钮状态

        - env_ok & model_ok: 配置完成 -> 删除入口
        - !env_ok & model_ok: 缺乏依赖（仅环境缺失）-> 保持黄色样式，提供下载环境依赖入口
        - otherwise: 下载依赖和模型
        """
        btn = getattr(self, "download_btn", None)

        # 先更新内部状态（即使按钮尚未创建）
        self._is_delete_mode = bool(env_ok and model_ok)

        # 弹窗懒创建：界面 refresh() 可能先于弹窗按钮创建
        if btn is None:
            return

        # 1) 配置完成：允许删除
        if env_ok and model_ok:
            btn.setText("配置完成，点击可删除")
            # 视觉保持与“加载完成，点击可卸载”一致：浅蓝 + 对勾
            btn.setIcon(FluentIcon.ACCEPT)
            btn.setToolTip("删除 IndexTTS2 的依赖和模型文件以释放磁盘空间")
            if hasattr(self, "_model_btn_icon_size"):
                btn.setIconSize(self._model_btn_icon_size)
            btn.setStyleSheet(getattr(self, "_load_btn_style_unload", ""))
            return

        # 2) 仅环境缺失：保持黄色样式，但引导下载环境依赖
        if (not env_ok) and model_ok:
            btn.setText("缺乏依赖，点击可下载")
            btn.setIcon(FluentIcon.DOWNLOAD)
            btn.setToolTip("检测到环境依赖缺失，点击可下载/安装环境依赖")
            if hasattr(self, "_model_btn_icon_size"):
                btn.setIconSize(self._model_btn_icon_size)
            # 复用当前“配置完成”黄色样式
            btn.setStyleSheet(getattr(self, "_download_btn_style_delete", ""))
            return

        # 3) 其余情况：下载依赖和模型
        btn.setText("下载依赖和模型")
        btn.setIcon(FluentIcon.DOWNLOAD)
        btn.setToolTip("下载 IndexTTS2 所需的依赖和模型文件（约 5GB）")
        if hasattr(self, "_model_btn_icon_size"):
            btn.setIconSize(self._model_btn_icon_size)
        btn.setStyleSheet(getattr(self, "_download_btn_style_download", ""))

    def _on_load_model_clicked(self):
        """加载/卸载模型"""
        if getattr(self, "_synthesis_in_progress", False):
            InfoBar.info(
                title="正在生成",
                content="生成进行中，暂不可加载/卸载模型",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return
        job = self._main_window.indextts_job
        
        if job.is_model_loaded:
            # 卸载模型
            job.unload_model()
            self._update_model_status()
            InfoBar.success(
                title="模型已卸载",
                content="显存已释放",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000
            )
        else:
            # 检查环境是否就绪
            if not self._check_env_ready_with_warning():
                return
            
            # 加载模型
            model_dir = IndexTTSUtility.get_default_model_dir()
            
            is_complete, missing = IndexTTSUtility.check_model_files(model_dir)
            if not is_complete:
                InfoBar.error(
                    title="模型文件不完整",
                    content="请先下载依赖和模型",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3000
                )
                return

            # 读取 FP16 开关（若弹窗未创建则按智能推荐/持久化偏好）
            use_fp16 = None
            try:
                cb = getattr(self, "fp16_checkbox", None)
                if cb is not None:
                    use_fp16 = bool(cb.isChecked())
            except Exception:
                use_fp16 = None
            if use_fp16 is None:
                saved = self._get_fp16_saved_preference()
                if saved is None:
                    use_fp16, _ = self._recommend_fp16()
                else:
                    use_fp16 = bool(saved)
            
            # 标记：本次为“模型加载”，用于失败提示/自动重试
            try:
                self._model_load_in_progress = True
                self._model_load_last_fp16 = bool(use_fp16)
            except Exception:
                pass
            
            # 加载耗时提示：若过久仍未完成，给出优化建议（不打断）
            try:
                if not hasattr(self, "_model_load_watchdog") or self._model_load_watchdog is None:
                    self._model_load_watchdog = QTimer(self)
                    self._model_load_watchdog.setSingleShot(True)
                    self._model_load_watchdog.timeout.connect(self._on_model_load_watchdog_timeout)
                self._model_load_watchdog.start(90_000)
            except Exception:
                pass
            
            job.load_model_action(
                model_dir,
                use_fp16=bool(use_fp16),
                use_cuda_kernel=False,
                use_deepspeed=False,
            )
            
            self.load_model_btn.setEnabled(False)
            self.load_model_btn.setText("加载中...")

            # 加载期间禁用 FP16 开关（避免用户误以为实时生效）
            try:
                if getattr(self, "fp16_checkbox", None) is not None:
                    self.fp16_checkbox.setEnabled(False)
            except Exception:
                pass

    def _on_model_load_watchdog_timeout(self):
        """模型加载超过一定时间：提示可能需要 FP16/释放显存。"""
        try:
            if not bool(getattr(self, "_model_load_in_progress", False)):
                return
        except Exception:
            return

        try:
            rec, reason = self._recommend_fp16()
        except Exception:
            rec, reason = (True, "")

        msg = "模型加载时间较长。"
        if bool(getattr(self, "_model_load_last_fp16", False)):
            msg += "已启用 FP16，仍较慢时建议关闭占用显存的软件后重试。"
        else:
            msg += "可能是显存不足导致卡住，建议开启 FP16（半精度）后重试。"
        if reason:
            msg += f"\n{reason}"

        try:
            InfoBar.warning(
                title="模型加载较慢",
                content=msg,
                parent=self,
                position=InfoBarPosition.TOP,
                duration=7000,
            )
        except Exception:
            pass
    
    def _check_env_ready_with_warning(self) -> bool:
        """检查环境是否就绪，如未就绪则显示警告
        
        Returns:
            bool: 环境是否就绪
        """
        # 1) 检查 IndexTTS2 独立 venv 是否就绪
        try:
            from Source.Job.indextts_env_job import IndexTTSEnvJob

            is_ready, msg = IndexTTSEnvJob.check_env_ready()
            if not is_ready:
                InfoBar.warning(
                    title="环境未就绪",
                    content=msg,
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=4500
                )
                return False
        except Exception as e:
            InfoBar.error(
                title="环境检测失败",
                content=str(e),
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4500
            )
            return False

        # 2) 检查模型文件是否存在
        model_dir = IndexTTSUtility.get_default_model_dir()
        is_complete, _ = IndexTTSUtility.check_model_files(model_dir)
        
        if not is_complete:
            InfoBar.warning(
                title="请先下载依赖和模型",
                content="AI 语音功能需要先下载依赖和模型文件才能使用",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000
            )
            return False
        return True

    def _update_model_status(self):
        """更新模型状态显示"""
        job = self._main_window.indextts_job

        btn = getattr(self, "load_model_btn", None)
        title_btn = getattr(self, "model_control_title_btn", None)
        
        if job.is_model_loaded:
            self._model_ready = True

            if btn is not None:
                btn.setText("加载完成，点击可卸载")
                btn.setIcon(FluentIcon.ACCEPT)
                btn.setStyleSheet(self._load_btn_style_unload)

            # 标题切换为“使用中 + 设备信息”，并允许点击查看详情
            try:
                device = getattr(job, "device", "")
                device = device() if callable(device) else device
            except Exception:
                device = ""

            device_text = str(device).strip() if device else "未知"
            if title_btn is not None:
                title_btn.setText(f"正在使用本地模型，使用设备：{device_text}")
                title_btn.setEnabled(True)
                title_btn.setToolTip("点击查看更详细的模型/显存信息")
        else:
            self._model_ready = False

            if btn is not None:
                btn.setText("加载模型")
                btn.setIcon(FluentIcon.PLAY)
                btn.setStyleSheet(self._load_btn_style)

            # 未加载时恢复普通标题且不响应点击
            if title_btn is not None:
                title_btn.setText("模型选择")
                title_btn.setEnabled(False)
                title_btn.setToolTip("")

        if btn is not None:
            btn.setEnabled(True)

        # FP16 开关：模型已加载时禁用（更改需要卸载后重新加载才生效）
        try:
            cb = getattr(self, "fp16_checkbox", None)
            if cb is not None:
                cb.setEnabled(not bool(job.is_model_loaded))
        except Exception:
            pass
        self._update_generate_btn_state()

    def _run_nvidia_smi(self) -> dict:
        """尝试通过 nvidia-smi 获取 CUDA/显存信息。

        返回 dict，可能为空（例如没有 NVIDIA 驱动/命令）。
        """
        try:
            import subprocess

            # 1) 获取 CUDA 版本（nvidia-smi 顶部行包含 CUDA Version）
            p = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            out = (p.stdout or "").splitlines()
            cuda_ver = ""
            driver_ver = ""
            if out:
                # 示例：| NVIDIA-SMI 555.85 ... CUDA Version: 12.5 |
                first = out[0]
                if "CUDA Version" in first:
                    try:
                        cuda_ver = first.split("CUDA Version:", 1)[1].split("|")[0].strip()
                    except Exception:
                        cuda_ver = ""
                if "NVIDIA-SMI" in first:
                    try:
                        # NVIDIA-SMI 后面的版本号
                        driver_ver = first.split("NVIDIA-SMI", 1)[1].strip().split()[0]
                    except Exception:
                        driver_ver = ""

            # 2) GPU 名称 + 显存（首张卡）
            q = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,memory.used,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            row = (q.stdout or "").strip().splitlines()
            gpu_name = ""
            mem_total = ""
            mem_used = ""
            mem_free = ""
            if row:
                parts = [p.strip() for p in row[0].split(",")]
                if len(parts) >= 4:
                    gpu_name, mem_total, mem_used, mem_free = parts[:4]

            return {
                "cuda_version": cuda_ver,
                "driver_version": driver_ver,
                "gpu_name": gpu_name,
                "mem_total_mb": mem_total,
                "mem_used_mb": mem_used,
                "mem_free_mb": mem_free,
            }
        except Exception:
            return {}

    def _on_model_title_clicked(self):
        """点击标题：展示模型诊断信息。"""
        job = self._main_window.indextts_job
        if not job.is_model_loaded:
            return

        # Job/engine 信息
        try:
            device = job.device
        except Exception:
            device = ""
        device_text = str(device).strip() if device else "未知"

        model_dir = ""
        engine_pid = ""
        engine_alive = ""
        stderr_tail = ""
        try:
            util = getattr(job, "_utility", None)
            if util is not None:
                model_dir = getattr(util, "model_dir", "") or ""
                proc = getattr(util, "_engine_proc", None)
                if proc is not None:
                    try:
                        engine_pid = str(proc.pid)
                    except Exception:
                        engine_pid = ""
                    try:
                        engine_alive = "是" if (proc.poll() is None) else "否"
                    except Exception:
                        engine_alive = ""

                tail = getattr(util, "_engine_stderr_tail", None)
                if isinstance(tail, list) and tail:
                    stderr_tail = "\n".join([str(x) for x in tail[-60:]])
        except Exception:
            pass

        # GPU/CUDA 信息
        smi = self._run_nvidia_smi()

        lines = []
        lines.append("基础")
        lines.append(f"- 设备: {device_text}")
        if model_dir:
            lines.append(f"- 模型目录: {model_dir}")
        if engine_pid:
            lines.append(f"- 引擎进程 PID: {engine_pid}")
        if engine_alive:
            lines.append(f"- 引擎存活: {engine_alive}")

        lines.append("")
        lines.append("CUDA / 显存（来自 nvidia-smi，若可用）")
        if smi:
            if smi.get("gpu_name"):
                lines.append(f"- GPU: {smi.get('gpu_name')}")
            if smi.get("driver_version"):
                lines.append(f"- NVIDIA-SMI: {smi.get('driver_version')}")
            if smi.get("cuda_version"):
                lines.append(f"- CUDA Version: {smi.get('cuda_version')}")
            if smi.get("mem_total_mb"):
                lines.append(
                    f"- 显存(MB): 已用 {smi.get('mem_used_mb')}/{smi.get('mem_total_mb')}，剩余 {smi.get('mem_free_mb')}"
                )
        else:
            lines.append("- 未检测到 nvidia-smi 或读取失败")

        if stderr_tail:
            lines.append("")
            lines.append("引擎日志尾部（stderr tail）")
            lines.append(stderr_tail)

        details = "\n".join(lines)
        dlg = ModelDiagnosticsDialog(self, "模型详细信息", details)
        dlg.exec()

    # ==================== 音频操作 ====================

    def _on_import_audio(self):
        """导入参考音频"""
        if getattr(self, "_synthesis_in_progress", False):
            InfoBar.info(
                title="正在生成",
                content="生成进行中，暂不可导入参考音频",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return
        character = self._character_manager.selected_character
        if not character:
            InfoBar.warning(
                title="请先选择角色",
                content="需要先创建并选择一个角色",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择参考音频", "",
            "音频文件 (*.wav *.mp3 *.flac *.ogg);;所有文件 (*.*)"
        )
        
        if file_path:
            self._update_character_audio(character.id, file_path)

    def _on_audio_dropped(self, file_path: str):
        """处理拖拽导入的音频"""
        if getattr(self, "_synthesis_in_progress", False):
            InfoBar.info(
                title="正在生成",
                content="生成进行中，暂不可导入参考音频",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return
        character = self._character_manager.selected_character
        if not character:
            InfoBar.warning(
                title="请先选择角色",
                content="请先在左侧列表中选择或创建一个角色",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return
            
        self._update_character_audio(character.id, file_path)

    def _update_character_audio(self, character_id: str, file_path: str):
        """更新角色的参考音频"""
        self._character_manager.update_reference_audio(character_id, file_path)
        self._update_reference_audio_display()
        self._update_generate_btn_state()
        try:
            self.character_list_widget.update_reference_state(character_id, bool(file_path))
        except Exception:
            pass
        
        InfoBar.success(
            title="参考音频已更新",
            content=f"已加载: {os.path.basename(file_path)}",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def _ensure_ref_player(self):
        """确保参考音频播放器已创建"""
        if self._ref_player is None:
            self._ref_player = QMediaPlayer(self)
            self._ref_audio_output = QAudioOutput(self)
            self._ref_player.setAudioOutput(self._ref_audio_output)

    def _on_play_reference(self):
        """播放参考音频 (已由 AudioPlayerWidget 接管)"""
        pass

    def _ensure_player(self):
        """确保输出音频播放器已创建 (已废弃)"""
        pass

    def _on_play_output(self):
        """播放生成的音频 (已由 AudioPlayerWidget 接管)"""
        pass

    def _on_download_audio(self, wav_path: Optional[str] = None):
        """下载/保存生成的音频（支持指定某个样本路径）。"""
        if wav_path is None:
            wav_path = self._main_window.indextts_job.last_wav_path
        if not wav_path or not os.path.exists(wav_path):
            InfoBar.warning(
                title="无可保存文件",
                content="请先生成音频",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000,
            )
            return

        character = self._character_manager.selected_character
        if character:
            suggested_dir, suggested_name = self._character_manager.get_suggested_output_path(character.id)
        else:
            suggested_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MusicLocation)
            suggested_name = f"output_{int(time.time())}.wav"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存音频文件",
            os.path.join(suggested_dir, suggested_name),
            "WAV 音频 (*.wav);;所有文件 (*.*)",
        )

        if save_path:
            try:
                import shutil

                shutil.copy2(wav_path, save_path)
                if character:
                    self._character_manager.update_last_output(
                        character.id,
                        os.path.dirname(save_path),
                        os.path.basename(save_path),
                    )
                InfoBar.success(
                    title="保存成功",
                    content=os.path.basename(save_path),
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                )
            except Exception as e:
                InfoBar.error(
                    title="保存失败",
                    content=str(e),
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                )

    # ==================== 语音合成 ====================

    def _on_generate_clicked(self):
        """生成语音"""
        if getattr(self, "_synthesis_in_progress", False):
            InfoBar.info(
                title="正在生成",
                content="请等待当前生成完成",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return
        # 检查环境是否就绪
        if not self._check_env_ready_with_warning():
            return
        
        # 检查模型是否已加载
        if not self._main_window.indextts_job.is_model_loaded:
            InfoBar.warning(
                title="请先加载模型",
                content="需要先加载模型才能生成语音",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return
        
        character = self._character_manager.selected_character
        if not character:
            InfoBar.warning(
                title="请先选择角色",
                content="需要先创建并选择一个角色",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        if not character.reference_audio_path or not os.path.exists(character.reference_audio_path):
            InfoBar.warning(
                title="请导入参考音频",
                content="需要先导入音色参考音频",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        text = self.text_edit.toPlainText().strip()
        if not text:
            InfoBar.warning(
                title="请输入文本",
                content="合成文本不能为空",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        # 确定情感模式
        if self.emo_mode_same.isChecked():
            emo_mode = IndexTTSUtility.EMO_MODE_SAME_AS_SPEAKER
            emo_vector = None
        else:
            emo_mode = IndexTTSUtility.EMO_MODE_VECTOR
            emo_vector = [
                self.emo_sliders[label].value() / 100.0
                for label in IndexTTSUtility.EMO_LABELS
            ]

        # 输出路径与历史记录：按项目/角色写入 temp_output/<project>/<角色>/，并生成序列文件名
        try:
            output_paths = self._get_current_history_store().build_output_paths(character.id, character.name, count=3)
        except Exception:
            # 极端情况下 build_output_paths 失败时，仍尽量保持按项目隔离，避免写入全局 temp_output
            project_dir = str(getattr(self, "_current_project_id", "") or "")
            if project_dir:
                temp_dir = os.path.join(os.getcwd(), "temp_output", project_dir)
            else:
                temp_dir = os.path.join(os.getcwd(), "temp_output")
            os.makedirs(temp_dir, exist_ok=True)
            ts = int(time.time())
            output_paths = [os.path.join(temp_dir, f"temp_{ts}_v{i + 1}.wav") for i in range(3)]

        # 组逻辑：合成文本不变则并入上一组；否则新建一组
        try:
            group_id = self._get_current_history_store().get_or_create_group_id(character.id, character.name, text)
        except Exception:
            group_id = str(int(time.time() * 1000))
        self._history_pending = {
            "character_id": character.id,
            "character_name": character.name,
            "text": text,
            "group_id": group_id,
        }

        # 清空旧输出 UI，并预渲染 3 个样本为“生成中”遮罩态
        try:
            self._output_wav_paths = ["", "", ""]
            for w in getattr(self, "output_player_widgets", []):
                w.set_audio_path("")
                try:
                    w.set_loading(True, 0.0)
                except Exception:
                    pass
            # 点击生成后立刻展示 3 个预渲染播放器（避免出现“空态音符 + 底部进度/文本”）
            self._set_output_empty_state(False)
        except Exception:
            pass

        # 开始生成
        self._synthesis_in_progress = True
        self._main_window.indextts_job.synthesize_variants_action(
            spk_audio_path=character.reference_audio_path,
            text=text,
            output_paths=output_paths,
            emo_mode=emo_mode,
            emo_vector=emo_vector,
        )

        # 更新 UI 状态
        self.generate_btn.setEnabled(False)

    def _on_emo_mode_changed(self):
        """情感模式切换"""
        self.vector_panel.setVisible(self.emo_mode_vector.isChecked())
        # 展开情感向量面板时，让窗口向外增高而不是压缩上方组件
        if self.emo_mode_vector.isChecked():
            self._grow_window_to_fit_contents()

    def _update_generate_btn_state(self):
        """更新生成按钮状态"""
        character = self._character_manager.selected_character
        job = self._main_window.indextts_job

        ref_audio = ""
        try:
            if character is not None and character.reference_audio_path:
                ref_audio = str(character.reference_audio_path)
        except Exception:
            ref_audio = ""

        can_generate = bool(
            job.is_model_loaded
            and character is not None
            and ref_audio
            and os.path.exists(ref_audio)
        )
        self.generate_btn.setEnabled(bool(can_generate))

    # ==================== 进度回调 ====================

    @Slot(float, str)
    def _on_progress_updated(self, progress: float, text: str):
        """进度更新回调"""
        # 生成结果区域不再展示“总进度条/底部状态文本”（仅使用每个样本卡片的遮罩进度）
        return

    @Slot(int, str)
    def _on_variant_generated(self, index: int, wav_path: str):
        """某个候选样本生成完成回调。"""
        try:
            if 0 <= int(index) < 3:
                self._output_wav_paths[int(index)] = wav_path
                if hasattr(self, "output_player_widgets") and int(index) < len(self.output_player_widgets):
                    self.output_player_widgets[int(index)].set_audio_path(wav_path)
                    try:
                        self.output_player_widgets[int(index)].set_loading(False)
                    except Exception:
                        pass
                self._set_output_empty_state(False)
        except Exception:
            pass

    @Slot(int, float, str)
    def _on_variant_progress(self, index: int, progress: float, text: str):
        """单个样本实时进度：更新对应播放器遮罩进度条。"""
        try:
            idx = int(index)
            if hasattr(self, "output_player_widgets") and 0 <= idx < len(self.output_player_widgets):
                self.output_player_widgets[idx].set_loading_progress(float(progress))
        except Exception:
            pass

    @Slot(bool)
    def _on_job_completed(self, success: bool):
        """任务完成回调"""
        # 先处理“模型加载”路径：补齐失败提示/一键重试
        is_model_load_flow = bool(getattr(self, "_model_load_in_progress", False)) and (not bool(getattr(self, "_synthesis_in_progress", False)))
        if is_model_load_flow:
            # 停止 watchdog
            try:
                if getattr(self, "_model_load_watchdog", None) is not None:
                    self._model_load_watchdog.stop()
            except Exception:
                pass

            # 清理标志
            try:
                self._model_load_in_progress = False
            except Exception:
                pass

            # 先把 FP16 开关放开（若模型成功加载，_update_model_status 会再禁用）
            try:
                if getattr(self, "fp16_checkbox", None) is not None:
                    self.fp16_checkbox.setEnabled(True)
            except Exception:
                pass

            if not success:
                last_fp16 = bool(getattr(self, "_model_load_last_fp16", False))

                try:
                    rec, reason = self._recommend_fp16()
                except Exception:
                    rec, reason = (True, "")

                if not last_fp16:
                    msg = (
                        "模型加载失败，常见原因：显存不足（尤其 8GB）、驱动/环境异常或模型文件不完整。\n\n"
                        "建议开启 FP16（半精度）降低显存占用后重试。"
                    )
                    if reason:
                        msg += f"\n\n{reason}"

                    ok = False
                    try:
                        box = MessageBox("模型加载失败", msg, self._main_window)
                        self._tune_message_box(box)
                        box.yesButton.setText("开启 FP16 并重试")
                        box.cancelButton.setText("取消")
                        ok = (box.exec() == 1)
                    except Exception:
                        ok = False

                    if ok:
                        try:
                            if getattr(self, "fp16_checkbox", None) is not None:
                                self.fp16_checkbox.setChecked(True)
                        except Exception:
                            pass
                        try:
                            self._on_load_model_clicked()
                        except Exception:
                            pass
                else:
                    hint = (
                        "模型加载失败（已启用 FP16）。\n"
                        "建议：\n"
                        "- 关闭占用显存的软件（游戏/浏览器硬件加速等）\n"
                        "- 更新 NVIDIA 驱动\n"
                        "- 确认模型文件完整（必要时重新下载）"
                    )
                    if reason:
                        hint += f"\n\n{reason}"
                    try:
                        InfoBar.error(
                            title="模型加载失败",
                            content=hint,
                            parent=self,
                            position=InfoBarPosition.TOP,
                            duration=9000,
                        )
                    except Exception:
                        pass

        self._update_model_status()
        self._update_generate_btn_state()

        # job_completed(True) 同时用于“模型加载完成”和“语音生成完成”。
        # 只有当我们确实处于“合成中”时，才更新生成结果状态文本。
        if not self._synthesis_in_progress:
            return

        self._synthesis_in_progress = False

        # 结束后，确保所有遮罩都退出
        try:
            for w in getattr(self, "output_player_widgets", []):
                w.set_loading(False)
        except Exception:
            pass
        
        if success:
            any_ok = False
            try:
                any_ok = any(p and os.path.exists(p) for p in getattr(self, "_output_wav_paths", []))
            except Exception:
                any_ok = False
            if any_ok:
                self._set_output_empty_state(False)

                # 写入历史记录（最多 3 个样本）
                try:
                    pending = getattr(self, "_history_pending", None) or {}
                    cid = str(pending.get("character_id", ""))
                    cname = str(pending.get("character_name", ""))
                    gid = str(pending.get("group_id", ""))
                    txt = str(pending.get("text", ""))
                    if cid and gid:
                        self._get_current_history_store().append_samples(
                            cid,
                            cname,
                            gid,
                            txt,
                            list(getattr(self, "_output_wav_paths", []) or []),
                        )
                except Exception:
                    pass

                # 若历史窗口已打开，刷新内容
                try:
                    self._refresh_history_window_if_open()
                except Exception:
                    pass
            else:
                # 没有任何样本产出：回到空态音符
                try:
                    self._output_wav_paths = ["", "", ""]
                    for w in getattr(self, "output_player_widgets", []):
                        w.set_audio_path("")
                except Exception:
                    pass
                self._set_output_empty_state(True)
        else:
            try:
                self._output_wav_paths = ["", "", ""]
                for w in getattr(self, "output_player_widgets", []):
                    w.set_audio_path("")
            except Exception:
                pass
            self._set_output_empty_state(True)

        # 清理 pending
        try:
            self._history_pending = None
        except Exception:
            pass

    @Slot(bool)
    def _on_download_job_completed(self, success: bool):
        """下载任务完成回调"""
        if success:
            self._check_env_and_model()

    # ==================== 环境检测 ====================

    def _check_env_and_model(self):
        """检查环境和模型状态"""
        # 注意：此方法会在界面 refresh() 时被调用，必须保持非阻塞。
        # 这里只做“是否存在独立 venv python”的快速判断；更完整的依赖检查
        # 由 EnvCheckWorker 在后台线程完成。
        env_ok = False
        try:
            from Source.Utility.indextts_runtime_utility import get_runtime_paths

            env_ok = bool(os.path.exists(get_runtime_paths().venv_python))
        except Exception:
            env_ok = False

        # 检查模型文件
        model_dir = IndexTTSUtility.get_default_model_dir()
        model_ok, _ = IndexTTSUtility.check_model_files(model_dir)

        # 记录快照，供点击逻辑使用
        self._env_ok_fast = bool(env_ok)
        self._model_files_ok = bool(model_ok)
        
        # 更新下载/删除按钮状态（若正在异步检测，不覆盖按钮文案/禁用状态）
        if not self._env_check_pending:
            self._update_download_btn_state(bool(env_ok), bool(model_ok))
            try:
                if getattr(self, "download_btn", None) is not None:
                    self.download_btn.setEnabled(True)
            except Exception:
                pass
        self._env_ready = bool(env_ok and model_ok)

        # 更新模型状态
        self._update_model_status()

    # ==================== 公共接口 ====================

    def refresh(self):
        """刷新界面状态（切换到此界面时调用）"""
        # 进入 AI语音 页时，优先对齐到主窗口当前项目（避免显示默认/旧项目角色）
        try:
            pid = str(getattr(self._main_window, "get_current_project_id")() or "").strip()
            if pid:
                self.on_project_tab_switched(pid)
        except Exception:
            pass

        self._refresh_character_list()
        self._check_env_and_model()
        self._update_generate_btn_state()

        # 更新播放器状态：默认回到空态（不做历史回填）
        try:
            self._output_wav_paths = ["", "", ""]
            for w in getattr(self, "output_player_widgets", []):
                w.set_audio_path("")
                try:
                    w.set_loading(False)
                except Exception:
                    pass
        except Exception:
            pass
        self._set_output_empty_state(True)

    # ==================== 首次使用引导 ====================

    def show_first_time_welcome_from_project(self) -> bool:
        """每次应用启动后，首次进入 AI语音 时调用（非模态）。

        规则：
        - 由 dev_config_utility.force_ai_voice_welcome_every_time() 控制是否展示
        - force=true 时，本次进程只展示一次（不是每次切页都弹）
        - 只有点击“OK，不再显示”才会写入本地 dev.json(force=false)

        返回：本次是否成功展示
        """
        try:
            if not bool(dev_config_utility.force_ai_voice_welcome_every_time()):
                return False
        except Exception:
            return False

        if getattr(self, "_welcome_shown_runtime", False):
            return False

        try:
            dlg = AIVoiceWelcomeDialog(self._main_window, on_start_guide=self.start_quick_guide)
            try:
                dlg.setModal(False)
            except Exception:
                pass
            try:
                dlg.setWindowModality(Qt.WindowModality.NonModal)
            except Exception:
                pass

            dlg.show()
            try:
                dlg.raise_()
                dlg.activateWindow()
            except Exception:
                pass

            self._welcome_dialog = dlg
            self._welcome_shown_runtime = True

            try:
                print("[AIVoice] Welcome dialog shown", flush=True)
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                print(f"[AIVoice][WelcomeDialog][Error] {e}", flush=True)
            except Exception:
                pass
            return False

    def start_quick_guide(self):
        """启动 6 步快速指引。优先使用 TeachingTip（锚定），失败则回退为模态弹窗。"""
        try:
            if self._welcome_dialog is not None:
                self._welcome_dialog.close()
        except Exception:
            pass

        self._quick_guide_step_index = 0
        # 让欢迎弹窗先完全关闭，再开始指引
        QTimer.singleShot(120, lambda: self._run_quick_guide_step_teaching_tip(0))

    def _ensure_teaching_tip_modal_blocker(self):
        """开启透明输入拦截层，让 TeachingTip 流程表现为“模态”。"""
        try:
            if getattr(self, "_quick_guide_modal_overlay", None) is None and self._main_window is not None:
                self._quick_guide_modal_overlay = _ModalInputBlockerOverlay(self._main_window)
            overlay = getattr(self, "_quick_guide_modal_overlay", None)
            if overlay is not None:
                overlay.show()
                overlay.raise_()
        except Exception:
            pass

    def _update_teaching_tip_spotlight(self, target: QWidget | None):
        """更新 spotlight 高亮区域。"""
        overlay = getattr(self, "_quick_guide_modal_overlay", None)
        if overlay is None:
            return
        try:
            overlay.set_spotlight_target(target)
        except Exception:
            pass

    def _teardown_teaching_tip_modal_blocker(self):
        """关闭并释放透明输入拦截层。"""
        overlay = getattr(self, "_quick_guide_modal_overlay", None)
        if overlay is None:
            return
        try:
            try:
                overlay.set_spotlight_target(None)
            except Exception:
                pass
            overlay.hide()
        except Exception:
            pass
        try:
            overlay.deleteLater()
        except Exception:
            pass
        self._quick_guide_modal_overlay = None

    def _add_teaching_tip_footer_buttons(self, view: QWidget, step_index: int, total: int):
        """在 TeachingTipView 底部添加按钮。

        """
        try:
            host = QWidget(view)
            layout = QHBoxLayout(host)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(12)
            layout.addStretch(1)

            is_last = (step_index >= (total - 1))
            if not is_last:
                next_btn = PrimaryPushButton("下一步", host)
                skip_btn = PushButton("跳过", host)
                next_btn.setMinimumHeight(32)
                skip_btn.setMinimumHeight(32)
                next_btn.clicked.connect(lambda: self._on_teaching_tip_next(step_index))
                skip_btn.clicked.connect(self._on_teaching_tip_skip)
                layout.addWidget(next_btn)
                layout.addWidget(skip_btn)
            else:
                finish_btn = PrimaryPushButton("恭喜完成指引！快去上手实操吧~", host)
                finish_btn.setMinimumHeight(32)
                finish_btn.clicked.connect(self._on_teaching_tip_finish)
                layout.addWidget(finish_btn)

            # TeachingTipView.addWidget 存在于 qfluentwidgets 1.10.5
            view.addWidget(host)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _configure_teaching_tip_view_for_wrapping(self, tip: QWidget, view: QWidget):
        """尽量避免 TeachingTip 由于不换行导致的越界/超宽。"""
        try:
            from PySide6.QtWidgets import QLabel
        except Exception:
            QLabel = None  # type: ignore

        max_content_w = 520
        try:
            win = getattr(self, "_main_window", None)
            if win is not None and hasattr(win, "width"):
                w = int(win.width())
                # 适配：宽窗口用更舒适的宽度，小窗口跟随缩小
                max_content_w = int(min(560, max(340, w * 0.45)))
        except Exception:
            pass

        try:
            if QLabel is not None:
                title_label = view.findChild(QLabel, "titleLabel")
                content_label = view.findChild(QLabel, "contentLabel")

                if title_label is not None:
                    try:
                        title_label.setWordWrap(True)
                        title_label.setMaximumWidth(max_content_w)
                    except Exception:
                        pass

                if content_label is not None:
                    try:
                        content_label.setWordWrap(True)
                        content_label.setMaximumWidth(max_content_w)
                    except Exception:
                        pass
        except Exception:
            pass

        # 给 view 也加一个上限，避免布局把窗口拉到非常宽
        try:
            view.setMaximumWidth(int(max_content_w + 72))
        except Exception:
            pass

        try:
            view.adjustSize()
        except Exception:
            pass
        try:
            tip.adjustSize()
        except Exception:
            pass

    def _choose_teaching_tip_tail_position(self, target: QWidget, preferred):
        """根据目标控件在屏幕中的位置，尽量选择更不容易被遮挡的 tailPosition。

        约定：
        - tip 在目标下方  -> tailPosition.TOP
        - tip 在目标上方  -> tailPosition.BOTTOM
        - tip 在目标右侧  -> tailPosition.LEFT
        - tip 在目标左侧  -> tailPosition.RIGHT
        """
        try:
            from PySide6.QtCore import QPoint, QRect
            from PySide6.QtGui import QGuiApplication
        except Exception:
            return preferred

        def _to_global_rect(w: QWidget):
            try:
                p = w.mapToGlobal(QPoint(0, 0))
                return QRect(p, w.size())
            except Exception:
                return None

        try:
            rect = _to_global_rect(target)
            if rect is None:
                return preferred
            screen = QGuiApplication.screenAt(rect.center())
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            if screen is None:
                return preferred
            avail = screen.availableGeometry()

            above = rect.top() - avail.top()
            below = avail.bottom() - rect.bottom()
            left = rect.left() - avail.left()
            right = avail.right() - rect.right()

            # 粗略估计 TeachingTip 高度（含按钮），用于决定上下翻转
            min_space = 190

            # 先尊重 preferred
            try:
                if preferred == TeachingTipTailPosition.TOP and below >= min_space:
                    return TeachingTipTailPosition.TOP
                if preferred == TeachingTipTailPosition.BOTTOM and above >= min_space:
                    return TeachingTipTailPosition.BOTTOM
                if preferred == TeachingTipTailPosition.LEFT and right >= 260:
                    return TeachingTipTailPosition.LEFT
                if preferred == TeachingTipTailPosition.RIGHT and left >= 260:
                    return TeachingTipTailPosition.RIGHT
            except Exception:
                pass

            # 再做自适应选择
            best = max(
                [
                    (below, TeachingTipTailPosition.TOP),
                    (above, TeachingTipTailPosition.BOTTOM),
                    (right, TeachingTipTailPosition.LEFT),
                    (left, TeachingTipTailPosition.RIGHT),
                ],
                key=lambda x: x[0],
            )[1]
            return best
        except Exception:
            return preferred

    def _get_quick_guide_steps(self):
        return [
            (
                "模型选择\n",
                "⬇️ 先点击“下载依赖和模型”完成准备，然后点击“加载模型”把模型加载到显存。"
                "💡 只需下载一次，后续使用只需点击“加载模型”即可，关闭程序会自动卸载模型。",
                lambda: getattr(self, "model_control_panel_card", None) or getattr(self, "download_btn", None),
                # 期望放在“模型选择”区域下方；空间不足时会自动翻转
                TeachingTipTailPosition.TOP,
            ),
            (
                "角色列表\n",
                "👤 在这里选择/新增角色。每个角色 固定对应一个导入的音频。",
                lambda: getattr(self, "character_list_widget", None),
                TeachingTipTailPosition.LEFT,
            ),
            (
                "导入参考音频\n",
                "🎧 点击该区域导入参考音频，支持拖拽本地文件导入。",
                lambda: getattr(self, "ref_player_widget", None),
                TeachingTipTailPosition.TOP,
            ),
            (
                "合成文本\n",
                "✍️ 在文本框输入要合成的内容，然后点击“生成音频”。支持 Alt+Enter 快捷键生成。",
                lambda: getattr(self, "text_edit", None),
                TeachingTipTailPosition.TOP,
            ),
            (
                "情感控制\n",
                "🎛️ 可选择“与参考相同”或“使用情感向量控制”。使用向量控制时可通过滑块调节语音情绪。",
                lambda: getattr(self, "emotion_control_panel_card", None) or getattr(self, "emo_mode_same", None),
                TeachingTipTailPosition.TOP,
            ),
            (
                "生成结果\n",
                "🔊 生成完成后会在右侧展示 3 个候选样本，并可点击历史记录查看以往生成结果。",
                # 空状态时 outputs_view 会被 QStackedLayout 隐藏，导致样本控件 isVisible=False。
                # 这里改为锚定“生成结果”总容器，始终可见。
                lambda: getattr(self, "_output_stack_host", None),
                TeachingTipTailPosition.RIGHT,
            ),
        ]

    def _close_current_teaching_tip(self):
        tip = getattr(self, "_quick_guide_teaching_tip", None)
        if tip is None:
            return
        try:
            tip.close()
        except Exception:
            pass
        try:
            tip.deleteLater()
        except Exception:
            pass
        self._quick_guide_teaching_tip = None

    def _run_quick_guide_step_teaching_tip(self, step_index: int):
        """TeachingTip 版本的引导。无法锚定/异常时回退到模态弹窗版本。"""
        steps = self._get_quick_guide_steps()
        total = len(steps)
        if step_index < 0 or step_index >= total:
            self._close_current_teaching_tip()
            self._teardown_teaching_tip_modal_blocker()
            return

        step_title, step_desc, focus_getter, tail_pos = steps[step_index]

        try:
            target = focus_getter() if callable(focus_getter) else None
        except Exception:
            target = None

        if target is None:
            self._close_current_teaching_tip()
            self._teardown_teaching_tip_modal_blocker()
            self._run_quick_guide_step(step_index)
            return

        try:
            if hasattr(target, "isVisible") and (not target.isVisible()):
                # 不可见时很难锚定，直接回退
                self._close_current_teaching_tip()
                self._teardown_teaching_tip_modal_blocker()
                self._run_quick_guide_step(step_index)
                return
        except Exception:
            pass

        # 尽量把焦点给到对应区域（非强制）
        try:
            target.setFocus()
        except Exception:
            pass

        try:
            # 让 TeachingTip 流程表现为“模态”：阻断背景操作
            self._ensure_teaching_tip_modal_blocker()
            self._update_teaching_tip_spotlight(target)
            self._close_current_teaching_tip()
            tip_title = f"快速指引（{step_index + 1}/{total}）·{step_title}"
            # 根据屏幕可用空间做 tailPosition 自适应，尽量避免被遮挡
            try:
                tail_pos = self._choose_teaching_tip_tail_position(target, tail_pos)
            except Exception:
                pass

            tip = TeachingTip.create(
                target=target,
                title=tip_title,
                content=step_desc,
                icon=None,
                image=None,
                isClosable=False,
                duration=-1,
                tailPosition=tail_pos,
                parent=self._main_window,
                isDeleteOnClose=True,
            )
            self._quick_guide_teaching_tip = tip

            # 尝试设置窗口模态（有些平台/窗口旗标下可能不生效，但 overlay 会生效）
            try:
                tip.setWindowModality(Qt.WindowModality.ApplicationModal)
            except Exception:
                pass

            # 确保 TeachingTip 在拦截层之上
            try:
                tip.raise_()
                tip.activateWindow()
            except Exception:
                pass

            # 由于 tip.raise_() 会改变 Z 序，这里再把 overlay raise 到下方一次，并刷新 spotlight
            try:
                overlay = getattr(self, "_quick_guide_modal_overlay", None)
                if overlay is not None:
                    overlay.raise_()
                    tip.raise_()
                self._update_teaching_tip_spotlight(target)
            except Exception:
                pass

            view = getattr(tip, "view", None)
            if view is None:
                raise RuntimeError("TeachingTip.view 不可用")

            # 提升可读性：标题更大加粗；标题/正文间隔一行
            try:
                view.setStyleSheet(
                    "QLabel#titleLabel{font-size: 13pt; font-weight: 600;}"
                    "QLabel#contentLabel{font-size: 12pt; margin-top: 8px;}"
                )
            except Exception:
                pass

            # 解决越界：启用换行 + 限制最大宽度
            try:
                self._configure_teaching_tip_view_for_wrapping(tip, view)
            except Exception:
                pass

            # 底部按钮（可见）
            self._add_teaching_tip_footer_buttons(view, step_index, total)

        except Exception:
            self._close_current_teaching_tip()
            self._teardown_teaching_tip_modal_blocker()
            self._run_quick_guide_step(step_index)

    def _on_teaching_tip_next(self, current_index: int):
        steps = self._get_quick_guide_steps()
        total = len(steps)
        next_idx = current_index + 1
        self._close_current_teaching_tip()
        if next_idx >= total:
            self._teardown_teaching_tip_modal_blocker()
            return
        QTimer.singleShot(80, lambda: self._run_quick_guide_step_teaching_tip(next_idx))

    def _on_teaching_tip_skip(self):
        self._close_current_teaching_tip()
        self._teardown_teaching_tip_modal_blocker()

    def _on_teaching_tip_finish(self):
        self._close_current_teaching_tip()
        self._teardown_teaching_tip_modal_blocker()

    def _run_quick_guide_step(self, step_index: int):
        steps = [
            (
                "模型选择",
                "点击“使用本地模型”打开弹窗，然后在弹窗内完成“下载依赖和模型”和“加载模型”。\n\n"
                "建议：首次使用请优先完成下载与加载，再进行生成。",
                lambda: getattr(self, "use_local_model_btn", None),
            ),
            (
                "角色列表",
                "在这里选择/新增角色。每个角色对应一套音色与参考音频配置。",
                lambda: getattr(self, "character_list_widget", None),
            ),
            (
                "导入参考音频",
                "在“音色参考音频”区域导入参考音频，用于复刻音色。也支持拖拽音频到界面导入。",
                lambda: getattr(self, "ref_player_widget", None),
            ),
            (
                "合成文本",
                "在文本框输入要合成的内容，然后点击“生成音频”。支持 Alt+Enter 快捷键生成。",
                lambda: getattr(self, "text_edit", None),
            ),
            (
                "情感控制",
                "可选择“与参考相同”或“使用情感向量控制”。使用向量控制时可通过滑块调整风格。",
                lambda: getattr(self, "emo_mode_same", None),
            ),
            (
                "生成结果",
                "生成完成后会在右侧展示 3 个候选样本，可播放试听并保存到本地。",
                lambda: getattr(self, "_output_stack_host", None),
            ),
        ]

        total = len(steps)
        if step_index < 0 or step_index >= total:
            self._quick_guide_dialog = None
            return

        title, desc, focus_getter = steps[step_index]

        # 尽量把焦点给到对应区域（非强制）
        try:
            w = focus_getter() if callable(focus_getter) else None
            if w is not None:
                try:
                    w.setFocus()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            dlg = AIVoiceQuickGuideStepDialog(
                self._main_window,
                step_title=title,
                step_desc=desc,
                step_index=step_index + 1,
                step_total=total,
            )

            # 按你的要求：每步必须点“下一步”才能继续操作 => 使用模态 exec()
            self._quick_guide_dialog = dlg
            res = dlg.exec()

            if res and dlg.choice == "next":
                next_idx = step_index + 1
                if next_idx >= total:
                    self._quick_guide_dialog = None
                    return
                QTimer.singleShot(80, lambda: self._run_quick_guide_step(next_idx))
                return

            # skip / close
            self._quick_guide_dialog = None
        except Exception:
            self._quick_guide_dialog = None

    def on_job_finished(self, success: bool):
        """Job 完成回调（由 MainWindow 调用）"""
        self._update_model_status()
        self._update_generate_btn_state()

    def _on_use_local_model_clicked(self):
        """打开“使用本地模型”弹窗，并在打开时触发一次环境检测（仅更新状态）。"""
        try:
            audiobox_root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
            save_dir = os.path.join(audiobox_root, "checkpoints")
            self._pending_save_dir = save_dir

            dlg = self._ensure_local_model_dialog()
            if dlg is None:
                return

            # 每次打开都刷新智能推荐文案/默认值（仅在用户未保存偏好时自动应用）
            try:
                self._apply_fp16_default(auto_only=True)
            except Exception:
                pass

            # 先做一次快速检查，确保弹窗一打开按钮状态就正确
            try:
                self._check_env_and_model()
            except Exception:
                pass

            # 触发一次完整依赖检查（不弹安装对话框、不自动下载）
            try:
                self._start_async_env_check(
                    save_dir,
                    show_install_dialog_on_missing=False,
                    on_ready="none",
                )
            except Exception:
                pass

            dlg.exec()
        except Exception:
            pass

    def _on_use_online_model_clicked(self):
        """打开“使用线上模型”弹窗（占位，后续实现 API 管理/模型选择）。"""
        try:
            dlg = OnlineModelDialog(self._main_window)
            dlg.exec()
        except Exception:
            pass

