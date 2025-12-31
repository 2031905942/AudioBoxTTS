from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QAbstractItemView, QApplication, QHBoxLayout, QTreeWidgetItem, QWidget

from Source.UI.Basic.wwise_object_tree_widget_item import WwiseObjectTreeWidgetItem
from qfluentwidgets import TreeWidget
from waapi import CannotConnectToWaapiException, WaapiClient


class WwiseObjectCheckWindow(QWidget):
    window_closed_signal = Signal()

    def __init__(self, title: str, check_list: list[tuple[str, str | None, list | None]]):
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
            check: (str, str | None, list | None)
            item: WwiseObjectTreeWidgetItem = WwiseObjectTreeWidgetItem([check[0]])
            wwise_object_id: str | None = check[1]
            item.wwise_object_id = wwise_object_id
            if len(check) > 2 and check[2]:
                self._add_item(item, check[2])
            self._tree_widget.addTopLevelItem(item)

        self._tree_widget.expandAll()

        self._tree_widget.clicked.connect(self._change_item_expand_state)
        self._tree_widget.itemDoubleClicked.connect(WwiseObjectCheckWindow._on_item_double_clicked)
        self.resize(800, 800)
        self.show()

    def _add_item(self, parent_item: QTreeWidgetItem, child_check_list: list[tuple[str, str | None, list | None]]):
        for check in child_check_list:
            check: (str, str | None, list | None)
            item: WwiseObjectTreeWidgetItem = WwiseObjectTreeWidgetItem([check[0]])
            wwise_object_id: str | None = check[1]
            item.wwise_object_id = wwise_object_id
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

    @staticmethod
    def _on_item_double_clicked(item):
        item: WwiseObjectTreeWidgetItem
        text: str = item.text(0)
        if text:
            QApplication.clipboard().setText(text)

        if item.wwise_object_id:
            try:
                with WaapiClient() as client:
                    args = {
                        "command": "FindInProjectExplorerSyncGroup1",
                        "objects": [
                            f"{item.wwise_object_id}"
                        ]
                    }
                    client.call("ak.wwise.ui.commands.execute", args)
                    args = {
                        "command": "Inspect",
                        "objects": [
                            f"{item.wwise_object_id}"
                        ]
                    }
                    client.call("ak.wwise.ui.commands.execute", args)
            except CannotConnectToWaapiException:
                # print("无法连接Waapi: 请确认Wwise打开并开启Waapi相关功能?")
                pass
