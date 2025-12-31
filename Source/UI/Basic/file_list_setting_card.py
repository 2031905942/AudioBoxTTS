import os.path

from PySide6.QtCore import QStandardPaths, Qt, Signal
from PySide6.QtWidgets import QFileDialog

from qfluentwidgets import ConfigItem, Dialog, ExpandSettingCard, FluentIcon, PushButton, qconfig
from qfluentwidgets.components.settings.folder_list_setting_card import FolderItem


class FileListSettingCard(ExpandSettingCard):
    file_list_changed = Signal(list)

    def __init__(self, parent, config_item: ConfigItem, title: str, content: str = None, file_dialogue_config: dict = None):
        super().__init__(FluentIcon.APPLICATION, title, content, parent)
        self.main_window = parent
        self.config_item = config_item
        self._file_dialogue_config: dict = {}
        if file_dialogue_config:
            self._file_dialogue_config = file_dialogue_config
        self.add_file_button = PushButton("添加路径", self, FluentIcon.ADD)
        self.file_list = qconfig.get(config_item).copy()
        self.__initWidget()

    def __initWidget(self):
        self.addWidget(self.add_file_button)
        self.viewLayout.setSpacing(0)
        self.viewLayout.setAlignment(Qt.AlignTop)
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        for file in self.file_list:
            self._add_file_item(file)

        self.add_file_button.clicked.connect(self._show_add_file_dialog)

    def _show_add_file_dialog(self):
        file_dialog = QFileDialog(self.main_window)
        title = self._file_dialogue_config.get("title", "")
        if title:
            file_dialog.setWindowTitle(title)
        else:
            file_dialog.setWindowTitle("请选择文件")

        dir_path = self._file_dialogue_config.get("dir_path", "")

        if len(self.file_list) > 0:
            dir_path = os.path.dirname(self.file_list[0])
        if dir_path:
            file_dialog.setDirectory(dir_path)
        else:
            file_dialog.setDirectory(QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0])

        name_filter = self._file_dialogue_config.get("name_filter", "")
        if name_filter:
            file_dialog.setNameFilter(name_filter)

        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setViewMode(QFileDialog.ViewMode.List)
        file_path = ""
        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]

        if file_path and file_path not in self.file_list:
            self._add_file_item(file_path)
            self.file_list.append(file_path)
            qconfig.set(self.config_item, self.file_list)
            self.file_list_changed.emit(self.file_list)

    def _add_file_item(self, file: str):
        item = FolderItem(file, self.view)
        item.removed.connect(self._show_confirm_dialog)
        self.viewLayout.addWidget(item)
        item.show()
        self._adjustViewSize()

    def _show_confirm_dialog(self, item: FolderItem):
        name = item.folder
        title = "确认删除路径吗?"
        content = f"\"{name}\""
        w = Dialog(title, content, self.main_window)
        w.yesSignal.connect(lambda: self._remove_file(item))
        w.exec_()

    def _remove_file(self, item: FolderItem):
        if item.folder not in self.file_list:
            return

        self.file_list.remove(item.folder)
        self.viewLayout.removeWidget(item)
        item.deleteLater()
        self._adjustViewSize()

        self.file_list_changed.emit(self.file_list)
        qconfig.set(self.config_item, self.file_list)
