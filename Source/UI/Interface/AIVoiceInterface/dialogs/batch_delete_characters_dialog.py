"""批量删除角色对话框（Fluent 风格）。

- 支持搜索过滤
- 支持全选/取消全选（单按钮切换）
- 默认不全选
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QHeaderView, QTableView, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    LineEdit,
    MessageBoxBase,
    PushButton,
    SubtitleLabel,
)

try:
    from qfluentwidgets import TableView as FluentTableView
except Exception:
    FluentTableView = QTableView

from Source.UI.Interface.AIVoiceInterface.models.character_manager import Character


@dataclass
class _CharacterRowData:
    character: Character
    checked: bool = False


class _CharacterTableModel(QAbstractTableModel):
    selectionChanged = Signal()

    COL_CHECK = 0
    COL_NAME = 1
    COL_HAS_REF = 2

    def __init__(self, characters: Sequence[Character], parent: QWidget | None = None):
        super().__init__(parent)
        self._rows: list[_CharacterRowData] = [_CharacterRowData(c) for c in characters]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return 3

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section == self.COL_CHECK:
                return ""
            if section == self.COL_NAME:
                return "角色"
            if section == self.COL_HAS_REF:
                return "参考音频"
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == self.COL_CHECK:
            return base | Qt.ItemFlag.ItemIsUserCheckable
        return base

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._rows):
            return None

        ch = self._rows[row].character
        name = str(getattr(ch, "name", "") or "").strip() or "(未命名)"
        has_ref = bool(str(getattr(ch, "reference_audio_path", "") or "").strip())

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_NAME:
                return name
            if col == self.COL_HAS_REF:
                return "有" if has_ref else "无"
            return None

        if role == Qt.ItemDataRole.CheckStateRole:
            if col == self.COL_CHECK:
                return Qt.CheckState.Checked if self._rows[row].checked else Qt.CheckState.Unchecked
            return None

        if role == Qt.ItemDataRole.ToolTipRole:
            if col == self.COL_NAME:
                return name
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col == self.COL_HAS_REF:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignVCenter)

        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False
        if index.column() != self.COL_CHECK:
            return False
        row = index.row()
        if row < 0 or row >= len(self._rows):
            return False
        if role == Qt.ItemDataRole.CheckStateRole:
            checked = value == Qt.CheckState.Checked
            if self._rows[row].checked == checked:
                return False
            self._rows[row].checked = checked
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            self.selectionChanged.emit()
            return True
        return False

    def selected_count(self) -> int:
        return sum(1 for r in self._rows if r.checked)

    def total_count(self) -> int:
        return len(self._rows)

    def get_selected_ids(self) -> List[str]:
        ids: List[str] = []
        for r in self._rows:
            try:
                if r.checked:
                    ids.append(str(getattr(r.character, "id", "")))
            except Exception:
                continue
        return [i for i in ids if i]

    def set_checked_for_source_rows(self, source_rows: Sequence[int], checked: bool):
        changed: list[int] = []
        for r in source_rows:
            if 0 <= r < len(self._rows) and self._rows[r].checked != bool(checked):
                self._rows[r].checked = bool(checked)
                changed.append(r)
        if not changed:
            return
        min_row = min(changed)
        max_row = max(changed)
        left = self.index(min_row, self.COL_CHECK)
        right = self.index(max_row, self.COL_CHECK)
        self.dataChanged.emit(left, right, [Qt.ItemDataRole.CheckStateRole])
        self.selectionChanged.emit()


class _CharacterFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._keyword_filter: str = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_keyword_filter(self, keyword: str):
        keyword = str(keyword or "").strip().lower()
        if self._keyword_filter == keyword:
            return
        self._keyword_filter = keyword
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return True
        try:
            row_data = model._rows[source_row]  # type: ignore[attr-defined]
        except Exception:
            return True

        if not self._keyword_filter:
            return True
        name = str(getattr(row_data.character, "name", "") or "").lower()
        return self._keyword_filter in name


class BatchDeleteCharactersDialog(MessageBoxBase):
    def __init__(self, parent=None, characters: List[Character] | None = None):
        super().__init__(parent)
        self._all_characters: List[Character] = list(characters or [])

        self._source_model = _CharacterTableModel(self._all_characters, self)
        self._proxy_model = _CharacterFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)

        self._init_ui()
        self._apply_filter()
        self._update_ui_state()

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

        self._table = FluentTableView(self)
        self._table.setModel(self._proxy_model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        self._table.setSortingEnabled(False)
        try:
            self._table.setWordWrap(False)
        except Exception:
            pass
        self.viewLayout.addWidget(self._table, 1)

        self.widget.setMinimumWidth(660)
        self.widget.setMinimumHeight(520)
        self.yesButton.setText("删除选中")
        self.cancelButton.setText("取消")

        # 列宽：复选框列固定，其余列均分
        try:
            header.setSectionResizeMode(_CharacterTableModel.COL_CHECK, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(_CharacterTableModel.COL_CHECK, 44)
            header.setSectionResizeMode(_CharacterTableModel.COL_NAME, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(_CharacterTableModel.COL_HAS_REF, QHeaderView.ResizeMode.Stretch)
        except Exception:
            pass

        try:
            self._table.doubleClicked.connect(self._on_table_double_clicked)
        except Exception:
            pass

        self._source_model.selectionChanged.connect(self._update_ui_state)

    def _apply_filter(self):
        try:
            keyword = str(self._filter_edit.text() or "").strip()
        except Exception:
            keyword = ""
        self._proxy_model.set_keyword_filter(keyword)
        self._update_ui_state()

    def _on_table_double_clicked(self, proxy_index: QModelIndex):
        if not proxy_index.isValid():
            return
        try:
            src = self._proxy_model.mapToSource(proxy_index)
        except Exception:
            return
        if not src.isValid():
            return

        check_index = self._source_model.index(src.row(), _CharacterTableModel.COL_CHECK)
        try:
            cur = self._source_model.data(check_index, Qt.ItemDataRole.CheckStateRole)
            target = Qt.CheckState.Unchecked if cur == Qt.CheckState.Checked else Qt.CheckState.Checked
            self._source_model.setData(check_index, target, Qt.ItemDataRole.CheckStateRole)
        except Exception:
            return

    def _toggle_select_visible(self):
        visible_proxy_rows = self._proxy_model.rowCount()
        if visible_proxy_rows <= 0:
            return

        source_rows: list[int] = []
        checked = 0
        for r in range(visible_proxy_rows):
            proxy_idx = self._proxy_model.index(r, _CharacterTableModel.COL_CHECK)
            src_idx = self._proxy_model.mapToSource(proxy_idx)
            if not src_idx.isValid():
                continue
            source_rows.append(src_idx.row())
            try:
                if self._source_model.data(src_idx, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked:
                    checked += 1
            except Exception:
                pass

        all_checked = checked == len(source_rows)
        self._source_model.set_checked_for_source_rows(source_rows, checked=not all_checked)
        self._update_ui_state()

    def _update_ui_state(self):
        total = self._source_model.total_count()
        selected = self._source_model.selected_count()

        visible = self._proxy_model.rowCount()
        visible_checked = 0
        for r in range(visible):
            proxy_idx = self._proxy_model.index(r, _CharacterTableModel.COL_CHECK)
            src_idx = self._proxy_model.mapToSource(proxy_idx)
            if not src_idx.isValid():
                continue
            try:
                if self._source_model.data(src_idx, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked:
                    visible_checked += 1
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
        return self._source_model.get_selected_ids()
