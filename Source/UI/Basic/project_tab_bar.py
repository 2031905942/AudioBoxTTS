from typing import Union

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QIcon, QMouseEvent
from qfluentwidgets import Action, FluentIcon, FluentIconBase, RoundMenu, TabBar, TabItem


class ProjectTabItem(TabItem):
    rename_signal: Signal = Signal(str)

    def mousePressEvent(self, e: QMouseEvent):
        super().mousePressEvent(e)

        if e.type() == QEvent.Type.MouseButtonPress and e.button() == Qt.MouseButton.RightButton:
            # print(f"右键: {self.routeKey()}")
            menu = RoundMenu(parent=self)
            rename_project_action: Action = Action(FluentIcon.QUICK_NOTE, "重命名")
            rename_project_action.triggered.connect(self.on_rename_requested)
            menu.addAction(rename_project_action)
            menu.exec(e.globalPos())

    def on_rename_requested(self):
        self.rename_signal.emit(self.routeKey())


class ProjectTabBar(TabBar):
    tab_item_swaped_signal: Signal = Signal(int)

    # noinspection PyPep8Naming
    def insertTab(self, index: int, routeKey: str, text: str, icon: Union[QIcon, str, FluentIconBase] = None, onClick=None):
        if routeKey in self.itemMap:
            raise ValueError(f"The route key `{routeKey}` is duplicated.")

        if index == -1:
            index = len(self.items)

        # adjust current index
        if index <= self.currentIndex() and self.currentIndex() >= 0:
            self._currentIndex += 1

        item = ProjectTabItem(text, self.view, icon)
        item.setRouteKey(routeKey)

        # set the size of tab
        # w = self.tabMaximumWidth() if self.isScrollable() else self.tabMinimumWidth()
        item.setMinimumWidth(180)
        item.setMaximumWidth(180)

        item.setShadowEnabled(self.isTabShadowEnabled())
        item.setCloseButtonDisplayMode(self.closeButtonDisplayMode)
        item.setSelectedBackgroundColor(self.lightSelectedBackgroundColor, self.darkSelectedBackgroundColor)

        item.pressed.connect(self._onItemPressed)
        item.closed.connect(lambda: self.tabCloseRequested.emit(self.items.index(item)))
        if onClick:
            item.pressed.connect(onClick)

        self.itemLayout.insertWidget(index, item, 1)
        self.items.insert(index, item)
        self.itemMap[routeKey] = item

        if len(self.items) == 1:
            self.setCurrentIndex(0)

        return item

    def _swapItem(self, index: int):
        self.tab_item_swaped_signal.emit(index)
        super()._swapItem(index)
