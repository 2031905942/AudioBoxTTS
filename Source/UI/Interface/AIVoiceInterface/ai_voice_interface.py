"""
AI 语音界面 - IndexTTS2

"""
import os
import time
from typing import Optional

from PySide6.QtCore import QStandardPaths, QUrl, QRunnable, QThreadPool, QObject, Signal, Slot, Qt, QTimer
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QVBoxLayout, QWidget, QSizePolicy
)
from qfluentwidgets import (
    BodyLabel, CardWidget, FluentIcon, InfoBar, InfoBarPosition,
    MessageBox, PlainTextEdit, PrimaryPushButton, ProgressBar, PushButton, RadioButton,
    Slider, StrongBodyLabel, TitleLabel,
    ToolTipFilter, ToolTipPosition, TransparentToolButton
)

from Source.Utility.indextts_utility import IndexTTSUtility
from Source.UI.Interface.AIVoiceInterface.character_manager import CharacterManager, Character
from Source.UI.Interface.AIVoiceInterface.character_dialog import CharacterDialog
from Source.UI.Interface.AIVoiceInterface.character_list_widget import CharacterListWidget
from Source.UI.Interface.AIVoiceInterface.audio_player_widget import AudioPlayerWidget
from Source.UI.Basic.progress_bar_window import ProgressBarWindow


