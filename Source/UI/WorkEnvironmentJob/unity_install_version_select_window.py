from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QAbstractItemView, QTreeWidgetItem, QVBoxLayout, QWidget

from qfluentwidgets import Dialog, FluentIcon, HorizontalSeparator, LargeTitleLabel, PushButton, StrongBodyLabel, TitleLabel, TreeWidget


class UnityInstallVersionSelectWindow(QWidget):
    confirm_signal = Signal(list, dict)
    window_closed_signal = Signal()

    unity_install_root_path = f"C:/Program Files"

    def __init__(self, version_info_dict: dict):
        self._version_info_dict = version_info_dict

        super().__init__()
        self.setWindowTitle("Unity引擎安装窗口")
        self.setStyleSheet("background-color: white")
        self._layout = QVBoxLayout(self)
        self._unity_version_list_tree_widget: TreeWidget = TreeWidget(self)

        self._unity_install_title_label = LargeTitleLabel(self)
        self._unity_install_title_label.setText("Unity引擎安装")
        self._layout.addWidget(self._unity_install_title_label)

        self._unity_install_sub_label = StrongBodyLabel(self)
        self._unity_install_sub_label.setText("请选择需要安装的Unity引擎版本")
        self._layout.addWidget(self._unity_install_sub_label)

        self._init_unity_version_list_tree_widget()

        self._separator1 = HorizontalSeparator(self)
        self._layout.addWidget(self._separator1)
        self._layout.addSpacing(10)

        self._unity_install_info_title_label = TitleLabel(self)
        self._unity_install_info_title_label.setText("安装信息")
        self._layout.addWidget(self._unity_install_info_title_label)

        self._unity_install_info_content_label = StrongBodyLabel(self)
        self._unity_install_info_content_label.setText("")
        self._layout.addWidget(self._unity_install_info_content_label)
        # self.resize(800, 600)

        self._separator2 = HorizontalSeparator(self)
        self._layout.addWidget(self._separator2)

        self._layout.addSpacing(10)

        self._confirm_button = PushButton(self)
        self._confirm_button.setIcon(FluentIcon.SEND)
        self._confirm_button.setText("确认")
        self._confirm_button.clicked.connect(self._on_confirmed)
        self._layout.addWidget(self._confirm_button)
        self.show()

    def _init_unity_version_list_tree_widget(self):
        self._unity_version_list_tree_widget.setHeaderHidden(True)
        self._unity_version_list_tree_widget.setExpandsOnDoubleClick(False)
        self._unity_version_list_tree_widget.setMaximumHeight(400)
        self._unity_version_list_tree_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._layout.addWidget(self._unity_version_list_tree_widget)

        for version in self._version_info_dict.keys():
            item = QTreeWidgetItem()
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setText(0, version)
            self._unity_version_list_tree_widget.addTopLevelItem(item)

        self._unity_version_list_tree_widget.expandAll()

        self._unity_version_list_tree_widget.itemChanged.connect(self._set_item_check_state)  #

    def closeEvent(self, event: QCloseEvent) -> None:
        self.window_closed_signal.emit()
        event.accept()

    def _set_item_check_state(self, item: QTreeWidgetItem):
        self._unity_install_info_content_label.setText("")
        unity_install_info_content = ""
        for i in range(0, self._unity_version_list_tree_widget.topLevelItemCount()):
            item = self._unity_version_list_tree_widget.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Unchecked:
                continue
            version = item.text(0)
            unity_install_path = f"{self.unity_install_root_path}/Unity {version}"
            unity_install_info_content = f"{unity_install_info_content}\n将会安装Unity {version}至\"{unity_install_path}\", 包含组件:\n"
            for installer in self._version_info_dict[version]:
                unity_install_info_content = f"{unity_install_info_content}* {installer}\n"

        self._unity_install_info_content_label.setText(unity_install_info_content)

    def _on_confirmed(self):
        install_version_list = []
        for i in range(0, self._unity_version_list_tree_widget.topLevelItemCount()):
            item = self._unity_version_list_tree_widget.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Unchecked:
                continue
            version = item.text(0)
            install_version_list.append(version)

        if len(install_version_list) == 0:
            dialog = Dialog("提醒", "未选择Unity引擎\n请选择版本后重试", self)
            dialog.cancelButton.setHidden(True)
            return dialog.exec()

        dialog_content = f"Unity版本:"
        for version in install_version_list:
            dialog_content = f"{dialog_content}\n* {version}"
        dialog = Dialog("确认安装Unity引擎", dialog_content, self)
        result = dialog.exec()
        if result:
            self.confirm_signal.emit(install_version_list, self._version_info_dict)
            self.close()
