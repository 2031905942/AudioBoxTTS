"""Wwise WorkUnit 导入对话框

目标体验：
- 只从“叶子 WorkUnit”导入角色（避免 Sound/SFX 爆量导入）
- 只导入 Voices 作为参考音色（不使用 SFX）
- 支持按父 WorkUnit（例如 Boss）过滤 + 关键词过滤
- 支持全选/取消全选，且默认不全选
"""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    FluentIcon,
    LineEdit,
    ListWidget,
    MessageBoxBase,
    PushButton,
    SubtitleLabel,
)

from Source.Utility.wwise_character_discovery import WorkUnitCandidate


def _get_top_parent_name(candidate: WorkUnitCandidate) -> str:
    path = str(candidate.full_path or "").strip()
    if not path:
        return ""
    parts = [p.strip() for p in path.split("/")]
    parts = [p for p in parts if p]
    return parts[0] if parts else ""


class _WorkUnitRow(QWidget):
    def __init__(self, candidate: WorkUnitCandidate, parent: QWidget | None = None):
        super().__init__(parent)
        self.candidate = candidate

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        self.check = CheckBox(self)
        self.check.setChecked(False)
        layout.addWidget(self.check, 0, Qt.AlignmentFlag.AlignVCenter)

        label = str(candidate.full_path or candidate.name or "").strip()
        self.name_label = BodyLabel(label, self)
        self.name_label.setWordWrap(False)
        try:
            self.name_label.setToolTip(label)
        except Exception:
            pass
        layout.addWidget(self.name_label, 1)

        has_voice = bool(getattr(candidate, "reference_voice_path", None))
        self.voice_label = CaptionLabel("有" if has_voice else "无", self)
        self.voice_label.setMinimumWidth(64)
        self.voice_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.voice_label, 0)

        self.count_label = CaptionLabel(str(int(getattr(candidate, "voice_count", 0) or 0)), self)
        self.count_label.setMinimumWidth(56)
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count_label, 0)

        if has_voice:
            try:
                self.voice_label.setToolTip(str(candidate.reference_voice_path))
            except Exception:
                pass