class ReferenceAudioCard(CardWidget):
    """支持拖拽的参考音频卡片"""
    
    audio_dropped = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._is_dragging = False
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.wav', '.mp3', '.flac', '.ogg')):
                event.acceptProposedAction()
                self._is_dragging = True
                self.update()
                return
        event.ignore()
        
    def dragLeaveEvent(self, event):
        self._is_dragging = False
        self.update()
        
    def dropEvent(self, event):
        self._is_dragging = False
        self.update()
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.wav', '.mp3', '.flac', '.ogg')):
                self.audio_dropped.emit(file_path)
                
    def paintEvent(self, event):
        super().paintEvent(event)
        if self._is_dragging:
            from PySide6.QtGui import QPainter, QPen, QColor
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 绘制虚线边框
            pen = QPen(QColor("#009faa"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(0, 159, 170, 20))
            rect = self.rect().adjusted(2, 2, -2, -2)
            painter.drawRoundedRect(rect, 10, 10)


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
        
        # 环境/模型是否就绪
        self._env_ready = False
        self._model_ready = False

        # 启用拖拽支持
        self.setAcceptDrops(True)

        self._init_ui()
        self._connect_signals()

    def dragEnterEvent(self, event):
        """处理拖拽进入事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.wav', '.mp3', '.flac', '.ogg')):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        """处理拖拽放下事件"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.wav', '.mp3', '.flac', '.ogg')):
                self._on_audio_dropped(file_path)

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
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 30))
        panel.setGraphicsEffect(shadow)
        
        panel.setStyleSheet("""
            CardWidget {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #e8e8e8;
            }
        """)
        
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 14)
        panel_layout.setSpacing(12)
        
        # 标题
        title_label = StrongBodyLabel("模型控制", panel)
        panel_layout.addWidget(title_label)
        
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
                background-color: #fde7e9;
                border: 1px solid #d13438;
                color: #d13438;
            }
            PushButton:hover {
                background-color: #fdd3d6;
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
        self.ref_player_widget = AudioPlayerWidget("Voice Reference", self, compact_mode=True)
        self.ref_player_widget.audio_dropped.connect(self._on_audio_dropped)
        
        # 添加导入按钮到标题栏
        self.ref_player_widget.add_tool_button(
            FluentIcon.ADD, "导入参考音频", self._on_import_audio
        )
        
        parent_layout.addWidget(self.ref_player_widget)

    def _create_text_input_card(self, parent_layout: QHBoxLayout):
        """创建合成文本输入卡片"""
        card = CardWidget(self)
        card.setMinimumWidth(300)
        card.setMinimumHeight(200)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # 标题
        title = StrongBodyLabel("合成文本", card)
        card_layout.addWidget(title)

        # 文本输入框（使用 qfluentwidgets 组件）
        self.text_edit = PlainTextEdit(card)
        self.text_edit.setPlaceholderText("在此输入要合成的文本内容...")
        self.text_edit.setMinimumHeight(120)
        card_layout.addWidget(self.text_edit, 1)

        # 调整占比：改为 1，使三栏等宽 (1:1:1)
        parent_layout.addWidget(card, 1)

    def _create_output_card(self, parent_layout: QHBoxLayout):
        """创建生成音频结果卡片"""
        container = CardWidget(self)
        container.setMinimumWidth(200)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 16)
        container_layout.setSpacing(12)
        
        # 上半部分：播放器 (AudioPlayerWidget 也是 CardWidget，这里嵌套使用或调整)
        # 为了保持样式一致，我们直接使用 AudioPlayerWidget 作为上半部分，
        # 但 AudioPlayerWidget 本身有边框和阴影。
        # 方案：AudioPlayerWidget 放在 container 内部，去掉 container 的 padding
        
        self.output_player_widget = AudioPlayerWidget("Synthesis Result", container)
        # 移除 AudioPlayerWidget 的边框和阴影，使其融入
        self.output_player_widget.setStyleSheet("CardWidget { border: none; background: transparent; }")
        
        # 添加下载按钮
        self.output_player_widget.add_tool_button(
            FluentIcon.DOWNLOAD, "保存音频", self._on_download_audio
        )
        
        container_layout.addWidget(self.output_player_widget)
        
        # 下半部分：控制区
        control_area = QWidget(container)
        control_layout = QVBoxLayout(control_area)
        control_layout.setContentsMargins(16, 0, 16, 0)
        control_layout.setSpacing(12)
        
        # 进度条
        self.generate_progress = ProgressBar(control_area)
        self.generate_progress.setRange(0, 100)
        self.generate_progress.setValue(0)
        self.generate_progress.setFixedHeight(6)
        self.generate_progress.setVisible(False)
        control_layout.addWidget(self.generate_progress)

        # 状态标签
        self.output_status_label = BodyLabel("等待生成", control_area)
        self.output_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.output_status_label.setStyleSheet("color: gray;")
        control_layout.addWidget(self.output_status_label)

        # 生成按钮
        self.generate_btn = PrimaryPushButton(FluentIcon.SEND, "生成音频", control_area)
        self.generate_btn.setEnabled(False)
        control_layout.addWidget(self.generate_btn)
        
        container_layout.addWidget(control_area)
        container_layout.addStretch()
        
        parent_layout.addWidget(container, 1)

    def _create_emotion_panel(self, parent_layout: QVBoxLayout):
        """创建情感控制面板"""
        card = CardWidget(self)
        card.setMinimumWidth(600)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # 标题
        title = StrongBodyLabel("情感控制", card)
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
        # self.output_play_btn.clicked.connect(self._on_play_output)
        # self.download_audio_btn.clicked.connect(self._on_download_audio)

        # 情感模式切换
        self.emo_mode_same.toggled.connect(self._on_emo_mode_changed)
        self.emo_mode_vector.toggled.connect(self._on_emo_mode_changed)

        # IndexTTSJob 信号
        self._main_window.indextts_job.progress_updated.connect(self._on_progress_updated)
        self._main_window.indextts_job.job_completed.connect(self._on_job_completed)
        
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
            f"确定要删除角色「{character.name}」吗？\n此操作不可撤销。",
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
        audiobox_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        save_dir = os.path.join(audiobox_root, "checkpoints")
        
        # 保存路径以防万一
        self._pending_save_dir = save_dir

        if self._is_delete_mode:
            # 删除模式：删除依赖和模型
            self._delete_model_files(save_dir)
        else:
            # 下载模式：先检查环境，再下载模型
            self._start_async_env_check(save_dir)

    def _start_async_env_check(self, save_dir: str):
        """异步检查环境"""
        self.download_btn.setEnabled(False)
        self.download_btn.setText("正在检测环境...")
        
        worker = EnvCheckWorker()
        worker.signals.finished.connect(lambda is_ready, msg: self._on_env_check_finished(is_ready, msg, save_dir))
        QThreadPool.globalInstance().start(worker)

    def _on_env_check_finished(self, is_ready: bool, msg: str, save_dir: str):
        """环境检测完成回调"""
        self.download_btn.setEnabled(True)
        # 检查当前状态（如果文件已存在，则更新为删除模式；否则保持下载模式）
        self._check_env_and_model()
        
        if not is_ready:
            # 提示安装环境
            msg_box = MessageBox(
                "环境缺失",
                f"检测到运行所需的 Python 依赖未安装。\n({msg})\n\n是否立即安装依赖并下载模型？",
                self._main_window
            )
            msg_box.yesButton.setText("安装并下载")
            msg_box.cancelButton.setText("取消")
            
            if msg_box.exec():
                self._pending_save_dir = save_dir
                
                # 连接信号，等待环境安装完成
                # 先断开可能的旧连接
                try:
                    self._main_window.indextts_env_job.job_completed.disconnect(self._on_env_job_finished)
                except:
                    pass
                self._main_window.indextts_env_job.job_completed.connect(self._on_env_job_finished)
                
                # 启动环境安装
                self._main_window.indextts_env_job.install_action()
            return

        # 2. 环境已就绪，直接进入模型下载流程
        self._download_model_files(save_dir)

    def _on_env_job_finished(self, success: bool):
        """环境安装完成回调"""
        # 断开信号
        try:
            self._main_window.indextts_env_job.job_completed.disconnect(self._on_env_job_finished)
        except:
            pass
            
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
            self._update_download_btn_state(is_complete=True)
            return

        # 显示确认对话框
        msg = MessageBox(
            "准备下载模型",
            f"环境依赖检测通过。\n\n即将下载模型文件到:\n{save_dir}\n\n文件大小约 5GB，请选择下载方式：",
            self._main_window
        )
        msg.yesButton.setText("镜像下载 (推荐)")
        msg.cancelButton.setText("取消")
        
        # 添加直连下载按钮
        direct_btn = PushButton("直连下载")
        msg.buttonLayout.insertWidget(1, direct_btn)
        
        # 添加删除环境依赖按钮
        delete_env_btn = PushButton("删除环境依赖")
        delete_env_btn.setStyleSheet("PushButton { color: #d13438; } PushButton:hover { background-color: #fde7e9; border: 1px solid #d13438; }")
        msg.buttonLayout.insertWidget(2, delete_env_btn)
        
        # 用于捕获用户选择
        choice = [None]
        
        def on_direct():
            choice[0] = 'direct'
            msg.accept()
            
        def on_delete_env():
            choice[0] = 'delete_env'
            msg.reject()
            
        direct_btn.clicked.connect(on_direct)
        delete_env_btn.clicked.connect(on_delete_env)

        res = msg.exec()
        
        if choice[0] == 'delete_env':
            QTimer.singleShot(100, lambda: self._delete_model_files(save_dir))
            return

        if res:
            use_mirror = (choice[0] != 'direct')
            # 开始下载
            self._main_window.indextts_download_job.download_action(
                save_dir, use_mirror=use_mirror
            )

    def _delete_model_files(self, save_dir: str):
        """删除模型文件"""
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

        # 确认删除
        msg = MessageBox(
            "删除依赖和模型",
            f"确定要删除 AI 语音相关的依赖和模型文件吗？\n\n"
            f"1. 删除模型目录: {save_dir}\n"
            f"2. 卸载 Python 依赖 (torch, transformers 等)\n\n"
            f"此操作将删除约 5GB 的文件，且不可撤销。",
            self._main_window
        )
        msg.yesButton.setText("确认删除")
        msg.cancelButton.setText("取消")
        
        # 设置删除按钮为危险样式
        msg.yesButton.setStyleSheet("""
            PushButton {
                background-color: #d13438;
                color: white;
            }
            PushButton:hover {
                background-color: #a4262c;
            }
        """)

        if not msg.exec():
            return

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
        
        # 添加要删除的文件夹 (如 qwen 模型文件夹和 hf_cache)
        dirs_to_delete = []
        for dir_name in ["qwen0.6bemo4-merge", "hf_cache"]:
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
            
            # 3. 启动依赖卸载 Job
            # 注意：这里应该调用 indextts_env_job 而不是 indextts_job
            self._main_window.indextts_env_job.uninstall_action()

            # 更新按钮状态 (假设卸载会成功，或者在 Job 完成回调中更新)
            self._update_download_btn_state(is_complete=False)
            self._env_ready = False
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
            self._update_download_btn_state(is_complete=False)
            self._env_ready = False
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

    def _update_download_btn_state(self, is_complete: bool):
        """更新下载/删除按钮状态"""
        if is_complete:
            # 切换为删除模式
            self._is_delete_mode = True
            self.download_btn.setText("删除依赖和模型")
            self.download_btn.setIcon(FluentIcon.DELETE)
            self.download_btn.setToolTip("删除 IndexTTS2 的依赖和模型文件以释放磁盘空间")
            if hasattr(self, "_model_btn_icon_size"):
                self.download_btn.setIconSize(self._model_btn_icon_size)
            self.download_btn.setStyleSheet(getattr(self, "_download_btn_style_delete", ""))
        else:
            # 切换为下载模式
            self._is_delete_mode = False
            self.download_btn.setText("下载依赖和模型")
            self.download_btn.setIcon(FluentIcon.DOWNLOAD)
            self.download_btn.setToolTip("下载 IndexTTS2 所需的依赖和模型文件（约 5GB）")
            if hasattr(self, "_model_btn_icon_size"):
                self.download_btn.setIconSize(self._model_btn_icon_size)
            self.download_btn.setStyleSheet(getattr(self, "_download_btn_style_download", ""))

    def _on_load_model_clicked(self):
        """加载/卸载模型"""
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
            self.load_model_btn.setText("卸载模型")
            self.load_model_btn.setIcon(FluentIcon.CLOSE) # 使用关闭图标区分
            self.load_model_btn.setStyleSheet(self._load_btn_style_unload)
            self._model_ready = True
        else:
            self.load_model_btn.setText("加载模型")
            self.load_model_btn.setIcon(FluentIcon.PLAY)
            self.load_model_btn.setStyleSheet(self._load_btn_style)
            self._model_ready = False
        
        self.load_model_btn.setEnabled(True)
        self._update_generate_btn_state()

    # ==================== 音频操作 ====================

    def _on_import_audio(self):
        """导入参考音频"""
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

    def _on_download_audio(self):
        """下载/保存生成的音频"""
        wav_path = self._main_window.indextts_job.last_wav_path
        if not wav_path or not os.path.exists(wav_path):
            InfoBar.warning(
                title="无可保存文件",
                content="请先生成音频",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        character = self._character_manager.selected_character
        
        # 获取建议路径
        if character:
            suggested_dir, suggested_name = self._character_manager.get_suggested_output_path(character.id)
        else:
            suggested_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MusicLocation)
            suggested_name = f"output_{int(time.time())}.wav"

        # 打开保存对话框
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存音频文件",
            os.path.join(suggested_dir, suggested_name),
            "WAV 音频 (*.wav);;所有文件 (*.*)"
        )

        if save_path:
            try:
                import shutil
                shutil.copy2(wav_path, save_path)
                
                # 记住保存位置
                if character:
                    self._character_manager.update_last_output(
                        character.id,
                        os.path.dirname(save_path),
                        os.path.basename(save_path)
                    )
                
                InfoBar.success(
                    title="保存成功",
                    content=os.path.basename(save_path),
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3000
                )
            except Exception as e:
                InfoBar.error(
                    title="保存失败",
                    content=str(e),
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3000
                )

    # ==================== 语音合成 ====================

    def _on_generate_clicked(self):
        """生成语音"""
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

        # 临时输出路径
        temp_dir = os.path.join(os.getcwd(), "temp_output")
        os.makedirs(temp_dir, exist_ok=True)
        output_path = os.path.join(temp_dir, f"temp_{int(time.time())}.wav")

        # 开始生成
        self._main_window.indextts_job.synthesize_action(
            spk_audio_path=character.reference_audio_path,
            text=text,
            output_path=output_path,
            emo_mode=emo_mode,
            emo_vector=emo_vector,
        )

        # 更新 UI 状态
        self.generate_btn.setEnabled(False)
        self.generate_progress.setVisible(True)
        self.generate_progress.setValue(0)
        self.output_status_label.setText("正在生成...")
        self.output_status_label.setStyleSheet("color: #0078d4;")

    def _on_emo_mode_changed(self):
        """情感模式切换"""
        self.vector_panel.setVisible(self.emo_mode_vector.isChecked())

    def _update_generate_btn_state(self):
        """更新生成按钮状态"""
        character = self._character_manager.selected_character
        job = self._main_window.indextts_job
        
        can_generate = (
            job.is_model_loaded and
            character is not None and
            character.reference_audio_path and
            os.path.exists(character.reference_audio_path)
        )
        self.generate_btn.setEnabled(can_generate)

    # ==================== 进度回调 ====================

    @Slot(float, str)
    def _on_progress_updated(self, progress: float, text: str):
        """进度更新回调"""
        percent = int(progress * 100)
        self.generate_progress.setValue(percent)
        if text:
            self.output_status_label.setText(text)

    @Slot(bool)
    def _on_job_completed(self, success: bool):
        """任务完成回调"""
        self._update_model_status()
        self._update_generate_btn_state()
        self.generate_progress.setVisible(False)
        
        if success:
            wav_path = self._main_window.indextts_job.last_wav_path
            if wav_path and os.path.exists(wav_path):
                self.output_player_widget.set_audio_path(wav_path)
                self.output_status_label.setText("生成成功")
                self.output_status_label.setStyleSheet("color: green;")
            else:
                self.output_status_label.setText("生成失败: 文件未找到")
                self.output_status_label.setStyleSheet("color: red;")
        else:
            self.output_status_label.setText("生成失败")
            self.output_status_label.setStyleSheet("color: red;")

    @Slot(bool)
    def _on_download_job_completed(self, success: bool):
        """下载任务完成回调"""
        if success:
            self._check_env_and_model()

    # ==================== 环境检测 ====================

    def _check_env_and_model(self):
        """检查环境和模型状态"""
        # 检查模型文件
        model_dir = IndexTTSUtility.get_default_model_dir()
        is_complete, _ = IndexTTSUtility.check_model_files(model_dir)
        
        # 更新下载/删除按钮状态
        self._update_download_btn_state(is_complete)
        self._env_ready = is_complete

        # 更新模型状态
        self._update_model_status()

    # ==================== 公共接口 ====================

    def refresh(self):
        """刷新界面状态（切换到此界面时调用）"""
        self._refresh_character_list()
        self._check_env_and_model()
        self._update_generate_btn_state()

        # 更新播放器状态
        wav_path = self._main_window.indextts_job.last_wav_path
        if wav_path and os.path.exists(wav_path):
            self.output_player_widget.set_audio_path(wav_path)
        else:
            self.output_player_widget.set_audio_path("")

    def on_job_finished(self, success: bool):
        """Job 完成回调（由 MainWindow 调用）"""
        self._update_model_status()
        self._update_generate_btn_state()

