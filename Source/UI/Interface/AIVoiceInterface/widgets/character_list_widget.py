"""角色列表容器组件

需求实现：
1. 默认仅显示一行角色（组件高度固定）
2. 不提供展开按钮
3. 通过垂直滚动条上下滚动浏览全部角色
"""

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon,
    LineEdit,
    ScrollArea,
    TransparentToolButton,
)

from Source.UI.Interface.AIVoiceInterface.models.character_manager import CharacterManager
from Source.UI.Interface.AIVoiceInterface.widgets.character_button import CharacterButton, AddCharacterButton


class CharacterListWidget(CardWidget):
    """角色列表容器（固定一行高度 + 垂直滚动浏览全部）"""

    # 信号
    character_selected = Signal(str)
    character_edit_requested = Signal(str)
    character_delete_requested = Signal(str)
    add_character_requested = Signal()
    import_from_wwise_requested = Signal()  # 从Wwise导入角色的信号
    batch_delete_requested = Signal()  # 批量删除角色

    # 布局常量
    COLUMNS = 6
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
        """使用 qfluentwidgets 的默认 CardWidget 风格。"""
        # 避免硬编码颜色/阴影，交给 Fluent 主题控制。
        try:
            self.setGraphicsEffect(None)
        except Exception:
            pass
        self.setStyleSheet("")

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

        title_label = BodyLabel("角色列表", header)
        header_layout.addWidget(title_label)

        self._count_label = CaptionLabel("", header)
        header_layout.addWidget(self._count_label)

        self._current_character_label = CaptionLabel("", header)
        try:
            self._current_character_label.setToolTip("")
        except Exception:
            pass
        try:
            # 角色名过长时避免把标题栏撑爆
            self._current_character_label.setMaximumWidth(260)
        except Exception:
            pass
        header_layout.addWidget(self._current_character_label)

        header_layout.addStretch()

        # 搜索栏：过滤角色列表
        self._search_edit = LineEdit(header)
        self._search_edit.setPlaceholderText("搜索角色")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setFixedWidth(220)
        self._search_edit.textChanged.connect(lambda _t="": self._refresh_list())
        header_layout.addWidget(self._search_edit)

        # 批量删除按钮（垃圾桶）
        self._batch_delete_btn = TransparentToolButton(FluentIcon.DELETE, header)
        self._batch_delete_btn.setToolTip("批量删除角色")
        self._batch_delete_btn.clicked.connect(lambda: self.batch_delete_requested.emit())
        header_layout.addWidget(self._batch_delete_btn)

        # 从Wwise导入按钮
        self._import_from_wwise_btn = TransparentToolButton(FluentIcon.DOWNLOAD, header)
        self._import_from_wwise_btn.setToolTip("从Wwise项目导入角色")
        self._import_from_wwise_btn.clicked.connect(lambda: self.import_from_wwise_requested.emit())
        header_layout.addWidget(self._import_from_wwise_btn)

        main_layout.addWidget(header)

        # === 滚动区域 ===
        self._scroll_area = ScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # 固定一行高度下，通过滚动条浏览全部
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        # 避免滚动区域自身绘制出“长方形底色/阴影感”，让 CardWidget 的底色保持一致
        try:
            self._scroll_area.setStyleSheet("background: transparent; border: none;")
        except Exception:
            pass
        try:
            self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        except Exception:
            pass

        # 内容容器
        self._content_widget = QWidget()
        try:
            self._content_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        except Exception:
            pass
        self._grid_layout = QGridLayout(self._content_widget)
        # 给头像上方留出间隙，避免贴着上边缘显得拥挤
        self._grid_layout.setContentsMargins(2, 6, 2, 2)
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

        all_characters = self._character_manager.characters
        characters = all_characters
        # 搜索过滤
        try:
            kw = str(self._search_edit.text() or "").strip().lower() if hasattr(self, "_search_edit") else ""
        except Exception:
            kw = ""
        if kw:
            characters = [c for c in characters if kw in str(getattr(c, "name", "") or "").lower()]
        selected_id = self._character_manager.selected_id

        # 更新数量（搜索时显示过滤结果）
        try:
            total = len(all_characters)
        except Exception:
            total = len(characters)
        if kw:
            self._count_label.setText(f"{len(characters)}/{total}/{self._character_manager.MAX_CHARACTERS}")
        else:
            self._count_label.setText(f"{total}/{self._character_manager.MAX_CHARACTERS}")

        # 更新当前角色显示
        try:
            selected = self._character_manager.selected_character
            name = selected.name if selected is not None else "未选择"
            self._set_current_character_text(name)
        except Exception:
            self._set_current_character_text("未选择")

        # 添加"添加角色"按钮
        add_btn = AddCharacterButton(self._content_widget)
        add_btn.clicked_add.connect(lambda: self.add_character_requested.emit())
        self._grid_layout.addWidget(add_btn, 0, 0)

        # 添加角色按钮
        for i, char in enumerate(characters):
            row = (i + 1) // self.COLUMNS
            col = (i + 1) % self.COLUMNS

            btn = CharacterButton(
                char.id,
                char.name,
                char.avatar_path,
                self._content_widget,
                has_reference_audio=bool(getattr(char, "reference_audio_path", "")),
            )
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

    def set_character_manager(self, character_manager: CharacterManager):
        """切换数据源（用于按项目切换角色列表）。"""
        self._character_manager = character_manager
        self._refresh_list()

    def update_selection(self, selected_id: Optional[str]):
        """更新选中状态"""
        for cid, btn in self._character_buttons.items():
            btn.set_selected(cid == selected_id)

        try:
            selected = self._character_manager.selected_character
            name = selected.name if selected is not None else "未选择"
            self._set_current_character_text(name)
        except Exception:
            self._set_current_character_text("未选择")

    def update_reference_state(self, character_id: str, has_reference_audio: bool):
        """仅更新指定角色的“参考音频是否存在”状态（避免整表重建）。"""
        btn = self._character_buttons.get(character_id)
        if not btn:
            return
        try:
            btn.set_has_reference_audio(bool(has_reference_audio))
        except Exception:
            pass

    def _set_current_character_text(self, name: str):
        """设置标题栏右侧的当前角色文字（带省略与 tooltip）。"""
        base = f"当前角色：{name or ''}"
        try:
            fm = QFontMetrics(self._current_character_label.font())
            elided = fm.elidedText(base, Qt.TextElideMode.ElideRight, int(self._current_character_label.maximumWidth()))
        except Exception:
            elided = base
        try:
            self._current_character_label.setText(elided)
        except Exception:
            pass
        try:
            self._current_character_label.setToolTip(base)
        except Exception:
            pass

    def set_expanded(self, expanded: bool):
        """兼容旧接口：展开功能已移除"""
        return