class WwiseWorkUnitImportDialog(MessageBoxBase):
    def __init__(
        self,
        parent=None,
        candidates: List[WorkUnitCandidate] | None = None,
        *,
        default_parent: str | None = None,
    ):
        super().__init__(parent)
        self._all_candidates: List[WorkUnitCandidate] = list(candidates or [])
        self._rows: list[Tuple[WorkUnitCandidate, QListWidgetItem, _WorkUnitRow]] = []
        self._default_parent = str(default_parent or "").strip()

        self._init_ui()
        self._populate()

    def _init_ui(self):
        title_label = SubtitleLabel("从 Wwise 导入角色（按 WorkUnit）", self)
        self.viewLayout.addWidget(title_label)

        hint = BodyLabel("仅列出最低层 WorkUnit；只使用 Voices 作为参考音色。", self)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6b7280; font-size: 12px;")
        self.viewLayout.addWidget(hint)

        # 筛选行：父 WorkUnit + 关键词
        filter_row = QWidget(self)
        filter_layout = QHBoxLayout(filter_row)
        filter_layout.setContentsMargins(0, 8, 0, 0)
        filter_layout.setSpacing(8)

        self._parent_combo = ComboBox(filter_row)
        self._parent_combo.setPlaceholderText("父 WorkUnit")
        self._parent_combo.currentIndexChanged.connect(lambda _=0: self._apply_filters())
        filter_layout.addWidget(self._parent_combo, 0)

        self._filter_edit = LineEdit(filter_row)
        self._filter_edit.setPlaceholderText("过滤（支持角色名/路径关键字）")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.textChanged.connect(lambda _t="": self._apply_filters())
        filter_layout.addWidget(self._filter_edit, 1)

        self.viewLayout.addWidget(filter_row)

        # 操作行：全选 / 取消全选 / 选中统计
        action_row = QWidget(self)
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self._select_toggle_btn = PushButton(FluentIcon.ACCEPT, "全选", action_row)
        self._select_toggle_btn.clicked.connect(self._toggle_select_visible)
        action_layout.addWidget(self._select_toggle_btn)

        action_layout.addStretch(1)

        self._selected_count_label = CaptionLabel("已选 0", action_row)
        action_layout.addWidget(self._selected_count_label)

        self.viewLayout.addWidget(action_row)

        # 表头（更接近 table 的观感，但仍用 ListWidget 保持 Fluent 风格）
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)
        header_layout.setSpacing(10)

        header_layout.addSpacing(26)  # 对齐复选框
        header_layout.addWidget(CaptionLabel("WorkUnit", header), 1)
        v = CaptionLabel("参考Voice", header)
        v.setMinimumWidth(64)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(v, 0)
        c = CaptionLabel("Voice数", header)
        c.setMinimumWidth(56)
        c.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(c, 0)
        self.viewLayout.addWidget(header)

        self._list = ListWidget(self)
        self._list.setAlternatingRowColors(True)
        self.viewLayout.addWidget(self._list, 1)

        self.widget.setMinimumWidth(760)
        self.widget.setMinimumHeight(520)
        self.yesButton.setText("导入选中")
        self.cancelButton.setText("取消")

    def _populate(self):
        self._list.clear()
        self._rows.clear()

        # 父 WorkUnit 列表
        parents = sorted({p for p in (_get_top_parent_name(c) for c in self._all_candidates) if p})
        self._parent_combo.clear()
        self._parent_combo.addItem("全部")
        if parents:
            self._parent_combo.addItems(parents)

        # 默认父 WorkUnit：如果只存在一个父，则自动选中它；否则使用 default_parent；否则“全部”
        target_parent = ""
        if len(parents) == 1:
            target_parent = parents[0]
        elif self._default_parent and (self._default_parent in parents):
            target_parent = self._default_parent

        if target_parent:
            try:
                idx = self._parent_combo.findText(target_parent)
                self._parent_combo.setCurrentIndex(idx)
            except Exception:
                self._parent_combo.setCurrentIndex(0)
        else:
            self._parent_combo.setCurrentIndex(0)

        # 行
        for c in self._all_candidates:
            item = QListWidgetItem(self._list)
            row = _WorkUnitRow(c, self._list)
            try:
                row.check.stateChanged.connect(lambda _=0: self._update_selected_count())
            except Exception:
                pass

            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
            self._rows.append((c, item, row))

        self._apply_filters()
        self._update_selected_count()
        self._update_select_toggle_button()

    def _apply_filters(self):
        try:
            parent_text = str(self._parent_combo.currentText() or "").strip()
        except Exception:
            parent_text = ""
        try:
            keyword = str(self._filter_edit.text() or "").strip().lower()
        except Exception:
            keyword = ""

        for c, item, _row in self._rows:
            visible = True

            if parent_text and parent_text != "全部":
                top = _get_top_parent_name(c)
                if top != parent_text:
                    visible = False

            if visible and keyword:
                label = str(c.full_path or c.name or "").lower()
                visible = keyword in label

            try:
                item.setHidden(not visible)
            except Exception:
                pass

        self._update_select_toggle_button()

    def _toggle_select_visible(self):
        # 如果“可见项”全部已勾选 -> 取消全选；否则 -> 全选
        visible_rows: list[_WorkUnitRow] = []
        for _c, item, row in self._rows:
            try:
                if item.isHidden():
                    continue
            except Exception:
                pass
            visible_rows.append(row)

        if not visible_rows:
            return

        all_checked = True
        for row in visible_rows:
            try:
                if not row.check.isChecked():
                    all_checked = False
                    break
            except Exception:
                all_checked = False
                break

        self._set_check_for_visible(not all_checked)
        self._update_select_toggle_button()

    def _set_check_for_visible(self, checked: bool):
        for _c, item, row in self._rows:
            try:
                if item.isHidden():
                    continue
            except Exception:
                pass
            try:
                row.check.setChecked(bool(checked))
            except Exception:
                pass
        self._update_selected_count()

    def _update_select_toggle_button(self):
        # 根据可见项状态更新“全选/取消全选”按钮
        visible = 0
        checked = 0
        for _c, item, row in self._rows:
            try:
                if item.isHidden():
                    continue
            except Exception:
                pass
            visible += 1
            try:
                if row.check.isChecked():
                    checked += 1
            except Exception:
                pass

        try:
            self._select_toggle_btn.setEnabled(visible > 0)
        except Exception:
            pass

        if visible > 0 and checked == visible:
            try:
                self._select_toggle_btn.setText("取消全选")
                self._select_toggle_btn.setIcon(FluentIcon.CANCEL.icon())
            except Exception:
                pass
        else:
            try:
                self._select_toggle_btn.setText("全选")
                self._select_toggle_btn.setIcon(FluentIcon.ACCEPT.icon())
            except Exception:
                pass

    def _update_selected_count(self):
        count = 0
        total = len(self._rows)
        for _c, _item, row in self._rows:
            try:
                if row.check.isChecked():
                    count += 1
            except Exception:
                pass
        try:
            self._selected_count_label.setText(f"已选 {count} / {total}")
        except Exception:
            pass

        self._update_select_toggle_button()

    def get_selected_candidates(self) -> List[WorkUnitCandidate]:
        selected: List[WorkUnitCandidate] = []
        for c, _item, row in self._rows:
            try:
                if row.check.isChecked():
                    selected.append(c)
            except Exception:
                continue
        return selected
