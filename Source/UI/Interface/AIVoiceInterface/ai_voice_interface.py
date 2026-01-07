"""
AI 语音界面 - IndexTTS2

"""
import os
import time
from typing import Optional

from PySide6.QtCore import QStandardPaths, QUrl, QRunnable, QThreadPool, QObject, Signal, Slot, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QShortcut, QKeySequence
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QVBoxLayout, QWidget, QSizePolicy, QStackedLayout, QLabel, QDialog
)
from qfluentwidgets import (
    BodyLabel, CardWidget, FluentIcon, InfoBar, InfoBarPosition,
    MessageBox, MessageBoxBase, PlainTextEdit, PrimaryPushButton, ProgressBar, PushButton, RadioButton,
    Slider, StrongBodyLabel, TitleLabel,
    ToolTipFilter, ToolTipPosition, TransparentToolButton
)

from Source.Utility.indextts_utility import IndexTTSUtility
from Source.UI.Interface.AIVoiceInterface.character_manager import CharacterManager, Character
from Source.UI.Interface.AIVoiceInterface.character_dialog import CharacterDialog
from Source.UI.Interface.AIVoiceInterface.character_list_widget import CharacterListWidget
from Source.UI.Interface.AIVoiceInterface.audio_player_widget import ReferenceAudioPlayerWidget, ResultAudioPlayerWidget
from Source.UI.Basic.progress_bar_window import ProgressBarWindow


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

        title = BodyLabel("环境缺失", self)
        self.viewLayout.addWidget(title)

        content = BodyLabel(
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
    - 顶部：标题 + 模型控制按钮
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

        # 角色管理器
        self._character_manager = CharacterManager()

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

        # ========== 顶部：角色列表 + 模型控制 ==========
        self._create_top_section(main_layout)

        # ========== 中部三栏布局 ==========
        self._create_main_content(main_layout)

        # ========== 底部情感控制 ==========
        self._create_emotion_panel(main_layout)

        # 添加弹性空间
        main_layout.addStretch()
    
    def _create_top_section(self, parent_layout: QVBoxLayout):
        """创建顶部区域（角色列表 + 模型控制）"""
        top_widget = QWidget(self)
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(16)
        
        # === 左侧：角色列表（占 2/3 宽度）===
        self.character_list_widget = CharacterListWidget(
            self._character_manager, self
        )
        self.character_list_widget.character_selected.connect(self._on_character_selected)
        self.character_list_widget.character_edit_requested.connect(self._on_character_edit)
        self.character_list_widget.character_delete_requested.connect(self._on_character_delete)
        self.character_list_widget.add_character_requested.connect(self._on_add_character)
        top_layout.addWidget(self.character_list_widget, 2)  # stretch factor 2
        
        # === 右侧：模型控制面板（占 1/3 宽度）===
        self._create_model_control_panel(top_layout)
        
        parent_layout.addWidget(top_widget)
    
    def _create_model_control_panel(self, parent_layout: QHBoxLayout):
        """创建模型控制面板"""
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor
        from PySide6.QtCore import QSize
        
        # 使用 CardWidget 包装
        panel = CardWidget(self)
        
        # 移除手动设置的阴影和背景色，使用 CardWidget 的默认主题样式
        # 这样可以保证在不同主题（亮/暗）下显示一致，且不会过亮
        
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 14)
        panel_layout.setSpacing(12)
        
        # 标题（模型加载后可点击查看诊断信息）
        self.model_control_title_btn = PushButton("模型控制", panel)
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

        # 下载/删除依赖和模型按钮
        self.download_btn = PushButton(FluentIcon.DOWNLOAD, "下载依赖和模型", panel)
        self.download_btn.setMinimumHeight(40)
        self.download_btn.setIconSize(self._model_btn_icon_size)
        self.download_btn.setToolTip("下载 IndexTTS2 所需的依赖和模型文件（约 5GB）")
        self.download_btn.setStyleSheet(self._download_btn_style_download)
        panel_layout.addWidget(self.download_btn)

        # 加载/卸载模型按钮
        self.load_model_btn = PushButton(FluentIcon.PLAY, "加载模型", panel)
        self.load_model_btn.setMinimumHeight(40)
        self.load_model_btn.setIconSize(self._model_btn_icon_size)
        self.load_model_btn.setToolTip("加载模型到显存（首次约需 20-30 秒）")
        self.load_model_btn.setStyleSheet(self._load_btn_style)
        panel_layout.addWidget(self.load_model_btn)
        
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
        self._history_btn.setToolTip("历史记录（暂未实现）")
        self._history_btn.setEnabled(False)
        self._history_btn.setFixedSize(32, 32)
        header_layout.addWidget(self._history_btn, 0, Qt.AlignmentFlag.AlignRight)

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
            w = ResultAudioPlayerWidget(f"样本 {i + 1}", outputs_view)
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
                if cur == 0:
                    return
                self._output_stack.setCurrentIndex(0)
                return

            # non-empty
            if cur == 1:
                return
            self._output_stack.setCurrentIndex(1)
            # 非空态会显著增加内容高度：主动让主窗口增高，避免控件被挤压造成“视觉重叠”
            self._grow_window_to_fit_contents()
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
        # 模型控制
        self.download_btn.clicked.connect(self._on_download_clicked)
        self.load_model_btn.clicked.connect(self._on_load_model_clicked)

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

    # ==================== 角色管理 ====================

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

    def _on_character_edit(self, character_id: str):
        """编辑角色"""
        character = self._character_manager.get_by_id(character_id)
        if not character:
            return

        dialog = CharacterDialog(
            self._main_window,
            character_name=character.name,
            avatar_path=character.avatar_path
        )
        if dialog.exec():
            name, avatar_path = dialog.get_data()
            if name:
                self._character_manager.update(
                    character_id,
                    name=name,
                    avatar_path=avatar_path
                )
                self._refresh_character_list()
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
            self._character_manager.delete(character_id)
            self._refresh_character_list()
            InfoBar.success(
                title="角色已删除",
                content=f"已删除角色: {character.name}",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000
            )

    def _select_character(self, character_id: str):
        """选中角色（不置顶）"""
        self._character_manager.select(character_id)
        
        # 更新角色列表选中状态
        self.character_list_widget.update_selection(character_id)
        
        # 更新参考音频显示
        self._update_reference_audio_display()
        
        # 更新生成按钮状态
        self._update_generate_btn_state()

    def _refresh_character_list(self):
        """刷新角色列表"""
        self.character_list_widget.refresh()
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

    # ==================== 模型控制 ====================

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

        # 若模型齐全但环境缺失：提供“下载环境依赖”入口（保持弹窗样式一致）
        if getattr(self, "_model_files_ok", False) and (not getattr(self, "_env_ok_fast", False)):
            self._show_fix_env_dialog(save_dir)
            return

        if self._is_delete_mode:
            # 删除模式：让用户选择删除模型 or 删除依赖
            self._show_delete_assets_dialog(save_dir)
            return

        # 下载模式：先检查环境，再下载模型
        self._start_async_env_check(save_dir)

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

    def _start_async_env_check(self, save_dir: str):
        """异步检查环境"""
        if self._env_check_pending:
            return

        self._env_check_pending = True
        self._env_check_request_id += 1
        request_id = self._env_check_request_id

        self.download_btn.setEnabled(False)
        self.download_btn.setText("正在检测环境...")

        worker = EnvCheckWorker()
        # Keep a strong reference to avoid Python GC interrupting signal delivery.
        try:
            worker.setAutoDelete(False)
        except Exception:
            pass
        self._env_check_worker = worker

        worker.signals.finished.connect(
            lambda is_ready, msg: self._on_env_check_finished(request_id, is_ready, msg, save_dir)
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
        self.download_btn.setEnabled(True)
        self._check_env_and_model()

        InfoBar.warning(
            title="环境检测超时",
            content="环境检测耗时过长，请稍后重试或直接点击“安装并下载”。",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=4500
        )

    def _on_env_check_finished(self, request_id: int, is_ready: bool, msg: str, save_dir: str):
        """环境检测完成回调"""
        if request_id != self._env_check_request_id:
            return

        self._env_check_pending = False
        self._env_check_worker = None
        self.download_btn.setEnabled(True)
        # 检查当前状态（如果文件已存在，则更新为删除模式；否则保持下载模式）
        self._check_env_and_model()
        
        if not is_ready:
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

        # 2. 环境已就绪，直接进入模型下载流程
        self._download_model_files(save_dir)

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
        # 1) 配置完成：允许删除
        if env_ok and model_ok:
            self._is_delete_mode = True
            self.download_btn.setText("配置完成，点击可删除")
            # 视觉保持与“加载完成，点击可卸载”一致：浅蓝 + 对勾
            self.download_btn.setIcon(FluentIcon.ACCEPT)
            self.download_btn.setToolTip("删除 IndexTTS2 的依赖和模型文件以释放磁盘空间")
            if hasattr(self, "_model_btn_icon_size"):
                self.download_btn.setIconSize(self._model_btn_icon_size)
            self.download_btn.setStyleSheet(getattr(self, "_load_btn_style_unload", ""))
            return

        # 2) 仅环境缺失：保持黄色样式，但引导下载环境依赖
        if (not env_ok) and model_ok:
            self._is_delete_mode = False
            self.download_btn.setText("缺乏依赖，点击可下载")
            self.download_btn.setIcon(FluentIcon.DOWNLOAD)
            self.download_btn.setToolTip("检测到环境依赖缺失，点击可下载/安装环境依赖")
            if hasattr(self, "_model_btn_icon_size"):
                self.download_btn.setIconSize(self._model_btn_icon_size)
            # 复用当前“配置完成”黄色样式
            self.download_btn.setStyleSheet(getattr(self, "_download_btn_style_delete", ""))
            return

        # 3) 其余情况：下载依赖和模型
        self._is_delete_mode = False
        self.download_btn.setText("下载依赖和模型")
        self.download_btn.setIcon(FluentIcon.DOWNLOAD)
        self.download_btn.setToolTip("下载 IndexTTS2 所需的依赖和模型文件（约 5GB）")
        if hasattr(self, "_model_btn_icon_size"):
            self.download_btn.setIconSize(self._model_btn_icon_size)
        self.download_btn.setStyleSheet(getattr(self, "_download_btn_style_download", ""))

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

            job.load_model_action(
                model_dir,
                use_fp16=False,
                use_cuda_kernel=False,
                use_deepspeed=False
            )
            
            self.load_model_btn.setEnabled(False)
            self.load_model_btn.setText("加载中...")
    
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
        
        if job.is_model_loaded:
            self.load_model_btn.setText("加载完成，点击可卸载")
            self.load_model_btn.setIcon(FluentIcon.ACCEPT)
            self.load_model_btn.setStyleSheet(self._load_btn_style_unload)
            self._model_ready = True

            # 标题切换为“使用中 + 设备信息”，并允许点击查看详情
            try:
                device = getattr(job, "device", "")
                device = device() if callable(device) else device
            except Exception:
                device = ""

            device_text = str(device).strip() if device else "未知"
            self.model_control_title_btn.setText(f"模型正在使用中，使用设备：{device_text}")
            self.model_control_title_btn.setEnabled(True)
            self.model_control_title_btn.setToolTip("点击查看更详细的模型/显存信息")
        else:
            self.load_model_btn.setText("加载模型")
            self.load_model_btn.setIcon(FluentIcon.PLAY)
            self.load_model_btn.setStyleSheet(self._load_btn_style)
            self._model_ready = False

            # 未加载时恢复普通标题且不响应点击
            self.model_control_title_btn.setText("模型控制")
            self.model_control_title_btn.setEnabled(False)
            self.model_control_title_btn.setToolTip("")
        
        self.load_model_btn.setEnabled(True)
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

        # 临时输出路径（一次生成 3 个候选样本）
        temp_dir = os.path.join(os.getcwd(), "temp_output")
        os.makedirs(temp_dir, exist_ok=True)
        ts = int(time.time())
        output_paths = [
            os.path.join(temp_dir, f"temp_{ts}_v{i + 1}.wav")
            for i in range(3)
        ]

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
            self.download_btn.setEnabled(True)
        self._env_ready = bool(env_ok and model_ok)

        # 更新模型状态
        self._update_model_status()

    # ==================== 公共接口 ====================

    def refresh(self):
        """刷新界面状态（切换到此界面时调用）"""
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

    def on_job_finished(self, success: bool):
        """Job 完成回调（由 MainWindow 调用）"""
        self._update_model_status()
        self._update_generate_btn_state()

