"""角色列表容器组件

需求实现：
1. 默认仅显示一行角色（组件高度固定）
2. 不提供展开按钮
3. 通过垂直滚动条上下滚动浏览全部角色
"""

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
    QFrame, QGridLayout, QGraphicsDropShadowEffect
)
from qfluentwidgets import (
    CardWidget,
    StrongBodyLabel, CaptionLabel
)

from Source.UI.Interface.AIVoiceInterface.character_button import CharacterButton, AddCharacterButton
from Source.UI.Interface.AIVoiceInterface.character_manager import CharacterManager


class CharacterListWidget(CardWidget):
    """角色列表容器（固定一行高度 + 垂直滚动浏览全部）"""
    
    # 信号
    character_selected = Signal(str)
    character_edit_requested = Signal(str)
    character_delete_requested = Signal(str)
    add_character_requested = Signal()
    
    # 布局常量
    COLUMNS = 5
    ITEM_WIDTH = 78
    ITEM_HEIGHT = 88
    GRID_SPACING = 6
    HEADER_ROW_HEIGHT = 28
    FIXED_SCROLL_HEIGHT = ITEM_HEIGHT  # 仅显示一行
    FIXED_HEIGHT = 24 + HEADER_ROW_HEIGHT + 8 + FIXED_SCROLL_HEIGHT + 12  # 上下边距+标题+间距+一行+底部缓冲
    
    def __init__(self, character_manager: CharacterManager, parent=None):
        super().__init__(parent)
        
        self._character_manager = character_manager
        self._character_buttons: Dict[str, CharacterButton] = {}
        
        self._apply_style()
        self._init_ui()
        self._refresh_list()
    
    def _apply_style(self):
        """应用现代化样式"""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)
        
        self.setStyleSheet("""
            CharacterListWidget {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #e8e8e8;
            }
        """)
    
    def _init_ui(self):
        """初始化 UI"""
        # 固定高度：仅显示一行角色
        self.setFixedHeight(self.FIXED_HEIGHT)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(8)
        
        # === 标题栏 ===
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        
        title_label = StrongBodyLabel("角色列表", header)
        header_layout.addWidget(title_label)
        
        self._count_label = CaptionLabel("", header)
        self._count_label.setStyleSheet("color: #888;")
        header_layout.addWidget(self._count_label)
        
        header_layout.addStretch()
        
        main_layout.addWidget(header)
        
        # === 滚动区域 ===
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # 固定一行高度下，通过滚动条浏览全部
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #f5f5f5;
                width: 8px;
                margin: 0;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        
        # 内容容器
        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("background: transparent;")
        self._grid_layout = QGridLayout(self._content_widget)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(self.GRID_SPACING)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self._scroll_area.setWidget(self._content_widget)
        self._scroll_area.setFixedHeight(self.FIXED_SCROLL_HEIGHT)
        main_layout.addWidget(self._scroll_area)
    
    def _refresh_list(self):
        """刷新角色列表"""
        # 清除旧按钮
        for btn in self._character_buttons.values():
            btn.deleteLater()
        self._character_buttons.clear()
        
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        characters = self._character_manager.characters
        selected_id = self._character_manager.selected_id
        
        # 更新数量
        self._count_label.setText(f"{len(characters)}/{self._character_manager.MAX_CHARACTERS}")
        
        # 添加"添加角色"按钮
        add_btn = AddCharacterButton(self._content_widget)
        add_btn.clicked_add.connect(lambda: self.add_character_requested.emit())
        self._grid_layout.addWidget(add_btn, 0, 0)
        
        # 添加角色按钮
        for i, char in enumerate(characters):
            row = (i + 1) // self.COLUMNS
            col = (i + 1) % self.COLUMNS
            
            btn = CharacterButton(char.id, char.name, char.avatar_path, self._content_widget)
            btn.set_selected(char.id == selected_id)
            btn.character_selected.connect(self._on_character_selected)
            btn.character_edit_requested.connect(lambda cid: self.character_edit_requested.emit(cid))
            btn.character_delete_requested.connect(lambda cid: self.character_delete_requested.emit(cid))
            
            self._grid_layout.addWidget(btn, row, col)
            self._character_buttons[char.id] = btn
    
    def _on_character_selected(self, character_id: str):
        """角色被选中"""
        for cid, btn in self._character_buttons.items():
            btn.set_selected(cid == character_id)
        self.character_selected.emit(character_id)
    
    def refresh(self):
        """刷新列表"""
        self._refresh_list()
    
    def update_selection(self, selected_id: Optional[str]):
        """更新选中状态"""
        for cid, btn in self._character_buttons.items():
            btn.set_selected(cid == selected_id)
    
    def set_expanded(self, expanded: bool):
        """兼容旧接口：展开功能已移除"""
        return
