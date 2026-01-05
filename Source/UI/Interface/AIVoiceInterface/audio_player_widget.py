import os
import numpy as np
import soundfile as sf
from PySide6.QtCore import Qt, Signal, QTimer, QUrl, QSize, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QAction, QFont, QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
    QGraphicsDropShadowEffect, QFrame, QStackedLayout
)
from qfluentwidgets import (
    CardWidget, FluentIcon, TransparentToolButton, 
    BodyLabel, CaptionLabel, ToolTipFilter, ToolTipPosition
)


class _UploadHintWidget(QFrame):
    """空状态提示：横向图标 + 文案，点击触发上传。"""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = QLabel(self)
        pm = self._make_upload_tray_pixmap(20)
        self._icon.setPixmap(pm)
        self._icon.setFixedSize(24, 24)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon, 0)

        self._text = QLabel("将音频拖入任意位置  -或-  点击上传", self)
        f = QFont()
        f.setPointSize(12)
        f.setBold(False)
        self._text.setFont(f)
        self._text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._text, 0)

    def _make_upload_tray_pixmap(self, size: int) -> QPixmap:
        """绘制托盘样式上传图标（上箭头 + U 型托盘），避免依赖特定 FluentIcon 枚举。"""
        s = int(size)
        pm = QPixmap(s, s)
        pm.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        c = self.palette().color(self.foregroundRole())
        pen = QPen(c, max(2, s // 10), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # 箭头
        cx = s * 0.5
        top = s * 0.18
        mid = s * 0.55
        painter.drawLine(QPoint(int(cx), int(mid)), QPoint(int(cx), int(top)))
        painter.drawLine(QPoint(int(cx), int(top)), QPoint(int(cx - s * 0.18), int(top + s * 0.18)))
        painter.drawLine(QPoint(int(cx), int(top)), QPoint(int(cx + s * 0.18), int(top + s * 0.18)))

        # 托盘（U 型）
        left = s * 0.22
        right = s * 0.78
        tray_top = s * 0.62
        tray_bottom = s * 0.82
        painter.drawLine(QPoint(int(left), int(tray_top)), QPoint(int(left), int(tray_bottom)))
        painter.drawLine(QPoint(int(right), int(tray_top)), QPoint(int(right), int(tray_bottom)))
        painter.drawLine(QPoint(int(left), int(tray_bottom)), QPoint(int(right), int(tray_bottom)))

        painter.end()
        return pm

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

class WaveformWidget(QWidget):
    """音频波形可视化组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self._bars = []  # 归一化的振幅数据 (0.0 - 1.0)
        self._progress = 0.0  # 播放进度 (0.0 - 1.0)
        self._bar_count = 60  # 条形数量
        self._bar_spacing = 2  # 间距
        self._color_played = QColor("#ff6b00")  # 已播放颜色 (橙色)
        self._color_remaining = QColor("#e0e0e0")  # 未播放颜色 (浅灰)
        self._cursor_color = QColor("#9c27b0")  # 光标颜色 (紫色)
        
        # 默认显示一些随机数据，避免空白
        self._generate_dummy_data()

    def _generate_dummy_data(self):
        """生成默认的随机波形数据"""
        self._bars = np.random.rand(self._bar_count) * 0.8 + 0.2
        self.update()

    def load_audio(self, file_path):
        """加载音频文件并生成波形数据"""
        if not os.path.exists(file_path):
            return

        try:
            # 使用 soundfile 读取音频
            data, samplerate = sf.read(file_path)
            
            # 如果是立体声，转为单声道
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
            
            # 降采样到目标条形数量
            # 将数据分成 N 个块，取每个块的最大绝对值
            chunk_size = len(data) // self._bar_count
            if chunk_size > 0:
                bars = []
                for i in range(self._bar_count):
                    start = i * chunk_size
                    end = start + chunk_size
                    chunk = data[start:end]
                    if len(chunk) > 0:
                        # 使用最大振幅，视觉效果更好
                        amplitude = np.max(np.abs(chunk))
                        bars.append(amplitude)
                    else:
                        bars.append(0.0)
                
                # 归一化
                bars = np.array(bars)
                max_val = np.max(bars)
                if max_val > 0:
                    bars = bars / max_val
                
                self._bars = bars
                self.update()
        except Exception as e:
            print(f"Error loading waveform: {e}")
            self._generate_dummy_data()

    def set_progress(self, progress):
        """设置播放进度 (0.0 - 1.0)"""
        self._progress = max(0.0, min(1.0, progress))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # 计算每个条形的宽度
        total_spacing = (self._bar_count - 1) * self._bar_spacing
        bar_width = (w - total_spacing) / self._bar_count
        
        # 绘制条形
        for i, value in enumerate(self._bars):
            x = i * (bar_width + self._bar_spacing)
            bar_height = max(4, value * h)  # 最小高度 4px
            y = (h - bar_height) / 2
            
            # 确定颜色
            bar_center_x = x + bar_width / 2
            cursor_x = self._progress * w
            
            if bar_center_x < cursor_x:
                painter.setBrush(self._color_played)
            else:
                painter.setBrush(self._color_remaining)
                
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, bar_width, bar_height, bar_width/2, bar_width/2)
            
        # 绘制光标线
        cursor_x = self._progress * w
        painter.setPen(QPen(self._cursor_color, 2))
        painter.drawLine(cursor_x, 0, cursor_x, h)


class AudioPlayerWidget(CardWidget):
    """现代化音频播放器组件"""
    
    # 信号
    play_requested = Signal()
    pause_requested = Signal()
    upload_requested = Signal()  # 空状态点击上传
    
    def __init__(self, title="Audio Player", parent=None, compact_mode=False):
        super().__init__(parent)
        self._audio_path = ""
        self._duration = 0
        self._is_playing = False
        self._compact_mode = compact_mode
        
        self._init_ui(title)
        self._init_player()
        
    def _init_ui(self, title_text):
        if self._compact_mode:
            self.setFixedHeight(80)
            self.setMinimumWidth(300)
            
            # 紧凑模式：水平布局
            self.main_layout = QHBoxLayout(self)
            self.main_layout.setContentsMargins(16, 10, 16, 10)
            self.main_layout.setSpacing(12)
            
            # 1. 标题/文件名 (左侧)
            self.title_label = BodyLabel(title_text, self)
            self.main_layout.addWidget(self.title_label)
            
            # 工具栏区域 (紧跟标题之后，或者放在最右侧？放在标题后比较合理，方便操作)
            self.tool_bar_layout = QHBoxLayout()
            self.tool_bar_layout.setSpacing(4)
            self.main_layout.addLayout(self.tool_bar_layout)
            
            # 2. 中间区域：空状态提示 / 波形显示（切换）
            self._center_host = QWidget(self)
            self._center_stack = QStackedLayout(self._center_host)
            self._center_stack.setContentsMargins(0, 0, 0, 0)

            self._empty_hint = _UploadHintWidget(self._center_host)
            self._empty_hint.clicked.connect(self.upload_requested.emit)
            self._center_stack.addWidget(self._empty_hint)

            self.waveform = WaveformWidget(self._center_host)
            self.waveform.setFixedHeight(40)
            self._center_stack.addWidget(self.waveform)

            self.main_layout.addWidget(self._center_host, 1)
            
            # 3. 播放按钮 (右侧)
            self.play_btn = TransparentToolButton(FluentIcon.PLAY_SOLID, self)
            self.play_btn.setFixedSize(40, 40)
            self.play_btn.setIconSize(QSize(18, 18))
            self.play_btn.setStyleSheet("""
                TransparentToolButton {
                    color: #ff6b00;
                    background-color: #fff0e0;
                    border-radius: 20px;
                }
                TransparentToolButton:hover {
                    background-color: #ffe0b2;
                }
                TransparentToolButton:pressed {
                    background-color: #ffcc80;
                }
            """)
            self.play_btn.clicked.connect(self._toggle_play)
            self.main_layout.addWidget(self.play_btn)
            
            # 创建隐藏的占位对象，防止 AttributeError
            self.icon_label = QLabel(self)
            self.icon_label.hide()
            self.current_time_label = QLabel(self)
            self.current_time_label.hide()
            self.total_time_label = QLabel(self)
            self.total_time_label.hide()

            # 初始为空状态：隐藏播放按钮 & 使用提示
            self._set_empty_state(True)
            
        else:
            # 标准模式
            self.setMinimumWidth(300)
            self.setMinimumHeight(160)
            
            # 布局
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(16, 12, 16, 16)
            self.main_layout.setSpacing(12)
            
            # === 1. 顶部标题栏 ===
            header_layout = QHBoxLayout()
            
            # 图标 + 标题
            self.icon_label = TransparentToolButton(FluentIcon.MUSIC, self)
            self.icon_label.setEnabled(False) # 仅作为图标使用
            self.title_label = BodyLabel(title_text, self)
            
            header_layout.addWidget(self.icon_label)
            header_layout.addWidget(self.title_label)
            header_layout.addStretch()
            
            # 工具栏区域 (用于添加自定义按钮，如关闭、下载)
            self.tool_bar_layout = QHBoxLayout()
            self.tool_bar_layout.setSpacing(4)
            header_layout.addLayout(self.tool_bar_layout)
            
            self.main_layout.addLayout(header_layout)
            
            # === 2. 波形显示 ===
            self.waveform = WaveformWidget(self)
            self.main_layout.addWidget(self.waveform)
            
            # === 3. 时间显示 ===
            time_layout = QHBoxLayout()
            self.current_time_label = CaptionLabel("0:00", self)
            self.current_time_label.setStyleSheet("color: #ff6b00;") # 橙色高亮
            self.total_time_label = CaptionLabel("0:00", self)
            self.total_time_label.setStyleSheet("color: gray;")
            
            time_layout.addWidget(self.current_time_label)
            time_layout.addStretch()
            time_layout.addWidget(self.total_time_label)
            self.main_layout.addLayout(time_layout)
            
            # === 4. 控制栏 ===
            controls_layout = QHBoxLayout()
            
            controls_layout.addStretch()
            
            # 中间：播放控制 (圆形纯净风格)
            self.play_btn = TransparentToolButton(FluentIcon.PLAY_SOLID, self)
            self.play_btn.setFixedSize(56, 56)
            self.play_btn.setIconSize(QSize(26, 26))
            self.play_btn.setStyleSheet("""
                TransparentToolButton {
                    color: #ff6b00;
                    background-color: #fff0e0;
                    border-radius: 28px;
                }
                TransparentToolButton:hover {
                    background-color: #ffe0b2;
                }
                TransparentToolButton:pressed {
                    background-color: #ffcc80;
                }
            """)
            self.play_btn.clicked.connect(self._toggle_play)
            
            controls_layout.addWidget(self.play_btn)
            
            controls_layout.addStretch()
            
            self.main_layout.addLayout(controls_layout)

    def _set_empty_state(self, empty: bool):
        """切换空状态（仅 compact_mode 需要）。"""
        if not getattr(self, "_compact_mode", False):
            return
        try:
            if empty:
                if hasattr(self, "_center_stack"):
                    self._center_stack.setCurrentWidget(self._empty_hint)
                if hasattr(self, "play_btn"):
                    self.play_btn.hide()
            else:
                if hasattr(self, "_center_stack"):
                    self._center_stack.setCurrentWidget(self.waveform)
                if hasattr(self, "play_btn"):
                    self.play_btn.show()
        except Exception:
            pass

    def _init_player(self):
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)

    def set_audio_path(self, path):
        """设置音频文件路径"""
        self._audio_path = path or ""

        # 空状态：未选择/文件不存在
        if not path or not os.path.exists(path):
            if getattr(self, "_compact_mode", False):
                self._set_empty_state(True)
            # 不要 disable 整个组件，否则无法点击上传
            try:
                self.title_label.setText("音色参考音频")
            except Exception:
                pass
            return

        # 已选择：加载波形并切回播放视图
        try:
            self.waveform.load_audio(path)
        except Exception:
            pass
        if getattr(self, "_compact_mode", False):
            self._set_empty_state(False)
        
        # 更新标题为文件名
        self.title_label.setText(os.path.basename(path))

        self.player.setSource(QUrl.fromLocalFile(path))
        self.setEnabled(True)

    def add_tool_button(self, icon, tooltip, callback):
        """在右上角添加工具按钮"""
        btn = TransparentToolButton(icon, self)
        btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        self.tool_bar_layout.addWidget(btn)
        return btn

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_position_changed(self, position):
        if self._duration > 0:
            progress = position / self._duration
            self.waveform.set_progress(progress)
            self.current_time_label.setText(self._format_time(position))

    def _on_duration_changed(self, duration):
        self._duration = duration
        self.total_time_label.setText(self._format_time(duration))

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setIcon(FluentIcon.PAUSE_BOLD)
        else:
            self.play_btn.setIcon(FluentIcon.PLAY_SOLID)

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.play_btn.setIcon(FluentIcon.PLAY_SOLID)
            self.waveform.set_progress(0)
            # 移除循环播放逻辑
            # if self.loop_btn.isChecked():
            #     self.player.play()

    def _format_time(self, ms):
        seconds = (ms // 1000) % 60
        minutes = (ms // 60000)
        return f"{minutes}:{seconds:02d}"

