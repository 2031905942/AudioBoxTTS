"""
创建/编辑角色对话框

提供角色创建和编辑的弹窗界面。
使用 qfluentwidgets 组件实现。
"""
import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QFileDialog
from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, BodyLabel, LineEdit,
    PushButton, FluentIcon, InfoBar, InfoBarPosition,
    ImageLabel
)


class CharacterDialog(MessageBoxBase):
    """创建/编辑角色对话框"""
    
    # 角色创建/更新完成信号
    character_saved = Signal(str, str)  # name, avatar_path
    
    AVATAR_SIZE = 80  # 对话框中的头像尺寸
    
    def __init__(self, parent=None, character_name: str = "", avatar_path: str = ""):
        """
        初始化对话框
        
        Args:
            parent: 父窗口
            character_name: 角色名称（编辑模式时传入）
            avatar_path: 头像路径（编辑模式时传入）
        """
        super().__init__(parent)
        
        self._avatar_path = avatar_path
        self._is_edit_mode = bool(character_name)
        
        self._init_ui(character_name, avatar_path)
    
    def _init_ui(self, character_name: str, avatar_path: str):
        """初始化 UI"""
        # 标题
        title = "编辑角色" if self._is_edit_mode else "创建角色"
        title_label = SubtitleLabel(title, self)
        self.viewLayout.addWidget(title_label)
        
        # 头像区域（使用 qfluentwidgets ImageLabel）
        avatar_layout = QHBoxLayout()
        avatar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 创建头像容器（用于圆形显示）
        from PySide6.QtWidgets import QLabel
        self.avatar_label = QLabel(self)
        self.avatar_label.setFixedSize(self.AVATAR_SIZE, self.AVATAR_SIZE)
        self.avatar_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #ccc;
                border-radius: 40px;
                background-color: #f5f5f5;
            }
        """)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if avatar_path and os.path.exists(avatar_path):
            self._set_avatar(avatar_path)
        else:
            self.avatar_label.setText("点击\n选择头像")
        
        self.avatar_label.mousePressEvent = lambda e: self._on_avatar_clicked()
        self.avatar_label.setCursor(Qt.CursorShape.PointingHandCursor)
        
        avatar_layout.addWidget(self.avatar_label)
        self.viewLayout.addLayout(avatar_layout)
        
        # 选择头像按钮（使用 qfluentwidgets PushButton）
        self.select_avatar_btn = PushButton(FluentIcon.PHOTO, "选择头像", self)
        self.select_avatar_btn.clicked.connect(self._on_avatar_clicked)
        self.viewLayout.addWidget(self.select_avatar_btn)
        
        # 昵称输入
        name_layout = QHBoxLayout()
        name_label = BodyLabel("昵称:", self)
        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText("请输入角色昵称（最多10个字符）")
        self.name_edit.setMaxLength(10)
        self.name_edit.setText(character_name)
        
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_edit, 1)
        self.viewLayout.addLayout(name_layout)
        
        # 按钮文本
        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")
        
        # 设置最小宽度
        self.widget.setMinimumWidth(350)
    
    def _on_avatar_clicked(self):
        """点击选择头像"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择头像图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)"
        )
        if file_path:
            self._avatar_path = file_path
            self._set_avatar(file_path)
    
    def _set_avatar(self, image_path: str):
        """设置头像"""
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return
        
        # 缩放并裁剪为圆形
        size = self.AVATAR_SIZE
        scaled = pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # 居中裁剪
        x = (scaled.width() - size) // 2
        y = (scaled.height() - size) // 2
        cropped = scaled.copy(x, y, size, size)
        
        # 创建圆形遮罩
        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        
        self.avatar_label.setPixmap(rounded)
        self.avatar_label.setStyleSheet("""
            QLabel {
                border: 2px solid #0078d4;
                border-radius: 40px;
            }
        """)
    
    def validate(self) -> bool:
        """验证输入"""
        name = self.name_edit.text().strip()
        if not name:
            InfoBar.error(
                title="请输入昵称",
                content="角色昵称不能为空",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return False
        return True
    
    def get_data(self) -> tuple[str, str]:
        """获取输入数据"""
        return self.name_edit.text().strip(), self._avatar_path
    
    @property
    def avatar_path(self) -> str:
        """获取头像路径"""
        return self._avatar_path
    
    @property
    def character_name(self) -> str:
        """获取角色名称"""
        return self.name_edit.text().strip()
