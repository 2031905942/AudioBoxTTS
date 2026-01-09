import os
import math
import numpy as np
import soundfile as sf
from datetime import datetime
from PySide6.QtCore import Qt, Signal, QTimer, QUrl, QSize, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QAction, QFont, QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
    QGraphicsDropShadowEffect, QFrame, QStackedLayout
)
from qfluentwidgets import (
    CardWidget, FluentIcon, TransparentToolButton, 
    BodyLabel, CaptionLabel, ToolTipFilter, ToolTipPosition, ProgressBar, IconWidget
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

        # 使用 FluentIcon 替代手绘图标，保持风格一致
        self._icon = IconWidget(self)
        try:
            # 当前版本 FluentIcon 没有 UPLOAD/CLOUD_UPLOAD，使用接近的 UP
            self._icon.setIcon(FluentIcon.UP)
        except Exception:
            pass
        self._icon.setFixedSize(24, 24)
        layout.addWidget(self._icon, 0)

        self._text = QLabel("将音频拖入任意位置  -或-  点击上传", self)
        f = QFont()
        f.setPointSize(12)
        f.setBold(False)
        self._text.setFont(f)
        self._text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._text, 0)

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

        self._duration_ms: int = 0
        self._position_ms: int = 0
        self._show_timestamps: bool = False
        # 时间戳区域高度（会在 paintEvent 中根据字体动态兜底）
        self._timestamp_area_h: int = 16
        
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
            # 避免在终端刷屏（历史记录可能一次加载很多条）
            self._generate_dummy_data()

    def set_progress(self, progress):
        """设置播放进度 (0.0 - 1.0)"""
        self._progress = max(0.0, min(1.0, progress))
        self.update()

    def set_duration_ms(self, duration_ms: int):
        self._duration_ms = max(0, int(duration_ms or 0))
        self.update()

    def set_position_ms(self, position_ms: int):
        self._position_ms = max(0, int(position_ms or 0))
        self.update()

    def set_timestamps_enabled(self, enabled: bool):
        self._show_timestamps = bool(enabled)
        self.update()

    def set_timestamp_area_height(self, px: int):
        """设置时间戳区域高度（像素）。"""
        try:
            self._timestamp_area_h = max(10, int(px))
        except Exception:
            self._timestamp_area_h = 16
        self.update()

    def apply_monochrome(self, enabled: bool = True):
        """将波形颜色切换为黑白系（根据 palette 自动适配）。"""
        if not enabled:
            self._color_played = QColor("#ff6b00")
            self._color_remaining = QColor("#e0e0e0")
            self._cursor_color = QColor("#9c27b0")
            self.update()
            return

        text = self.palette().color(self.foregroundRole())
        self._color_played = QColor(text)
        self._color_played.setAlpha(220)

        self._color_remaining = QColor(text)
        self._color_remaining.setAlpha(60)

        self._cursor_color = QColor(text)
        self._cursor_color.setAlpha(200)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()

        timestamp_h = 0
        bar_area_h = h
        if self._show_timestamps:
            # 根据当前字体高度动态兜底，避免高 DPI 下文字被裁剪
            font = QFont(self.font())
            font.setPointSize(max(8, font.pointSize() - 2))
            painter.setFont(font)
            metrics = painter.fontMetrics()
            timestamp_h = max(int(self._timestamp_area_h), int(metrics.height() + 2))
            bar_area_h = max(1, h - timestamp_h)
        
        # 计算每个条形的宽度
        total_spacing = (self._bar_count - 1) * self._bar_spacing
        bar_width = (w - total_spacing) / self._bar_count
        
        # 绘制条形
        for i, value in enumerate(self._bars):
            x = i * (bar_width + self._bar_spacing)
            bar_height = max(4, value * bar_area_h)  # 最小高度 4px
            y = (bar_area_h - bar_height) / 2
            
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
        painter.drawLine(cursor_x, 0, cursor_x, bar_area_h)

        # 时间戳（紧凑模式使用）：左 0:00，右 总时长，光标处 当前时间
        if self._show_timestamps:
            timestamp_y = bar_area_h
            text_color = QColor(self.palette().color(self.foregroundRole()))
            text_color.setAlpha(150)
            painter.setPen(QPen(text_color))

            def _fmt(ms: int) -> str:
                s = int(ms // 1000)
                return f"{s // 60}:{s % 60:02d}"

            total_text = _fmt(self._duration_ms) if self._duration_ms > 0 else ""
            left_text = "0:00" if self._duration_ms > 0 else ""
            current_text = _fmt(self._position_ms) if self._duration_ms > 0 else ""

            if left_text:
                painter.drawText(0, timestamp_y, w, timestamp_h, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, left_text)
            if total_text:
                painter.drawText(0, timestamp_y, w, timestamp_h, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, total_text)

            if current_text:
                # 在光标附近绘制当前时间，避免超出边界
                metrics = painter.fontMetrics()
                text_w = metrics.horizontalAdvance(current_text)
                x0 = int(cursor_x - text_w / 2)
                x0 = max(0, min(w - text_w, x0))
                painter.drawText(x0, timestamp_y, text_w, timestamp_h, Qt.AlignmentFlag.AlignCenter, current_text)


class AudioPlayerWidget(CardWidget):
    """现代化音频播放器组件"""
    
    # 信号
    play_requested = Signal()
    pause_requested = Signal()
    upload_requested = Signal()  # 空状态点击上传
    clear_requested = Signal()   # 请求清空音频（右上角叉号）
    
    def __init__(
        self,
        title="Audio Player",
        parent=None,
        compact_mode=False,
        *,
        compact_empty_hint: str = "upload",
        show_clear_button: bool = True,
        clear_tooltip: str = "移除音频",
        title_follows_filename: bool = True,
    ):
        super().__init__(parent)
        self._audio_path = ""
        # QMediaPlayer 懒加载：避免在列表渲染阶段对每个音频都触发底层探测/日志输出
        self._player_source_path = ""
        self._duration = 0
        self._is_playing = False
        self._compact_mode = compact_mode
        # 紧凑模式空态提示："upload"(参考音频) / "none"(输出样本)
        self._compact_empty_hint = (compact_empty_hint or "upload").strip().lower()
        self._show_clear_button = bool(show_clear_button)
        self._clear_tooltip = str(clear_tooltip)
        self._title_follows_filename = bool(title_follows_filename)
        self._base_title_text = str(title)

        self._tool_buttons = []
        self._loading = False
        self._loading_overlay = None
        
        self._init_ui(title)
        self._init_player()

    @staticmethod
    def _format_datetime_from_mtime(path: str) -> str:
        try:
            ts = os.path.getmtime(path)
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ""

    @staticmethod
    def _guess_bit_depth_from_subtype(subtype: str) -> int | None:
        s = str(subtype or "").upper()
        # 常见：PCM_16 / PCM_24 / PCM_32 / FLOAT / DOUBLE
        for n in (8, 16, 24, 32, 64):
            if f"_{n}" in s or s.endswith(str(n)):
                return n
        if "FLOAT" in s:
            return 32
        if "DOUBLE" in s:
            return 64
        return None

    def _build_audio_tooltip(self, path: str) -> str:
        """构建悬停提示文本（更可读，替代终端的 ffmpeg dump）。"""
        if not path:
            return ""
        try:
            base = os.path.basename(path)
        except Exception:
            base = path

        info = None
        try:
            info = sf.info(path)
        except Exception:
            info = None

        lines: list[str] = []
        lines.append(f"文件：{base}")

        created = self._format_datetime_from_mtime(path)
        if created:
            lines.append(f"生成时间：{created}")

        if info is not None:
            try:
                dur_s = float(getattr(info, "duration", 0.0) or 0.0)
            except Exception:
                dur_s = 0.0

            try:
                sr = int(getattr(info, "samplerate", 0) or 0)
            except Exception:
                sr = 0

            try:
                ch = int(getattr(info, "channels", 0) or 0)
            except Exception:
                ch = 0

            subtype = str(getattr(info, "subtype", "") or "")
            fmt = str(getattr(info, "format", "") or "")
            bit_depth = self._guess_bit_depth_from_subtype(subtype)

            if dur_s > 0:
                lines.append(f"时长：{dur_s:.2f}s")
            if sr > 0:
                lines.append(f"采样率：{sr} Hz")
            if ch > 0:
                lines.append(f"声道：{ch}")
            if bit_depth is not None:
                lines.append(f"位深：{bit_depth}-bit")
            if subtype or fmt:
                codec_text = subtype if subtype else fmt
                lines.append(f"格式：{codec_text}")

            # PCM 类 wav 码率可由采样率*声道*位深估算（kb/s）
            try:
                if sr > 0 and ch > 0 and bit_depth is not None and bit_depth > 0:
                    kbps = int(round((sr * ch * bit_depth) / 1000.0))
                    lines.append(f"码率：{kbps} kb/s")
            except Exception:
                pass

        # 最后一行给路径，方便定位
        lines.append(f"路径：{path}")
        return "\n".join(lines)

    def _apply_tooltip(self, text: str):
        if not text:
            return
        try:
            self.setToolTip(text)
        except Exception:
            pass
        # 常用可悬停区域也同步一份，提升可发现性
        for w in (getattr(self, "title_label", None), getattr(self, "waveform", None), getattr(self, "play_btn", None)):
            if w is None:
                continue
            try:
                w.setToolTip(text)
            except Exception:
                pass

    def _apply_duration_from_file(self, path: str):
        """在不触发 QMediaPlayer 探测的前提下设置总时长。"""
        try:
            info = sf.info(path)
            dur_s = float(getattr(info, "duration", 0.0) or 0.0)
            dur_ms = int(max(0.0, dur_s) * 1000)
        except Exception:
            dur_ms = 0

        if dur_ms <= 0:
            return

        try:
            self._duration = dur_ms
        except Exception:
            pass
        try:
            self.total_time_label.setText(self._format_time(dur_ms))
        except Exception:
            pass
        try:
            self.waveform.set_duration_ms(dur_ms)
        except Exception:
            pass

    def _ensure_player_source(self) -> bool:
        """仅在需要播放时才 setSource，避免列表渲染阶段批量触发底层探测输出。"""
        path = str(getattr(self, "_audio_path", "") or "")
        if not path or not os.path.exists(path):
            return False
        if getattr(self, "_player_source_path", "") == path:
            return True
        try:
            self.player.setSource(QUrl.fromLocalFile(path))
            self._player_source_path = path
            return True
        except Exception:
            return False
        
    def _init_ui(self, title_text):
        if self._compact_mode:
            # 不要用过小 fixed height（高 DPI / 字体变化会导致内部控件被压扁重叠）
            self.setMinimumHeight(112)
            self.setMinimumWidth(300)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

            # 紧凑模式：上方弱化文件名 + 右上角清空；下方波形 + 播放
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(12, 10, 12, 10)
            self.main_layout.setSpacing(6)

            header_layout = QHBoxLayout()
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(6)

            # 文件名：弱化、放左上角
            self.title_label = CaptionLabel(title_text, self)
            self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            header_layout.addWidget(self.title_label, 1)

            # 紧凑模式工具按钮区域（例如下载）
            self.tool_bar_layout = QHBoxLayout()
            self.tool_bar_layout.setContentsMargins(0, 0, 0, 0)
            self.tool_bar_layout.setSpacing(4)
            header_layout.addLayout(self.tool_bar_layout)

            # 右上角清空按钮
            if self._show_clear_button:
                self.clear_btn = TransparentToolButton(FluentIcon.CLOSE, self)
                self.clear_btn.setFixedSize(28, 28)
                self.clear_btn.setIconSize(QSize(12, 12))
                self.clear_btn.setToolTip(self._clear_tooltip)
                self.clear_btn.clicked.connect(self.clear_requested.emit)
                header_layout.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignRight)
            else:
                self.clear_btn = None

            self.main_layout.addLayout(header_layout)

            body_layout = QHBoxLayout()
            body_layout.setContentsMargins(0, 0, 0, 0)
            body_layout.setSpacing(10)

            # 中间区域：空状态提示 / 波形显示（切换）
            self._center_host = QWidget(self)
            self._center_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._center_host.setMinimumHeight(56)

            self.waveform = WaveformWidget(self._center_host)
            self.waveform.setFixedHeight(56)
            self.waveform.set_timestamps_enabled(True)
            self.waveform.set_timestamp_area_height(16)
            self.waveform.apply_monochrome(True)

            self._center_stack = None
            self._empty_hint = None
            if self._compact_empty_hint == "upload":
                # 仅参考音频区域需要导入提示
                self._center_stack = QStackedLayout(self._center_host)
                self._center_stack.setContentsMargins(0, 0, 0, 0)

                self._empty_hint = _UploadHintWidget(self._center_host)
                self._empty_hint.clicked.connect(self.upload_requested.emit)
                self._center_stack.addWidget(self._empty_hint)
                self._center_stack.addWidget(self.waveform)
            else:
                # 输出样本：不允许显示“导入音频”空态，始终展示波形占位（加载遮罩会覆盖）
                host_layout = QVBoxLayout(self._center_host)
                host_layout.setContentsMargins(0, 0, 0, 0)
                host_layout.setSpacing(0)
                host_layout.addWidget(self.waveform)

            body_layout.addWidget(self._center_host, 1)

            # 播放按钮：黑白简洁风格，交互由 qfluentwidgets 接管
            self.play_btn = TransparentToolButton(FluentIcon.PLAY_SOLID, self)
            self.play_btn.setFixedSize(36, 36)
            self.play_btn.setIconSize(QSize(18, 18))
            self.play_btn.clicked.connect(self._toggle_play)
            body_layout.addWidget(self.play_btn, 0, Qt.AlignmentFlag.AlignVCenter)

            self.main_layout.addLayout(body_layout)
            
            # 创建隐藏的占位对象，防止 AttributeError
            self.icon_label = QLabel(self)
            self.icon_label.hide()
            self.current_time_label = QLabel(self)
            self.current_time_label.hide()
            self.total_time_label = QLabel(self)
            self.total_time_label.hide()

            # 初始为空状态：隐藏播放按钮 & 使用提示
            self._set_empty_state(True)
            if self.clear_btn is not None:
                try:
                    self.clear_btn.hide()
                except Exception:
                    pass
            
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
            self.waveform.set_timestamps_enabled(False)
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
            self.play_btn.clicked.connect(self._toggle_play)
            
            controls_layout.addWidget(self.play_btn)
            
            controls_layout.addStretch()
            
            self.main_layout.addLayout(controls_layout)

        # 生成遮罩层（默认隐藏）：三点加载动画 + 进度条
        try:
            self._loading_overlay = _LoadingOverlay(self)
            self._loading_overlay.hide()
            self._loading_overlay.raise_()
        except Exception:
            self._loading_overlay = None

    def _set_empty_state(self, empty: bool):
        """切换空状态（仅 compact_mode 需要）。"""
        if not getattr(self, "_compact_mode", False):
            return
        try:
            if empty:
                if getattr(self, "_compact_empty_hint", "upload") == "upload":
                    if getattr(self, "_center_stack", None) is not None and getattr(self, "_empty_hint", None) is not None:
                        self._center_stack.setCurrentWidget(self._empty_hint)
                if hasattr(self, "play_btn"):
                    self.play_btn.hide()
                if getattr(self, "clear_btn", None) is not None:
                    self.clear_btn.hide()
            else:
                if getattr(self, "_compact_empty_hint", "upload") == "upload":
                    if getattr(self, "_center_stack", None) is not None:
                        self._center_stack.setCurrentWidget(self.waveform)
                if hasattr(self, "play_btn"):
                    self.play_btn.show()
                if getattr(self, "clear_btn", None) is not None:
                    self.clear_btn.show()
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
        # 切换文件时重置懒加载状态
        try:
            self._player_source_path = ""
        except Exception:
            pass

        # 若之前在播放其它音频，先停止（避免切换资源时状态混乱）
        try:
            self.player.stop()
        except Exception:
            pass

        # 空状态：未选择/文件不存在
        if not path or not os.path.exists(path):
            # 释放媒体源，避免 Windows 下文件句柄占用导致无法删除/改名
            try:
                self.release_media()
            except Exception:
                pass
            if getattr(self, "_compact_mode", False):
                self._set_empty_state(True)
            # 不要 disable 整个组件，否则无法点击上传
            try:
                self.title_label.setText(self._base_title_text)
            except Exception:
                pass
            try:
                self.waveform.set_progress(0)
                self.waveform.set_duration_ms(0)
                self.waveform.set_position_ms(0)
            except Exception:
                pass
            try:
                self.player.stop()
            except Exception:
                pass
            # 清空 tooltip
            try:
                self.setToolTip("")
            except Exception:
                pass
            return

        # 已选择：加载波形并切回播放视图
        try:
            self.waveform.load_audio(path)
        except Exception:
            pass

        # 读取音频元信息：用于 tooltip + 在不触发 QMediaPlayer 的情况下设置总时长
        try:
            self._apply_duration_from_file(path)
        except Exception:
            pass
        try:
            self._apply_tooltip(self._build_audio_tooltip(path))
        except Exception:
            pass
        if getattr(self, "_compact_mode", False):
            self._set_empty_state(False)
        
        # 标题策略：参考音频需要显示文件名；输出样本可保持固定标题
        if self._title_follows_filename:
            try:
                self.title_label.setText(os.path.basename(path))
            except Exception:
                pass
        else:
            try:
                self.title_label.setText(self._base_title_text)
            except Exception:
                pass

        # 不在这里 setSource：避免历史记录一次性创建很多控件时，底层对每个文件探测并向终端输出
        self.setEnabled(True)

    def release_media(self):
        """停止播放并清空 QMediaPlayer 的 source，释放文件句柄（Windows 改名/删除需要）。"""
        try:
            if hasattr(self, "player") and self.player is not None:
                try:
                    self.player.stop()
                except Exception:
                    pass
                try:
                    from PySide6.QtCore import QUrl

                    self.player.setSource(QUrl())
                except Exception:
                    pass
        finally:
            try:
                self._player_source_path = ""
            except Exception:
                pass

    def add_tool_button(self, icon, tooltip, callback):
        """在右上角添加工具按钮"""
        btn = TransparentToolButton(icon, self)
        btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        if hasattr(self, "tool_bar_layout") and self.tool_bar_layout is not None:
            self.tool_bar_layout.addWidget(btn)
        try:
            self._tool_buttons.append(btn)
        except Exception:
            pass
        return btn

    def set_loading(self, loading: bool, progress: float = 0.0):
        """切换生成中的遮罩态（用于输出样本预渲染）。"""
        self._loading = bool(loading)
        if self._loading_overlay is None:
            return

        if self._loading:
            self._loading_overlay.set_progress(progress)
            self._loading_overlay.show()
            self._loading_overlay.raise_()
            self._loading_overlay.start()

            # 禁用交互控件（遮罩会拦截，但这里再保险）
            try:
                self.play_btn.setEnabled(False)
            except Exception:
                pass
            if getattr(self, "clear_btn", None) is not None:
                try:
                    self.clear_btn.setEnabled(False)
                except Exception:
                    pass
            for b in getattr(self, "_tool_buttons", []):
                try:
                    b.setEnabled(False)
                except Exception:
                    pass
        else:
            self._loading_overlay.stop()
            self._loading_overlay.hide()
            try:
                self.play_btn.setEnabled(True)
            except Exception:
                pass
            if getattr(self, "clear_btn", None) is not None:
                try:
                    self.clear_btn.setEnabled(True)
                except Exception:
                    pass
            for b in getattr(self, "_tool_buttons", []):
                try:
                    b.setEnabled(True)
                except Exception:
                    pass

    def set_loading_progress(self, progress: float):
        """更新遮罩态进度（0-1）。"""
        if self._loading_overlay is None:
            return
        self._loading_overlay.set_progress(progress)

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            # 懒加载媒体源：仅在用户主动播放时才打开音频
            if not self._ensure_player_source():
                return
            self.player.play()

    def _on_position_changed(self, position):
        if self._duration > 0:
            progress = position / self._duration
            self.waveform.set_progress(progress)
            try:
                self.waveform.set_position_ms(position)
            except Exception:
                pass
            self.current_time_label.setText(self._format_time(position))

    def _on_duration_changed(self, duration):
        self._duration = duration
        self.total_time_label.setText(self._format_time(duration))
        try:
            self.waveform.set_duration_ms(duration)
        except Exception:
            pass

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


