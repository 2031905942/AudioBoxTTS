from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QAbstractItemView, QApplication, QHBoxLayout, QTreeWidgetItem, QWidget

from qfluentwidgets import TreeWidget


class CheckListWindow(QWidget):
    window_closed_signal = Signal()

    def __init__(self, title: str, check_list: list[tuple[str, bool, list | None]]):
        super().__init__()
        self.setWindowTitle(title)
        self.setStyleSheet("background-color: white")
        self._box_layout: QHBoxLayout = QHBoxLayout(self)
        self._tree_widget: TreeWidget = TreeWidget(self)

        self._tree_widget.setHeaderHidden(True)
        self._tree_widget.setExpandsOnDoubleClick(False)
        self._tree_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._box_layout.addWidget(self._tree_widget)

        for check in check_list:
            check: (str, bool, list | None)
            item: QTreeWidgetItem = QTreeWidgetItem([check[0]])
            # if check[1]:
            #     item.setCheckState(0, Qt.CheckState.Checked)
            # else:
            #     item.setCheckState(0, Qt.CheckState.Unchecked)
            if len(check) > 2 and check[2]:
                self._add_item(item, check[2])
            self._tree_widget.addTopLevelItem(item)

        self._tree_widget.expandAll()

        self._tree_widget.clicked.connect(self._change_item_expand_state)
        # self._tree_widget.itemChanged.connect(self._set_item_check_state)
        self._tree_widget.itemDoubleClicked.connect(self._copy_text_to_clipboard)
        self.resize(800, 800)
        self.show()

    def _add_item(self, parent_item: QTreeWidgetItem, child_check_list: list[tuple[str, bool, list | None]]):
        for check in child_check_list:
            check: (str, bool, list | None)
            item: QTreeWidgetItem = QTreeWidgetItem([check[0]])
            # if check[1]:
            #     item.setCheckState(0, Qt.CheckState.Checked)
            # else:
            #     item.setCheckState(0, Qt.CheckState.Unchecked)
            if len(check) > 2 and check[2]:
                self._add_item(item, check[3])
            parent_item.addChild(item)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.window_closed_signal.emit()
        event.accept()

    def _change_item_expand_state(self, index):
        if self._tree_widget.isExpanded(index):
            self._tree_widget.collapse(index)
        else:
            self._tree_widget.expand(index)

    def _set_item_check_state(self, item: QTreeWidgetItem):
        # selected_item_list = self._tree_widget.selectedItems()
        # for selected_item in selected_item_list:
        #     selected_item.setCheckState(0, self._tree_widget.currentItem().checkState(0))
        # self.set_item_check_state_recursively(selected_item, selected_item.checkState(0))

        current_item = item
        if current_item.checkState(0) != Qt.CheckState.PartiallyChecked:
            if current_item.childCount() > 0:
                for i in range(current_item.childCount()):
                    self.set_item_check_state_recursively(current_item.child(i), current_item.checkState(0))

        parent_item = current_item.parent()
        if parent_item:
            has_checked = False
            has_unchecked = False
            has_partially_checked = False
            for i in range(parent_item.childCount()):
                if item.checkState(0) == Qt.CheckState.Checked:
                    has_checked = True
                elif item.checkState(0) == Qt.CheckState.Unchecked:
                    has_unchecked = True
                else:
                    has_partially_checked = True
                if has_checked and has_unchecked or has_partially_checked:
                    parent_item.setCheckState(0, Qt.CheckState.PartiallyChecked)
                    break
                item = parent_item.child(i)

            if has_checked and not has_unchecked and not has_partially_checked:
                parent_item.setCheckState(0, Qt.CheckState.Checked)
            elif has_unchecked and not has_checked and not has_partially_checked:
                parent_item.setCheckState(0, Qt.CheckState.Unchecked)

    def set_item_check_state_recursively(self, item: QTreeWidgetItem, check_state: Qt.CheckState):
        item.setCheckState(0, check_state)
        if item.childCount() > 0:
            for i in range(item.childCount()):
                self.set_item_check_state_recursively(item.child(i), check_state)

    def _copy_text_to_clipboard(self):
        text: str = self._tree_widget.currentItem().text(0)
        # ResultInfoBar("success", "复制内容至剪切板", text, self)
        self.raise_()
        if text:
            QApplication.clipboard().setText(text)
