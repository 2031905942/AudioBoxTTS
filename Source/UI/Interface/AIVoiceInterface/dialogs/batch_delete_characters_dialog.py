"""批量删除角色对话框（Fluent 风格）。

- 支持搜索过滤
- 支持全选/取消全选（单按钮切换）
- 默认不全选
"""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    FluentIcon,
    LineEdit,
    ListWidget,
    MessageBoxBase,
    PushButton,
    SubtitleLabel,
)

from Source.UI.Interface.AIVoiceInterface.models.character_manager import Character


class _CharacterRow(QWidget):
    def __init__(self, character: Character, parent: QWidget | None = None):
        super().__init__(parent)
        self.character = character

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        self.check = CheckBox(self)
        self.check.setChecked(False)
        layout.addWidget(self.check, 0, Qt.AlignmentFlag.AlignVCenter)

        name = str(getattr(character, "name", "") or "").strip()
        self.name_label = BodyLabel(name or "(未命名)", self)
        self.name_label.setWordWrap(False)
        try:
            self.name_label.setToolTip(name)
        except Exception:
            pass
        layout.addWidget(self.name_label, 1)

        has_ref = bool(str(getattr(character, "reference_audio_path", "") or "").strip())
        ref_label = CaptionLabel("有" if has_ref else "无", self)
        ref_label.setMinimumWidth(64)
        ref_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ref_label, 0)


class BatchDeleteCharactersDialog(MessageBoxBase):
    def __init__(self, parent=None, characters: List[Character] | None = None):
        super().__init__(parent)
        self._all_characters: List[Character] = list(characters or [])
        self._rows: list[Tuple[Character, QListWidgetItem, _CharacterRow]] = []

        self._init_ui()
        self._populate()

    def _init_ui(self):
        title_label = SubtitleLabel("批量删除角色", self)
        self.viewLayout.addWidget(title_label)

        hint = BodyLabel("支持搜索过滤与全选。删除后不可恢复（不会删除原始参考音频文件，仅清理历史缓存/输出）。", self)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6b7280; font-size: 12px;")
        self.viewLayout.addWidget(hint)

        filter_row = QWidget(self)
        filter_layout = QHBoxLayout(filter_row)
        filter_layout.setContentsMargins(0, 8, 0, 0)
        filter_layout.setSpacing(8)

        self._filter_edit = LineEdit(filter_row)
        self._filter_edit.setPlaceholderText("搜索角色（支持关键字）")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.textChanged.connect(lambda _t="": self._apply_filter())
        filter_layout.addWidget(self._filter_edit, 1)

        self._toggle_btn = PushButton(FluentIcon.ACCEPT, "全选", filter_row)
        self._toggle_btn.clicked.connect(self._toggle_select_visible)
        filter_layout.addWidget(self._toggle_btn, 0)

        self._selected_count = CaptionLabel("已选 0", filter_row)
        filter_layout.addWidget(self._selected_count, 0)

        self.viewLayout.addWidget(filter_row)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)
        header_layout.setSpacing(10)

        header_layout.addSpacing(26)
        header_layout.addWidget(CaptionLabel("角色", header), 1)
        v = CaptionLabel("参考音频", header)
        v.setMinimumWidth(64)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(v, 0)
        self.viewLayout.addWidget(header)

        self._list = ListWidget(self)
        self._list.setAlternatingRowColors(True)
        self.viewLayout.addWidget(self._list, 1)

        self.widget.setMinimumWidth(660)
        self.widget.setMinimumHeight(520)
        self.yesButton.setText("删除选中")
        self.cancelButton.setText("取消")

    def _populate(self):
        self._list.clear()
        self._rows.clear()

        for ch in self._all_characters:
            item = QListWidgetItem(self._list)
            row = _CharacterRow(ch, self._list)
            try:
                row.check.stateChanged.connect(lambda _=0: self._update_ui_state())
            except Exception:
                pass
            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
            self._rows.append((ch, item, row))

        self._apply_filter()
        self._update_ui_state()

    def _apply_filter(self):
        keyword = ""
        try:
            keyword = str(self._filter_edit.text() or "").strip().lower()
        except Exception:
            keyword = ""

        for ch, item, _row in self._rows:
            visible = True
            if keyword:
                name = str(getattr(ch, "name", "") or "").lower()
                visible = keyword in name
            try:
                item.setHidden(not visible)
            except Exception:
                pass

        self._update_ui_state()

    def _visible_rows(self) -> list[_CharacterRow]:
        rows: list[_CharacterRow] = []
        for _ch, item, row in self._rows:
            try:
                if item.isHidden():
                    continue
            except Exception:
                pass
            rows.append(row)
        return rows

    def _toggle_select_visible(self):
        visible = self._visible_rows()
        if not visible:
            return

        all_checked = True
        for r in visible:
            try:
                if not r.check.isChecked():
                    all_checked = False
                    break
            except Exception:
                all_checked = False
                break

        target = not all_checked
        for r in visible:
            try:
                r.check.setChecked(bool(target))
            except Exception:
                pass

        self._update_ui_state()

    def _update_ui_state(self):
        total = len(self._rows)
        selected = 0
        visible = 0
        visible_checked = 0

        for _ch, item, row in self._rows:
            is_visible = True
            try:
                is_visible = not item.isHidden()
            except Exception:
                is_visible = True

            if is_visible:
                visible += 1
                try:
                    if row.check.isChecked():
                        visible_checked += 1
                except Exception:
                    pass

            try:
                if row.check.isChecked():
                    selected += 1
            except Exception:
                pass

        try:
            self._selected_count.setText(f"已选 {selected} / {total}")
        except Exception:
            pass

        # toggle button
        try:
            self._toggle_btn.setEnabled(visible > 0)
        except Exception:
            pass
        if visible > 0 and visible_checked == visible:
            try:
                self._toggle_btn.setText("取消全选")
                self._toggle_btn.setIcon(FluentIcon.CANCEL.icon())
            except Exception:
                pass
        else:
            try:
                self._toggle_btn.setText("全选")
                self._toggle_btn.setIcon(FluentIcon.ACCEPT.icon())
            except Exception:
                pass

    def get_selected_ids(self) -> List[str]:
        ids: List[str] = []
        for ch, _item, row in self._rows:
            try:
                if row.check.isChecked():
                    ids.append(str(getattr(ch, "id", "")))
            except Exception:
                continue
        return [i for i in ids if i]
