from PySide6.QtWidgets import QTreeWidgetItem


class WwiseObjectTreeWidgetItem(QTreeWidgetItem):
    def __init__(self, other):
        super().__init__(other)
        self.wwise_object_id: str | None = None
