"""Wwise WorkUnit 导入对话框

目标体验：
- 只从“叶子 WorkUnit”导入角色（避免 Sound/SFX 爆量导入）
- 只导入 Voices 作为参考音色（不使用 SFX）
- 支持按父 WorkUnit（例如 Boss）过滤 + 关键词过滤
- 支持全选/取消全选，且默认不全选

性能目标：
- 使用 Model/View 虚拟化渲染，避免为每行创建 QWidget（ListWidget + setItemWidget 的瓶颈）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor
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
    # PySide6-Fluent-Widgets: 保留 Fluent 风格，但仍走 Qt Model/View 性能
    from qfluentwidgets import TableView as FluentTableView
except Exception:
    FluentTableView = QTableView

from Source.Utility.wwise_character_discovery import WorkUnitCandidate


@dataclass
class _WorkUnitRowData:
    candidate: WorkUnitCandidate
    checked: bool = False


class _WorkUnitTableModel(QAbstractTableModel):
    selectionChanged = Signal()

    COL_CHECK = 0
    COL_PATH = 1
    COL_HAS_VOICE = 2
    COL_VOICE_COUNT = 3

    def __init__(self, candidates: Sequence[WorkUnitCandidate], parent: QWidget | None = None):
        super().__init__(parent)
        self._rows: list[_WorkUnitRowData] = [_WorkUnitRowData(c) for c in candidates]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return 4

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section == self.COL_CHECK:
                return ""
            if section == self.COL_PATH:
                return "WorkUnit"
            if section == self.COL_HAS_VOICE:
                return "参考Voice"
            if section == self.COL_VOICE_COUNT:
                return "Voice数"
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

        candidate = self._rows[row].candidate
        full_path = str(getattr(candidate, "full_path", None) or getattr(candidate, "name", None) or "").strip()
        has_voice = bool(getattr(candidate, "reference_voice_path", None))
        voice_count = int(getattr(candidate, "voice_count", 0) or 0)

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_PATH:
                return full_path
            if col == self.COL_HAS_VOICE:
                return "有" if has_voice else "无"
            if col == self.COL_VOICE_COUNT:
                return str(voice_count)
            return None

        if role == Qt.ItemDataRole.CheckStateRole:
            if col == self.COL_CHECK:
                return Qt.CheckState.Checked if self._rows[row].checked else Qt.CheckState.Unchecked
            return None

        if role == Qt.ItemDataRole.ToolTipRole:
            if col == self.COL_PATH:
                return full_path
            if col == self.COL_HAS_VOICE and has_voice:
                return str(getattr(candidate, "reference_voice_path", ""))
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (self.COL_HAS_VOICE, self.COL_VOICE_COUNT):
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.BackgroundRole:
            # 轻微的行底色差异，保持可读性；避免 heavy stylesheet
            if row % 2 == 1:
                return QColor(0, 0, 0, 0)
            return None

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

    def candidates(self) -> list[WorkUnitCandidate]:
        return [r.candidate for r in self._rows]

    def get_selected_candidates(self) -> list[WorkUnitCandidate]:
        return [r.candidate for r in self._rows if r.checked]

    def set_checked_for_source_rows(self, source_rows: Sequence[int], checked: bool):
        changed: list[int] = []
        for r in source_rows:
            if 0 <= r < len(self._rows) and self._rows[r].checked != bool(checked):
                self._rows[r].checked = bool(checked)
                changed.append(r)

        if not changed:
            return

        # 批量发射变更信号，避免逐行刷新
        min_row = min(changed)
        max_row = max(changed)
        left = self.index(min_row, self.COL_CHECK)
        right = self.index(max_row, self.COL_CHECK)
        self.dataChanged.emit(left, right, [Qt.ItemDataRole.CheckStateRole])
        self.selectionChanged.emit()


class _WorkUnitFilterProxyModel(QSortFilterProxyModel):
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
        if not hasattr(model, "_rows"):
            return True

        try:
            row_data = model._rows[source_row]  # type: ignore[attr-defined]
        except Exception:
            return True

        candidate = row_data.candidate

        if self._keyword_filter:
            label = str(getattr(candidate, "full_path", None) or getattr(candidate, "name", None) or "").lower()
            if self._keyword_filter not in label:
                return False

        return True


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
        # 保持参数兼容：外部可能仍传 default_parent，但该版本对话框不再提供“父 WorkUnit”下拉筛选
        self._default_parent = str(default_parent or "").strip()

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._apply_filters)

        self._source_model = _WorkUnitTableModel(self._all_candidates, self)
        self._proxy_model = _WorkUnitFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)

        self._init_ui()
        self._apply_filters()
        self._update_selected_count()
        self._update_select_toggle_button()

    def _init_ui(self):
        title_label = SubtitleLabel("从 Wwise 导入角色（按 WorkUnit）", self)
        self.viewLayout.addWidget(title_label)

        hint = BodyLabel("仅列出最低层 WorkUnit；只使用 Voices 作为参考音色。", self)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6b7280; font-size: 12px;")
        self.viewLayout.addWidget(hint)

        # 筛选行：关键词 + 全选按钮 + 已选统计（布局对齐“批量删除角色”对话框）
        filter_row = QWidget(self)
        filter_layout = QHBoxLayout(filter_row)
        filter_layout.setContentsMargins(0, 8, 0, 0)
        filter_layout.setSpacing(8)

        self._filter_edit = LineEdit(filter_row)
        self._filter_edit.setPlaceholderText("搜索 WorkUnit（支持关键字）")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.textChanged.connect(lambda _t="": self._schedule_apply_filters())
        filter_layout.addWidget(self._filter_edit, 1)

        self._select_toggle_btn = PushButton(FluentIcon.ACCEPT, "全选", filter_row)
        self._select_toggle_btn.clicked.connect(self._toggle_select_visible)
        filter_layout.addWidget(self._select_toggle_btn, 0)

        self._selected_count_label = CaptionLabel("已选 0", filter_row)
        filter_layout.addWidget(self._selected_count_label, 0)

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

        # 双击整行也能切换勾选（提升可用性）
        try:
            self._table.doubleClicked.connect(self._on_table_double_clicked)
        except Exception:
            pass

        self.widget.setMinimumWidth(760)
        self.widget.setMinimumHeight(520)
        self.yesButton.setText("导入选中")
        self.cancelButton.setText("取消")

        # 列宽：复选框列固定，其余列均分（更美观且随窗口自适应）
        try:
            header.setSectionResizeMode(_WorkUnitTableModel.COL_CHECK, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(_WorkUnitTableModel.COL_CHECK, 44)
            header.setSectionResizeMode(_WorkUnitTableModel.COL_PATH, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(_WorkUnitTableModel.COL_HAS_VOICE, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(_WorkUnitTableModel.COL_VOICE_COUNT, QHeaderView.ResizeMode.Stretch)
        except Exception:
            pass

        self._source_model.selectionChanged.connect(self._update_selected_count)
        self._source_model.selectionChanged.connect(self._update_select_toggle_button)

    def _schedule_apply_filters(self):
        """关键字输入防抖：避免大列表每个字符都全量刷新。"""
        try:
            self._filter_timer.start(180)
        except Exception:
            self._apply_filters()

    def _apply_filters(self):
        try:
            keyword = str(self._filter_edit.text() or "").strip()
        except Exception:
            keyword = ""
        self._proxy_model.set_keyword_filter(keyword)
        self._update_select_toggle_button()

    def _on_table_double_clicked(self, proxy_index: QModelIndex):
        if not proxy_index.isValid():
            return
        try:
            src = self._proxy_model.mapToSource(proxy_index)
        except Exception:
            return
        if not src.isValid():
            return

        check_index = self._source_model.index(src.row(), _WorkUnitTableModel.COL_CHECK)
        try:
            cur = self._source_model.data(check_index, Qt.ItemDataRole.CheckStateRole)
            target = Qt.CheckState.Unchecked if cur == Qt.CheckState.Checked else Qt.CheckState.Checked
            self._source_model.setData(check_index, target, Qt.ItemDataRole.CheckStateRole)
        except Exception:
            return

    def _toggle_select_visible(self):
        # 如果“可见项”全部已勾选 -> 取消全选；否则 -> 全选
        visible_proxy_rows = self._proxy_model.rowCount()
        if visible_proxy_rows <= 0:
            return

        source_rows: list[int] = []
        checked = 0
        for r in range(visible_proxy_rows):
            proxy_idx = self._proxy_model.index(r, _WorkUnitTableModel.COL_CHECK)
            src_idx = self._proxy_model.mapToSource(proxy_idx)
            if not src_idx.isValid():
                continue
            source_rows.append(src_idx.row())

            try:
                state = self._source_model.data(src_idx, Qt.ItemDataRole.CheckStateRole)
                if state == Qt.CheckState.Checked:
                    checked += 1
            except Exception:
                pass

        all_checked = checked == len(source_rows)
        self._source_model.set_checked_for_source_rows(source_rows, checked=not all_checked)
        self._update_select_toggle_button()

    def _update_select_toggle_button(self):
        # 根据可见项状态更新“全选/取消全选”按钮
        visible = self._proxy_model.rowCount()
        checked = 0
        for r in range(visible):
            proxy_idx = self._proxy_model.index(r, _WorkUnitTableModel.COL_CHECK)
            src_idx = self._proxy_model.mapToSource(proxy_idx)
            if not src_idx.isValid():
                continue
            try:
                if self._source_model.data(src_idx, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked:
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
        count = self._source_model.selected_count()
        total = self._source_model.total_count()
        try:
            self._selected_count_label.setText(f"已选 {count} / {total}")
        except Exception:
            pass

        self._update_select_toggle_button()

    def get_selected_candidates(self) -> List[WorkUnitCandidate]:
        return self._source_model.get_selected_candidates()
