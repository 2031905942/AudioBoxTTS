# import os
# from pathlib import Path
# from typing import Optional
#
# from PySide6.QtCore import Qt
# from PySide6.QtWidgets import QAbstractItemView, QFrame, QListWidgetItem, QVBoxLayout
#
# from Source.UI.Basic.line_edit_window import LineEditWindow
# from Source.Utility.tts_config_utility import TTS_VOICE_DIR_PATH, VoiceData, tts_config_utility
# from qfluentwidgets import Action, Dialog, FluentIcon, HorizontalSeparator, ListWidget, PushButton, RoundMenu, SubtitleLabel
# from send2trash import send2trash
#
#
# class TTSVoiceListSubWindow(QFrame):
#     def __init__(self, parent, tts_generate_window):
#         super().__init__(parent)
#         from Source.UI.Interface.TTSInterface.tts_generate_window import TTSGenerateWindow
#         self._tts_generate_window: TTSGenerateWindow = tts_generate_window
#         from Source.main_window import MainWindow
#         parent: MainWindow
#         self._main_window = parent
#         self._tts_job = self._main_window.tts_job
#         self._project_title_edit_window: LineEditWindow | None = None
#
#         self.setStyleSheet("TTSVoiceListSubWindow { border: 1px solid rgba(36, 36, 36, 0.2); border-radius: 10px; background-color: rgba(0, 0, 0, 0.06); }")
#         self.setMaximumWidth(250)
#
#         self.current_select_voice_name: Optional[str] = None
#
#         self.vbox_layout: QVBoxLayout = QVBoxLayout(self)
#         self._init_voice_list_view()
#         self._refresh_voice_list_widget()
#
#     def refresh(self):
#         self._refresh_voice_list_widget()
#
#     def _init_voice_list_view(self):
#         self._voice_list_title_label: SubtitleLabel = SubtitleLabel(self)
#         self._voice_list_title_label.setText("声线列表")
#         self.vbox_layout.addWidget(self._voice_list_title_label)
#
#         self._separator1: HorizontalSeparator = HorizontalSeparator(self)
#         self.vbox_layout.addWidget(self._separator1)
#
#         self._voice_list_widget: ListWidget = ListWidget(self)
#         self._voice_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
#         self._voice_list_widget.itemSelectionChanged.connect(self._on_voice_item_changed)
#         self._voice_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
#         self._voice_list_widget.customContextMenuRequested.connect(self._on_voice_item_right_clicked)
#         self.vbox_layout.addWidget(self._voice_list_widget)
#
#         self._separator2: HorizontalSeparator = HorizontalSeparator(self)
#         self.vbox_layout.addWidget(self._separator2)
#
#         self._add_voice_button = PushButton(self)
#         self._add_voice_button.setText("新增声线")
#         self._add_voice_button.setIcon(FluentIcon.ADD)
#         self._add_voice_button.clicked.connect(self._on_add_voice_button_clicked)
#         self.vbox_layout.addWidget(self._add_voice_button)
#
#     def _refresh_voice_list_widget(self):
#         self._voice_list_widget.clear()
#         voice_name_list: list[str] = []
#         for voice_data in tts_config_utility.config_data.values():
#             voice_name_list.append(voice_data.get(VoiceData.VOICE_NAME))
#         voice_name_list.sort()
#         for voice_name in voice_name_list:
#             item: QListWidgetItem = QListWidgetItem(voice_name)
#             self._voice_list_widget.addItem(item)
#
#     def _on_voice_item_changed(self):
#         if self._voice_list_widget.currentItem():
#             self.current_select_voice_name = self._voice_list_widget.currentItem().text()
#             self._tts_generate_window.tts_voice_detail_sub_window.refresh()
#
#     def _on_voice_item_right_clicked(self, pos):
#         list_widget_item = self._voice_list_widget.itemAt(pos)
#         if not list_widget_item:
#             return
#
#         menu = RoundMenu(parent=self)
#
#         rename_action = Action(FluentIcon.SYNC, "重命名")
#         rename_action.triggered.connect(lambda: self._on_rename_voice_button_clicked(list_widget_item))
#         menu.addAction(rename_action)
#
#         delete_action = Action(FluentIcon.DELETE, "删除")
#         delete_action.triggered.connect(lambda: self._on_delete_voice_button_clicked(list_widget_item))
#         menu.addAction(delete_action)
#
#         menu.exec(self._voice_list_widget.mapToGlobal(pos))
#
#     def _on_add_voice_button_clicked(self):
#         self._project_title_edit_window = LineEditWindow("请输入声线名称")
#         self._project_title_edit_window.confirm_signal.connect(self._on_add_voice)
#         return
#
#     def _on_add_voice(self, voice_name: str):
#         import uuid
#         voice_id: str = str(uuid.uuid4())
#         if tts_config_utility.get_voice_data_by_voice_name(voice_name) is not None:
#             self._tts_job.show_error_info_bar(f"无法新增声线\"{voice_name}\", 已存在相同名称的声线")
#             return
#         if tts_config_utility.add_voice_data(voice_id, voice_name):
#             tts_config_utility.create_directory(f"{TTS_VOICE_DIR_PATH}/{voice_name}")
#             tts_config_utility.set_voice_data_config(voice_id, VoiceData.IS_BUILD_IN, False)
#             self._tts_generate_window.refresh()
#             self._tts_job.show_result_info_bar("success", "结果", f"新增声线\"{voice_name}\"成功")
#
#     def _on_rename_voice_button_clicked(self, voice_item: QListWidgetItem):
#         self._project_title_edit_window = LineEditWindow("请输入声线名称")
#         self._project_title_edit_window.confirm_signal.connect(lambda new_name: self._on_rename_voice(voice_item, new_name))
#         return
#
#     def _on_rename_voice(self, voice_item: QListWidgetItem, voice_name: str):
#         old_voice_name = voice_item.text()
#         if tts_config_utility.get_voice_data_by_voice_name(voice_name) is not None:
#             self._tts_job.show_error_info_bar(f"无法重命名为声线名称\"{voice_name}\", 已存在相同名称的声线")
#             return
#         if tts_config_utility.rename_voice_data(old_voice_name, voice_name):
#             self._tts_generate_window.refresh()
#             self._tts_job.show_result_info_bar("success", "结果", f"重命名声线\"{old_voice_name}\"为\"{voice_name}\"成功")
#
#     def _on_delete_voice_button_clicked(self, voice_item: QListWidgetItem):
#         if voice_item:
#             dialog: Dialog = Dialog("确认删除声线？", f"{voice_item.text()}", self._main_window)
#             if dialog.exec():
#                 voice_id, _ = tts_config_utility.get_voice_data_by_voice_name(voice_item.text())
#                 if voice_id:
#                     voice_dir_path: str = tts_config_utility.get_voice_dir_path(voice_id)
#                     if not voice_dir_path or not os.path.isdir(voice_dir_path):
#                         self._tts_job.show_error_info_bar(f"无法删除声线\"{voice_item.text()}\", 对应声线的目录不存在.")
#                     else:
#                         voice_dir_path = str(Path(voice_dir_path).resolve())
#                         try:
#                             send2trash(voice_dir_path)
#                             self._tts_job.show_result_info_bar("success", "结果", f"删除声线\"{voice_item.text()}\"成功\n已删除至回收站")
#                         except Exception as error:
#                             self._tts_job.show_error_info_bar(f"删除声线发生异常:\n{error}")
#                     tts_config_utility.delete_voice_data(voice_id)
#                 else:
#                     self._tts_job.show_error_info_bar(f"无法删除声线\"{voice_item.text()}\", 对应声线ID不存在.")
#                 self._tts_generate_window.refresh()
#         else:
#             self._tts_job.show_result_info_bar("warning", "结果", "未选中声线, 删除任务中止")
