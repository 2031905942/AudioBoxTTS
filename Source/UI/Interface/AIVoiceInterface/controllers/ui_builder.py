"""
UI Builder Mixin

Handles UI construction and initialization.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QVBoxLayout, QWidget, QLabel, QStackedLayout, QSizePolicy
)
from qfluentwidgets import (
    BodyLabel, CardWidget, FluentIcon,
    InfoBar, InfoBarPosition,
    MessageBox, PlainTextEdit, PrimaryPushButton, PushButton, RadioButton,
    Slider, TabCloseButtonDisplayMode, TransparentToolButton,
)

# NOTE: In the pre-refactor monolithic file these symbols were in the same module
# namespace. After splitting into mixins, each mixin must import what it uses.
from Source.UI.Basic.project_tab_bar import ProjectTabBar
from Source.UI.Interface.AIVoiceInterface.models.character_manager import CharacterManager
from Source.UI.Interface.AIVoiceInterface.widgets.character_list_widget import CharacterListWidget
from Source.UI.Interface.AIVoiceInterface.widgets.audio_player_widget import (
    ReferenceAudioPlayerWidget,
    ResultAudioPlayerWidget,
)
from Source.Utility.indextts_utility import IndexTTSUtility


class UIBuilderMixin:
    """Mixin for UI building operations."""

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


