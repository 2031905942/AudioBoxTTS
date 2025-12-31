"""
圆形头像按钮组件

用于角色列表中的头像显示。
特性：
1. 圆形头像显示
2. 悬停时显示删除(右上角)和编辑(右下角)图标
3. 选中状态高亮
4. 现代化阴影和动画效果
"""
import os
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QEasingCurve, Property, QPoint
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QPen, QFont, QEnterEvent, QLinearGradient
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from qfluentwidgets import TransparentToolButton, FluentIcon, ToolTipFilter, ToolTipPosition


class IconButton(QWidget):
    """小型圆形图标按钮，带阴影效果"""
    
    clicked = Signal()
    
    def __init__(self, icon_type: str, size: int = 20, parent=None):
        """
        Args:
            icon_type: 'delete' 或 'edit'
            size: 按钮尺寸
        """
        super().__init__(parent)
        self._icon_type = icon_type
        self._size = size
        self._is_hovered = False
        
        # 增加尺寸以容纳阴影，避免被裁剪
        self.setFixedSize(size + 4, size + 4)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 关键：避免 Windows 上出现黑底/黑框伪影
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        # 强制设置样式表为透明，防止继承父级样式或默认样式导致的背景/边框
        self.setStyleSheet("background: transparent; border: none; margin: 0px; padding: 0px;")
        
        # 使用属性动画控制透明度
        self._opacity = 0.0
        self._opacity_anim = QPropertyAnimation(self, b"buttonOpacity")
        self._opacity_anim.setDuration(180)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def getButtonOpacity(self):
        return self._opacity
    
    def setButtonOpacity(self, value):
        self._opacity = value
        self.update()
    
    buttonOpacity = Property(float, getButtonOpacity, setButtonOpacity)
    
    def show_animated(self):
        """带动画显示"""
        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(self._opacity)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.start()
    
    def hide_animated(self):
        """带动画隐藏"""
        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(self._opacity)
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.start()
    
    def paintEvent(self, event):
        """绘制图标"""
        if self._opacity <= 0:
            return  # 完全透明时不绘制
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 先清空背景（透明），避免残影
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        painter.setOpacity(self._opacity)
        
        size = self._size
        
        # 根据类型设置渐变颜色
        if self._icon_type == 'delete':
            if self._is_hovered:
                gradient = QLinearGradient(0, 0, 0, size)
                gradient.setColorAt(0, QColor("#ff5252"))
                gradient.setColorAt(1, QColor("#d32f2f"))
            else:
                gradient = QLinearGradient(0, 0, 0, size)
                gradient.setColorAt(0, QColor("#ff7675"))
                gradient.setColorAt(1, QColor("#e74c3c"))
            icon_color = QColor("white")
        else:  # edit
            if self._is_hovered:
                gradient = QLinearGradient(0, 0, 0, size)
                gradient.setColorAt(0, QColor("#42a5f5"))
                gradient.setColorAt(1, QColor("#1976d2"))
            else:
                gradient = QLinearGradient(0, 0, 0, size)
                gradient.setColorAt(0, QColor("#64b5f6"))
                gradient.setColorAt(1, QColor("#2196f3"))
            icon_color = QColor("white")
        
        # 绘制柔和阴影（已移除，以保持界面清爽）
        # shadow_alpha = int(40 * self._opacity)
        # painter.setPen(Qt.PenStyle.NoPen)
        # painter.setBrush(QColor(0, 0, 0, shadow_alpha))
        # painter.drawEllipse(4, 5, size - 2, size - 2)

        # 绘制圆形背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        # 居中绘制 (Widget尺寸为 size+4)
        painter.drawEllipse(2, 2, size, size)
        
        # 绘制图标
        painter.setPen(QPen(icon_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        center = size // 2
        
        # 调整图标绘制偏移
        painter.translate(2, 2)
        
        if self._icon_type == 'delete':
            # 绘制 X
            margin = size // 4 + 1
            painter.drawLine(margin, margin, size - margin, size - margin)
            painter.drawLine(size - margin, margin, margin, size - margin)
        else:  # edit
            # 绘制铅笔图标（简化版）
            margin = size // 4
            # 铅笔主体
            painter.drawLine(margin + 1, size - margin - 1, size - margin - 1, margin + 1)
            # 铅笔尖端小点
            painter.drawPoint(margin, size - margin)
        
        painter.end()
    
    def enterEvent(self, event: QEnterEvent):
        """鼠标进入"""
        self._is_hovered = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开"""
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """鼠标点击"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CharacterButton(QWidget):
    """圆形头像按钮
    
    特性：
    1. 圆形头像（无头像时显示名称首字）
    2. 选中状态高亮边框
    3. 悬停时显示删除(右上角)和编辑(右下角)小图标
    4. 底部显示角色名称
    5. 悬停时头像放大效果
    """
    
    # 信号
    character_selected = Signal(str)  # character_id
    character_edit_requested = Signal(str)  # character_id
    character_delete_requested = Signal(str)  # character_id
    
    AVATAR_SIZE = 58  # 头像尺寸
    ICON_SIZE = 20  # 操作图标尺寸
    TOTAL_WIDTH = 74  # 总宽度（包含名称）
    TOTAL_HEIGHT = 86  # 总高度（头像 + 名称）
    
    def __init__(
        self,
        character_id: str,
        name: str,
        avatar_path: str = "",
        parent=None
    ):
        super().__init__(parent)
        
        self._character_id = character_id
        self._name = name
        self._avatar_path = avatar_path
        self._is_selected = False
        self._is_hovered = False
        self._scale = 1.0
        
        self._init_ui()
        self._setup_animations()
    
    def _init_ui(self):
        """初始化 UI"""
        self.setFixedSize(self.TOTAL_WIDTH, self.TOTAL_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(self._name)

        # 用 Fluent 风格 Tooltip，避免系统 tooltip 黑框
        self.installEventFilter(ToolTipFilter(self, 400, ToolTipPosition.TOP))
        
        # 头像区域
        avatar_x = (self.TOTAL_WIDTH - self.AVATAR_SIZE) // 2
        
        # 增大 Label 尺寸以容纳放大动画，避免裁剪
        # 原始尺寸 58，增加到 72 (+14)
        expanded_size = self.AVATAR_SIZE + 14
        offset = (expanded_size - self.AVATAR_SIZE) // 2
        
        self._avatar_label = QLabel(self)
        self._avatar_label.setFixedSize(expanded_size, expanded_size)
        # 向上向左偏移，保持视觉中心不变
        self._avatar_label.move(avatar_x - offset, -offset)
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar_label.setStyleSheet("background: transparent;")
        
        # 删除按钮（右上角）
        # IconButton 尺寸增加了 4px (2px padding per side)，所以需要偏移 -2, -2
        btn_offset = 2
        self._delete_btn = IconButton('delete', self.ICON_SIZE, self)
        self._delete_btn.move(
            avatar_x + self.AVATAR_SIZE - self.ICON_SIZE + 4 - btn_offset,
            -4 - btn_offset
        )
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        
        # 编辑按钮（右下角）
        self._edit_btn = IconButton('edit', self.ICON_SIZE, self)
        self._edit_btn.move(
            avatar_x + self.AVATAR_SIZE - self.ICON_SIZE + 4 - btn_offset,
            self.AVATAR_SIZE - self.ICON_SIZE + 4 - btn_offset
        )
        self._edit_btn.clicked.connect(self._on_edit_clicked)
        
        # 名称标签
        self._name_label = QLabel(self)
        self._name_label.setFixedSize(self.TOTAL_WIDTH, 22)
        self._name_label.move(0, self.AVATAR_SIZE + 4)
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setStyleSheet("""
            QLabel {
                color: #444;
                font-size: 11px;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            }
        """)
        self._update_name_display()
        
        # 更新头像显示
        self._update_avatar()
    
    def _setup_animations(self):
        """设置动画"""
        self._scale_anim = QPropertyAnimation(self, b"avatarScale")
        self._scale_anim.setDuration(150)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def getAvatarScale(self):
        return self._scale
    
    def setAvatarScale(self, value):
        self._scale = value
        self._update_avatar()
    
    avatarScale = Property(float, getAvatarScale, setAvatarScale)
    
    def _update_name_display(self):
        """更新名称显示（超长截断）"""
        name = self._name
        if len(name) > 5:
            name = name[:4] + "…"
        self._name_label.setText(name)
    
    def _update_avatar(self):
        """更新头像"""
        size = self.AVATAR_SIZE
        
        # 创建画布（足够大以容纳放大后的头像和阴影）
        canvas_size = size + 14
        pixmap = QPixmap(canvas_size, canvas_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 计算缩放后的大小和偏移
        scaled_size = int(size * self._scale)
        offset = (canvas_size - scaled_size) // 2
        
        # 绘制阴影
        shadow_offset = 2
        shadow_color = QColor(0, 0, 0, 40)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow_color)
        painter.drawEllipse(
            offset + shadow_offset, 
            offset + shadow_offset, 
            scaled_size - 4, 
            scaled_size - 4
        )
        
        # 绘制边框和背景
        if self._is_selected:
            # 选中状态 - 渐变蓝色边框
            gradient = QLinearGradient(0, 0, 0, scaled_size)
            gradient.setColorAt(0, QColor("#42a5f5"))
            gradient.setColorAt(1, QColor("#1976d2"))
            painter.setPen(QPen(QColor("#1976d2"), 3))
            painter.setBrush(QColor("#e3f2fd"))
        elif self._is_hovered:
            # 悬停状态
            painter.setPen(QPen(QColor("#90caf9"), 2))
            painter.setBrush(QColor("#f5f9fc"))
        else:
            # 默认状态
            painter.setPen(QPen(QColor("#e0e0e0"), 2))
            painter.setBrush(QColor("#fafafa"))
        
        painter.drawEllipse(offset + 2, offset + 2, scaled_size - 4, scaled_size - 4)
        
        # 绘制头像或默认文字
        if self._avatar_path and os.path.exists(self._avatar_path):
            self._draw_avatar(painter, scaled_size, offset)
        else:
            self._draw_default_avatar(painter, scaled_size, offset)
        
        painter.end()
        
        self._avatar_label.setPixmap(pixmap)
    
    def _draw_avatar(self, painter: QPainter, size: int, offset: int):
        """绘制头像图片"""
        avatar_pixmap = QPixmap(self._avatar_path)
        if avatar_pixmap.isNull():
            self._draw_default_avatar(painter, size, offset)
            return
        
        # 缩放
        inner_size = size - 10  # 留出边框空间
        scaled = avatar_pixmap.scaled(
            inner_size, inner_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # 居中裁剪
        x = (scaled.width() - inner_size) // 2
        y = (scaled.height() - inner_size) // 2
        cropped = scaled.copy(x, y, inner_size, inner_size)
        
        # 创建圆形遮罩
        inner_offset = offset + 5
        path = QPainterPath()
        path.addEllipse(inner_offset, inner_offset, inner_size, inner_size)
        painter.setClipPath(path)
        painter.drawPixmap(inner_offset, inner_offset, cropped)
        painter.setClipping(False)
    
    def _draw_default_avatar(self, painter: QPainter, size: int, offset: int):
        """绘制默认头像（显示首字）"""
        first_char = self._name[0] if self._name else "?"
        
        font = QFont("Microsoft YaHei", 20)
        font.setBold(True)
        painter.setFont(font)
        
        # 使用渐变色文字
        if self._is_selected:
            painter.setPen(QColor("#1976d2"))
        else:
            painter.setPen(QColor("#666"))
        
        painter.drawText(
            offset, offset, size, size,
            Qt.AlignmentFlag.AlignCenter,
            first_char
        )
    
    def enterEvent(self, event: QEnterEvent):
        """鼠标进入 - 显示操作图标并放大头像"""
        self._is_hovered = True
        self._delete_btn.show_animated()
        self._edit_btn.show_animated()
        
        # 启动放大动画
        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._scale)
        self._scale_anim.setEndValue(1.08)
        self._scale_anim.start()
        
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开 - 隐藏操作图标并恢复头像大小"""
        self._is_hovered = False
        self._delete_btn.hide_animated()
        self._edit_btn.hide_animated()
        
        # 启动缩小动画
        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._scale)
        self._scale_anim.setEndValue(1.0)
        self._scale_anim.start()
        
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """鼠标点击 - 选中角色"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否点击在头像区域
            avatar_rect = self._avatar_label.geometry()
            if avatar_rect.contains(event.pos()):
                self.character_selected.emit(self._character_id)
        super().mousePressEvent(event)
    
    def _on_delete_clicked(self):
        """删除按钮点击"""
        self.character_delete_requested.emit(self._character_id)
    
    def _on_edit_clicked(self):
        """编辑按钮点击"""
        self.character_edit_requested.emit(self._character_id)
    
    @property
    def character_id(self) -> str:
        return self._character_id
    
    @property
    def is_selected(self) -> bool:
        return self._is_selected
    
    def set_selected(self, selected: bool):
        """设置选中状态"""
        if self._is_selected != selected:
            self._is_selected = selected
            self._update_avatar()
            # 选中状态下名称加粗
            if selected:
                self._name_label.setStyleSheet("""
                    QLabel {
                        color: #1976d2;
                        font-size: 11px;
                        font-weight: bold;
                        font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                    }
                """)
            else:
                self._name_label.setStyleSheet("""
                    QLabel {
                        color: #444;
                        font-size: 11px;
                        font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                    }
                """)
    
    def update_info(self, name: str, avatar_path: str):
        """更新角色信息"""
        self._name = name
        self._avatar_path = avatar_path
        self.setToolTip(name)
        self._update_name_display()
        self._update_avatar()


class AddCharacterButton(QWidget):
    """添加角色按钮（+号），现代化设计"""
    
    clicked_add = Signal()
    
    AVATAR_SIZE = 58
    TOTAL_WIDTH = 74
    TOTAL_HEIGHT = 86
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_hovered = False
        self._scale = 1.0
        self._init_ui()
        self._setup_animations()
    
    def _init_ui(self):
        """初始化 UI"""
        self.setFixedSize(self.TOTAL_WIDTH, self.TOTAL_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("创建新角色")
        
        # 图标区域
        avatar_x = (self.TOTAL_WIDTH - self.AVATAR_SIZE) // 2
        
        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(self.AVATAR_SIZE + 8, self.AVATAR_SIZE + 8)
        self._icon_label.move(avatar_x - 4, -4)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 名称标签
        self._name_label = QLabel("添加", self)
        self._name_label.setFixedSize(self.TOTAL_WIDTH, 22)
        self._name_label.move(0, self.AVATAR_SIZE + 4)
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setStyleSheet("""
            QLabel {
                color: #1976d2;
                font-size: 11px;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            }
        """)
        
        self._update_icon()
    
    def _setup_animations(self):
        """设置动画"""
        self._scale_anim = QPropertyAnimation(self, b"iconScale")
        self._scale_anim.setDuration(150)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def getIconScale(self):
        return self._scale
    
    def setIconScale(self, value):
        self._scale = value
        self._update_icon()
    
    iconScale = Property(float, getIconScale, setIconScale)
    
    def _update_icon(self):
        """更新图标"""
        size = self.AVATAR_SIZE
        canvas_size = size + 8
        
        pixmap = QPixmap(canvas_size, canvas_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 计算缩放后的大小和偏移
        scaled_size = int(size * self._scale)
        offset = (canvas_size - scaled_size) // 2
        
        # 绘制虚线圆形边框
        if self._is_hovered:
            # 渐变填充
            gradient = QLinearGradient(0, 0, 0, scaled_size)
            gradient.setColorAt(0, QColor("#e3f2fd"))
            gradient.setColorAt(1, QColor("#bbdefb"))
            painter.setBrush(gradient)
            painter.setPen(QPen(QColor("#1976d2"), 2, Qt.PenStyle.SolidLine))
        else:
            painter.setBrush(QColor("#f5f9fc"))
            painter.setPen(QPen(QColor("#64b5f6"), 2, Qt.PenStyle.DashLine))
        
        painter.drawEllipse(offset + 2, offset + 2, scaled_size - 4, scaled_size - 4)
        
        # 绘制 + 号
        font = QFont("Microsoft YaHei", 24)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#1976d2") if self._is_hovered else QColor("#42a5f5"))
        painter.drawText(
            offset, offset, scaled_size, scaled_size,
            Qt.AlignmentFlag.AlignCenter,
            "+"
        )
        
        painter.end()
        
        self._icon_label.setPixmap(pixmap)
    
    def enterEvent(self, event: QEnterEvent):
        """鼠标进入"""
        self._is_hovered = True
        
        # 启动放大动画
        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._scale)
        self._scale_anim.setEndValue(1.08)
        self._scale_anim.start()
        
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开"""
        self._is_hovered = False
        
        # 启动缩小动画
        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._scale)
        self._scale_anim.setEndValue(1.0)
        self._scale_anim.start()
        
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """鼠标点击"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_add.emit()
        super().mousePressEvent(event)