class _ThreeDotsSpinner(QWidget):
    """经典三圆点循环放缩加载动画。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(72, 22)

    def start(self):
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        if self._timer.isActive():
            self._timer.stop()

    def _tick(self):
        self._t += 0.06
        if self._t > 1e6:
            self._t = 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()
        cy = h // 2

        base_r = 5
        gap = 18
        x0 = (w - 2 * gap) // 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0))

        phases = [0.0, 0.33, 0.66]
        for i, ph in enumerate(phases):
            s = 0.70 + 0.55 * (0.5 + 0.5 * math.sin((self._t + ph) * 2 * math.pi))
            r = int(base_r * s)
            cx = x0 + i * gap
            painter.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)


class _LoadingOverlay(QWidget):
    """覆盖层：半透明遮罩 + 三点动画 + 进度条。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: rgba(255, 255, 255, 210); border-radius: 8px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.spinner = _ThreeDotsSpinner(self)
        layout.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignCenter)

        self.progress = ProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(6)
        self.progress.setFixedWidth(160)
        layout.addWidget(self.progress, 0, Qt.AlignmentFlag.AlignCenter)

        self._resize_to_parent()

    def _resize_to_parent(self):
        p = self.parentWidget()
        if p is None:
            return
        self.setGeometry(0, 0, p.width(), p.height())

    def showEvent(self, event):
        self._resize_to_parent()
        return super().showEvent(event)

    def resizeEvent(self, event):
        self._resize_to_parent()
        return super().resizeEvent(event)

    def start(self):
        self.spinner.start()

    def stop(self):
        self.spinner.stop()

    def set_progress(self, progress: float):
        v = int(max(0.0, min(1.0, float(progress))) * 100)
        self.progress.setValue(v)


class ReferenceAudioPlayerWidget(AudioPlayerWidget):
    """参考音频播放器：紧凑 + 可导入空态 + 可清空。"""

    def __init__(self, title="Voice Reference", parent=None):
        super().__init__(
            title,
            parent,
            compact_mode=True,
            compact_empty_hint="upload",
            show_clear_button=True,
            clear_tooltip="移除参考音频",
            title_follows_filename=True,
        )


class ResultAudioPlayerWidget(AudioPlayerWidget):
    """生成结果播放器：紧凑 + 不显示导入空态 + 无清空按钮。"""

    def __init__(self, title="音频", parent=None):
        super().__init__(
            title,
            parent,
            compact_mode=True,
            compact_empty_hint="none",
            show_clear_button=False,
            # 输出样本希望展示全局 wav 文件名
            title_follows_filename=True,
        )

