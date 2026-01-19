"""角色按钮组件（Fluent 风格）。

目标：
- 使用 qfluentwidgets 控件（按钮/标签/tooltip），风格统一。
- 避免硬编码颜色/阴影；选中态交给控件自身 checkable/hover 状态。
"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPixmap, QPalette, QFont, QColor, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout

from qfluentwidgets import CaptionLabel, FluentIcon


def _get_project_root() -> str:
    here = os.path.abspath(__file__)
    # .../Source/UI/Interface/AIVoiceInterface/character_button.py -> repo root
    return os.path.abspath(os.path.join(os.path.dirname(here), "..", "..", "..", "..", ".."))


def _resolve_avatar_path(path: str) -> str:
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(_get_project_root(), path))


def _make_round_pixmap(src: QPixmap, size: int) -> QPixmap:
    scaled = src.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    x = (scaled.width() - size) // 2
    y = (scaled.height() - size) // 2
    cropped = scaled.copy(x, y, size, size)

    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return out


def _make_placeholder_pixmap(text: str, size: int, palette: QPalette) -> QPixmap:
    """用当前主题 palette 绘制占位头像（不硬编码颜色）。"""
    bg = palette.color(QPalette.ColorRole.Base)
    border = palette.color(QPalette.ColorRole.Mid)
    fg = palette.color(QPalette.ColorRole.Text)

    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setPen(border)
    painter.setBrush(bg)
    painter.drawEllipse(1, 1, size - 2, size - 2)

    painter.setPen(fg)
    font = QFont()
    font.setBold(True)
    font.setPointSize(max(10, int(size * 0.34)))
    painter.setFont(font)
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, (text or "?")[:1].upper())
    painter.end()
    return pm


def _tint_icon_pixmap(icon: QIcon, size: int, color: QColor) -> QPixmap:
    pm = icon.pixmap(size, size)
    if pm.isNull():
        return pm
    out = QPixmap(pm.size())
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.drawPixmap(0, 0, pm)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(out.rect(), color)
    painter.end()
    return out


class _RoundClickable(QWidget):
    """圆形可点击控件：支持 hover/pressed/selected 的主题化绘制。"""

    clicked = Signal()

    def __init__(
        self,
        diameter: int,
        icon_size: int,
        parent=None,
        *,
        draw_background_when_idle: bool = False,
    ):
        super().__init__(parent)
        self._diameter = int(diameter)
        self._icon_size = int(icon_size)
        self._icon: Optional[QIcon] = None
        self._pixmap: Optional[QPixmap] = None
        self._hover = False
        self._pressed = False
        self._selected = False
        self._draw_bg_idle = bool(draw_background_when_idle)

        self.setFixedSize(self._diameter, self._diameter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def setIcon(self, icon: QIcon):
        self._icon = icon
        self._pixmap = None
        self.update()

    def setPixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self._icon = None
        self.update()

    def setSelected(self, selected: bool):
        self._selected = bool(selected)
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        was_pressed = self._pressed
        self._pressed = False
        self.update()
        if was_pressed and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 主题化颜色：避免硬编码
        pal = self.palette()
        bg = pal.color(QPalette.ColorRole.Base)
        border = pal.color(QPalette.ColorRole.Mid)
        hover_bg = pal.color(QPalette.ColorRole.Midlight)
        accent = pal.color(QPalette.ColorRole.Highlight)

        # 背景（hover/pressed 时更明显；操作按钮可常驻背景）
        show_bg = self._hover or self._pressed or self._draw_bg_idle
        if show_bg:
            c = QColor(hover_bg)
            c.setAlpha(110 if self._hover else 70)
            if self._pressed:
                c.setAlpha(140)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c)
            painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))

        # 边框（操作按钮常驻；头像仅在选中时强调）
        if self._draw_bg_idle:
            pen_c = QColor(border)
            pen_c.setAlpha(160)
            painter.setPen(QPen(pen_c, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))

        if self._selected:
            pen_c = QColor(accent)
            pen_c.setAlpha(230)
            painter.setPen(QPen(pen_c, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.rect().adjusted(2, 2, -2, -2))

        # 图标/图片
        if self._pixmap is not None and not self._pixmap.isNull():
            pm = self._pixmap
        elif self._icon is not None:
            pm = self._icon.pixmap(self._icon_size, self._icon_size)
        else:
            pm = None

        if pm is not None and not pm.isNull():
            x = (self.width() - pm.width()) // 2
            y = (self.height() - pm.height()) // 2
            painter.drawPixmap(x, y, pm)

        painter.end()


class CharacterButton(QWidget):
    """角色按钮：头像（可选中）+ 名称 + 悬停操作按钮。"""

    character_selected = Signal(str)
    character_edit_requested = Signal(str)
    character_delete_requested = Signal(str)

    AVATAR_SIZE = 58
    TOTAL_WIDTH = 74
    TOTAL_HEIGHT = 86

    def __init__(self, character_id: str, name: str, avatar_path: str = "", parent=None, *, has_reference_audio: bool = True):
        super().__init__(parent)
        self._character_id = character_id
        self._name = name
        self._avatar_path = avatar_path
        self._is_selected = False
        self._has_reference_audio = bool(has_reference_audio)

        self.setFixedSize(self.TOTAL_WIDTH, self.TOTAL_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # 移除 ToolTipFilter 以修复点击后 tooltip 持久存在的 bug
        # self.installEventFilter(ToolTipFilter(self, 400, ToolTipPosition.TOP))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        # 头像（自绘圆形 hover/选中态，避免出现方形阴影）
        self._avatar_btn = _RoundClickable(self.AVATAR_SIZE, self.AVATAR_SIZE, self, draw_background_when_idle=False)
        self._avatar_btn.clicked.connect(self._on_clicked)
        layout.addWidget(self._avatar_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        # 名称
        self._name_label = CaptionLabel(self._name, self)
        self._name_label.setFixedWidth(self.TOTAL_WIDTH)
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._name_label)

        # 悬停操作按钮（圆形按钮轮廓，更协调；默认隐藏）
        self._delete_btn = _RoundClickable(24, 14, self, draw_background_when_idle=True)
        self._delete_btn.setIcon(FluentIcon.DELETE.icon())
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        self._delete_btn.hide()

        self._edit_btn = _RoundClickable(24, 14, self, draw_background_when_idle=True)
        self._edit_btn.setIcon(FluentIcon.EDIT.icon())
        self._edit_btn.clicked.connect(self._on_edit_clicked)
        self._edit_btn.hide()

        # “暂无参考音频”提示：左下角红色麦克风图标（常驻显示）
        self._missing_ref_btn = _RoundClickable(24, 14, self, draw_background_when_idle=True)
        try:
            red = QColor("#d13438")  # Fluent red
        except Exception:
            red = QColor(209, 52, 56)
        self._missing_ref_btn.setPixmap(_tint_icon_pixmap(FluentIcon.MICROPHONE.icon(), 14, red))

        # 仅作提示，不响应点击
        try:
            self._missing_ref_btn.setCursor(Qt.CursorShape.ArrowCursor)
        except Exception:
            pass
        self._missing_ref_btn.setVisible(not self._has_reference_audio)

        self._layout_overlay_buttons()
        self._refresh_avatar_icon()

    def _layout_overlay_buttons(self):
        # 右上角/右下角，略微外扩，避免挡住头像内容
        x = self.width() - 24
        self._delete_btn.move(x, -4)
        self._edit_btn.move(x, self.AVATAR_SIZE - 18)

        # 左下角：对齐头像左侧
        avatar_left = (self.width() - self.AVATAR_SIZE) // 2
        self._missing_ref_btn.move(max(0, avatar_left - 4), self.AVATAR_SIZE - 18)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_overlay_buttons()

    def enterEvent(self, event):
        self._delete_btn.show()
        self._edit_btn.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._delete_btn.hide()
        self._edit_btn.hide()
        super().leaveEvent(event)

    def _on_clicked(self):
        self.character_selected.emit(self._character_id)

    def _on_delete_clicked(self):
        self.character_delete_requested.emit(self._character_id)

    def _on_edit_clicked(self):
        self.character_edit_requested.emit(self._character_id)

    def _refresh_avatar_icon(self):
        resolved = _resolve_avatar_path(self._avatar_path)
        if resolved and os.path.exists(resolved):
            pm = QPixmap(resolved)
            if not pm.isNull():
                pm = _make_round_pixmap(pm, self.AVATAR_SIZE)
                self._avatar_btn.setPixmap(pm)
                return

        # 占位头像：用 palette 生成，不硬编码颜色
        placeholder = _make_placeholder_pixmap(self._name, self.AVATAR_SIZE, self.palette())
        self._avatar_btn.setPixmap(placeholder)

    @property
    def character_id(self) -> str:
        return self._character_id

    @property
    def is_selected(self) -> bool:
        return self._is_selected

    def set_selected(self, selected: bool):
        self._is_selected = bool(selected)
        try:
            self._avatar_btn.setSelected(self._is_selected)
        except Exception:
            pass

    def update_info(self, name: str, avatar_path: str):
        self._name = name
        self._avatar_path = avatar_path
        self._name_label.setText(name)
        self._refresh_avatar_icon()

    def set_has_reference_audio(self, has_reference_audio: bool):
        self._has_reference_audio = bool(has_reference_audio)
        try:
            self._missing_ref_btn.setVisible(not self._has_reference_audio)
        except Exception:
            pass


class AddCharacterButton(QWidget):
    """添加角色按钮：Fluent 图标 + 文本。"""

    clicked_add = Signal()

    AVATAR_SIZE = 58
    TOTAL_WIDTH = 74
    TOTAL_HEIGHT = 86

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.TOTAL_WIDTH, self.TOTAL_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # 移除 ToolTipFilter 以修复点击后 tooltip 持久存在的 bug
        # self.installEventFilter(ToolTipFilter(self, 400, ToolTipPosition.TOP))
        # 不显示 tooltip（避免悬停弹出文本框）
        self.setToolTip("")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        # 圆形“添加”按钮：hover 不出现方形阴影
        self._btn = _RoundClickable(self.AVATAR_SIZE, 24, self, draw_background_when_idle=False)
        self._btn.setIcon(FluentIcon.ADD.icon())
        self._btn.clicked.connect(self.clicked_add.emit)
        layout.addWidget(self._btn, 0, Qt.AlignmentFlag.AlignHCenter)

        self._label = CaptionLabel("添加", self)
        self._label.setFixedWidth(self.TOTAL_WIDTH)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

    
