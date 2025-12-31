# from functools import partial
# from pathlib import Path
# from typing import Optional
#
# import playsoundsimple
# from PySide6.QtCore import Qt
# from PySide6.QtGui import QDesktopServices
# from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout
# from playsoundsimple import Sound
# from qfluentwidgets import FluentIcon, HorizontalSeparator, PillToolButton, PlainTextEdit, PushButton, StrongBodyLabel, TitleLabel, TransparentPushButton
#
# from Source.Utility.tts_config_utility import VoiceData, tts_config_utility
#
#
# class TTSVoiceDetailSubWindow(QFrame):
#     def __init__(self, parent, tts_generate_window):
#         super().__init__(parent)
#         from Source.main_window import MainWindow
#         # noinspection PyTypeChecker
#         self._main_window: MainWindow = parent
#         from Source.UI.Interface.TTSInterface.tts_generate_window import TTSGenerateWindow
#         self._tts_generate_window: TTSGenerateWindow = tts_generate_window
#         self.setStyleSheet("TTSVoiceDetailSubWindow { border: 1px solid rgba(36, 36, 36, 0.2); border-radius: 10px; background-color: rgba(0, 0, 0, 0.06); }")
#
#         self.current_voice_name: Optional[str] = None
#         self.current_voice_id: Optional[str] = None
#         self.current_voice_data: Optional[dict] = None
#         self.current_audition_audio_path_list: list[str] = []
#         self.current_playing_audition_sound: Optional[Sound] = None
#         self.current_playing_audition_audio_path: Optional[str] = None
#         self.current_playing_audition_audio_index: Optional[int] = None
#         self.vbox_layout: QVBoxLayout = QVBoxLayout(self)
#         self._init_voice_name_layout()
#
#         self._separator1: HorizontalSeparator = HorizontalSeparator(self)
#         self.vbox_layout.addWidget(self._separator1)
#
#         self._init_voice_audition_layout()
#
#         self._separator2: HorizontalSeparator = HorizontalSeparator(self)
#         self.vbox_layout.addWidget(self._separator2)
#
#         self._init_voice_description_layout()
#
#         self.vbox_layout.addStretch()
#
#         self._separator3: HorizontalSeparator = HorizontalSeparator(self)
#         self.vbox_layout.addWidget(self._separator3)
#
#         self._init_function_layout()
#
#     def refresh(self):
#         current_voice_name = self._tts_generate_window.tts_voice_list_sub_window.current_select_voice_name
#         if not current_voice_name:
#             self.hide()
#         else:
#             if self.current_voice_name != current_voice_name:
#                 self.current_voice_id, self.current_voice_data = tts_config_utility.get_voice_data_by_voice_name(current_voice_name)
#                 self._voice_name_label.setText(self.current_voice_data.get(VoiceData.VOICE_NAME, ""))
#                 self._voice_description_text_edit.setPlainText(self.current_voice_data.get(VoiceData.DESCRIPTION, ""))
#                 self.show()
#                 self.current_voice_name = current_voice_name
#
#                 self._stop_audition_audio()
#
#                 voice_dir_path: str = tts_config_utility.get_voice_dir_path(self.current_voice_id)
#                 audio_path_list = tts_config_utility.get_files(voice_dir_path, ["mp3", "ogg", "wav"], is_recursively=False)
#                 for i in range(5):
#                     is_valid = False
#                     voice_audition_button = self._voice_audition_button_list[i]
#                     if i < len(self.current_audition_audio_path_list):
#                         voice_audition_button.clicked.disconnect()
#                         voice_audition_button.setChecked(False)
#                     if i < len(audio_path_list):
#                         is_valid = True
#                         voice_audition_button.clicked.connect(partial(self._on_voice_audition_button_click, i))
#                     voice_audition_button.setEnabled(is_valid)
#                     voice_audition_button.setIcon(FluentIcon.PLAY if is_valid else None)
#                 self.current_audition_audio_path_list = audio_path_list
#                 self.current_playing_audition_audio_path = None
#                 self.current_playing_audition_audio_index = None
#
#     def _init_voice_name_layout(self):
#         self._voice_name_layout: QHBoxLayout = QHBoxLayout()
#         self._voice_name_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
#         self._voice_name_label = TitleLabel(self)
#         self._voice_name_layout.addWidget(self._voice_name_label)
#
#         self._voice_name_layout.addStretch()
#
#         self._open_voice_dir_button = TransparentPushButton(self)
#         self._open_voice_dir_button.setIcon(FluentIcon.FOLDER)
#         self._open_voice_dir_button.setText(f"打开声线目录")
#         self._open_voice_dir_button.setCheckable(False)
#
#         def on_open_voice_dir_button_click(_):
#             QDesktopServices.openUrl(f"file:///{tts_config_utility.get_voice_dir_path(self.current_voice_id)}")
#
#         self._open_voice_dir_button.clicked.connect(on_open_voice_dir_button_click)
#         self._voice_name_layout.addWidget(self._open_voice_dir_button)
#
#         self.vbox_layout.addLayout(self._voice_name_layout)
#
#     def _init_voice_audition_layout(self):
#         self._voice_audition_label = StrongBodyLabel(self)
#         self._voice_audition_label.setText("试听")
#         self.vbox_layout.addWidget(self._voice_audition_label)
#
#         self._voice_audition_button_layout = QHBoxLayout()
#
#         self._voice_audition_button_list: list[PillToolButton] = []
#         for _ in range(5):
#             voice_audition_button = PillToolButton(FluentIcon.PLAY, self)
#             self._voice_audition_button_layout.addWidget(voice_audition_button)
#             voice_audition_button.setEnabled(False)
#             self._voice_audition_button_list.append(voice_audition_button)
#
#         self._voice_audition_button_layout.addStretch()
#
#         self.vbox_layout.addLayout(self._voice_audition_button_layout)
#
#     def _init_voice_description_layout(self):
#         self._voice_description_title_label = StrongBodyLabel(self)
#         self._voice_description_title_label.setText("描述")
#         self.vbox_layout.addWidget(self._voice_description_title_label)
#
#         self._voice_description_text_edit = PlainTextEdit(self)
#         self._voice_description_text_edit.setFixedHeight(100)
#         self.vbox_layout.addWidget(self._voice_description_text_edit)
#
#     def _init_function_layout(self):
#         self.get_voice_conditioning_latent_button = PushButton(self)
#         self.get_voice_conditioning_latent_button.setIcon(FluentIcon.ROBOT)
#         self.get_voice_conditioning_latent_button.setText("声线训练")
#         self.get_voice_conditioning_latent_button.clicked.connect(self._on_get_voice_conditioning_latent_button_click)
#         self.vbox_layout.addWidget(self.get_voice_conditioning_latent_button)
#
#         self._do_tts_button = PushButton(self)
#         self._do_tts_button.setIcon(FluentIcon.CHAT)
#         self._do_tts_button.setText("文本转语音")
#         self._do_tts_button.clicked.connect(self._on_do_tts_button_click)
#         self.vbox_layout.addWidget(self._do_tts_button)
#
#     def _on_voice_audition_button_click(self, index: int):
#         audio_path = self.current_audition_audio_path_list[index]
#         if not Path(audio_path).is_file():
#             return
#
#         if self.current_playing_audition_audio_index is None:
#             self.current_playing_audition_sound = playsoundsimple.Sound(audio_path)
#             self.current_playing_audition_sound.play()
#             self.current_playing_audition_audio_path = audio_path
#             self.current_playing_audition_audio_index = index
#             self._voice_audition_button_list[index].setChecked(True)
#         else:
#             if index == self.current_playing_audition_audio_index:
#                 self._stop_audition_audio()
#                 self.current_playing_audition_audio_index = None
#                 self.current_playing_audition_audio_path = None
#                 self._voice_audition_button_list[index].setChecked(False)
#             else:
#                 self._stop_audition_audio()
#                 self._voice_audition_button_list[self.current_playing_audition_audio_index].setChecked(False)
#                 self.current_playing_audition_sound = playsoundsimple.Sound(audio_path)
#                 self.current_playing_audition_sound.play()
#                 self.current_playing_audition_audio_path = audio_path
#                 self._voice_audition_button_list[index].setChecked(True)
#                 self.current_playing_audition_audio_index = index
#
#     def _stop_audition_audio(self):
#         if self.current_playing_audition_sound and self.current_playing_audition_sound.playing:
#             self.current_playing_audition_sound.stop()
#             self.current_playing_audition_sound = None
#
#     def _on_get_voice_conditioning_latent_button_click(self):
#         self._main_window.tts_job.get_voice_conditioning_latent_action(self.current_voice_id)
#
#     def _on_do_tts_button_click(self):
#         self._main_window.tts_job.do_tts_action(self.current_voice_id)
