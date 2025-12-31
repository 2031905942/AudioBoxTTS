# import os.path
# from typing import Optional
#
# from PySide6.QtCore import QStandardPaths, Signal
# from PySide6.QtWidgets import QFileDialog
# from TTS.utils.synthesizer import Synthesizer
#
# from Source.Job.base_job import BaseJob
# from Source.UI.Basic.line_edit_window import LineEditWindow
# from Source.UI.Basic.progress_ring_window import ProgressRingWindow
# from Source.UI.Basic.tts_text_edit_window import TTSTextEditWindow
# from Source.Utility.tts_config_utility import VoiceData, tts_config_utility
# from Source.Utility.tts_utility import TTSUtility
#
#
# class TTSJob(BaseJob):
#
#     # 信号定义
#     generate_lyric_audio_signal = Signal(str, str)
#     get_voice_conditioning_latent_signal = Signal(str, str)
#     do_tts_signal = Signal(str, dict)
#
#     def __init__(self, main_window):
#         super().__init__(main_window)
#         self.synthesizer_dict: dict = {}
#         self._tts_utility: Optional[TTSUtility] = None
#         self._text_edit_window: Optional[LineEditWindow] = None
#
#     def generate_lyric_audio_action(self):
#         lyric_workbook_dialog: QFileDialog = QFileDialog(self.main_window)
#         lyric_workbook_dialog.setWindowTitle("请选择歌词工作簿")
#         lyric_workbook_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
#         lyric_workbook_dialog.setViewMode(QFileDialog.ViewMode.List)
#         set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
#         lyric_workbook_dialog.setDirectory(set_directory)
#
#         lyric_workbook_path = ""
#         if lyric_workbook_dialog.exec():
#             lyric_workbook_path = lyric_workbook_dialog.selectedFiles()[0]
#             set_directory = os.path.dirname(lyric_workbook_path)
#
#         if not lyric_workbook_path:
#             return
#
#         generate_dir_dialog: QFileDialog = QFileDialog(self.main_window)
#         generate_dir_dialog.setWindowTitle("请选择音频合成目录")
#         generate_dir_dialog.setFileMode(QFileDialog.FileMode.Directory)
#         generate_dir_dialog.setViewMode(QFileDialog.ViewMode.List)
#         generate_dir_dialog.setDirectory(set_directory)
#
#         generate_dir_path = ""
#         if generate_dir_dialog.exec():
#             generate_dir_path = generate_dir_dialog.selectedFiles()[0]
#
#         if not generate_dir_path:
#             return
#
#         if self._create_dialog("确认执行歌词音频合成?", f"歌词工作簿路径: \"{lyric_workbook_path}\"\n音频合成目录路径: \"{generate_dir_path}\"", ):
#             self._create_utility()
#             self._tts_utility.moveToThread(self.worker_thread)
#             self.start_worker()
#             self._create_progress_ring_window()
#             self.generate_lyric_audio_signal.emit(lyric_workbook_path, generate_dir_path)
#
#     def get_voice_conditioning_latent_action(self, voice_id: str):
#         voice_dir_path = tts_config_utility.get_voice_dir_path(voice_id)
#         voice_dir_dialog: QFileDialog = QFileDialog(self.main_window)
#         voice_dir_dialog.setWindowTitle("请选择训练用的样本目录")
#         voice_dir_dialog.setFileMode(QFileDialog.FileMode.Directory)
#         voice_dir_dialog.setViewMode(QFileDialog.ViewMode.List)
#         voice_dir_dialog.setDirectory(voice_dir_path)
#
#         voice_dir_path = ""
#         if voice_dir_dialog.exec():
#             voice_dir_path = voice_dir_dialog.selectedFiles()[0]
#
#         if not voice_dir_path:
#             return
#
#         if self._create_dialog("确认执行声线训练?", f"训练用的样本目录: \"{voice_dir_path}\"", ):
#             self._create_utility()
#             self._tts_utility.moveToThread(self.worker_thread)
#             self.start_worker()
#             self._create_progress_ring_window()
#             self._progress_ring_window.set_enable_cancel(False)
#             self.get_voice_conditioning_latent_signal.emit(voice_id, voice_dir_path)
#
#     def do_tts_action(self, voice_id: str):
#         generate_dir_dialog: QFileDialog = QFileDialog(self.main_window)
#         generate_dir_dialog.setWindowTitle("请选择音频生成目录")
#         generate_dir_dialog.setFileMode(QFileDialog.FileMode.Directory)
#         generate_dir_dialog.setViewMode(QFileDialog.ViewMode.List)
#         generate_dir_dialog.setDirectory(QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0])
#         generate_dir_path = ""
#         if generate_dir_dialog.exec():
#             generate_dir_path = generate_dir_dialog.selectedFiles()[0]
#         if not generate_dir_path:
#             return
#         arg_dict: dict = {
#             "generate_dir_path": generate_dir_path
#         }
#         self._text_edit_window = TTSTextEditWindow("请输入文本", arg_dict)
#         self._text_edit_window.confirm_signal.connect(lambda confirm_arg_dict: self.do_tts_confirm_action(voice_id, confirm_arg_dict))
#         return
#
#     def do_tts_confirm_action(self, voice_id: str, arg_dict: dict):
#         if self._text_edit_window is not None:
#             self._text_edit_window.close()
#             self._text_edit_window = None
#         voice_name: str = tts_config_utility.config_data[voice_id][VoiceData.VOICE_NAME]
#         text = arg_dict["text"]
#         language = arg_dict["language"]
#         generate_dir_path = arg_dict["generate_dir_path"]
#         if self._create_dialog("确认执行文本转语音?", f"声线: \"{voice_name}\"\n台本: \"{text}\"\n语言: \"{language}\"\n语音生成目录: \"{generate_dir_path}\""):
#             self._create_utility()
#             self._tts_utility.moveToThread(self.worker_thread)
#             self.start_worker()
#             self._create_progress_ring_window()
#             self.do_tts_signal.emit(voice_id, arg_dict)
#
#     def _create_utility(self):
#         self._tts_utility: TTSUtility = TTSUtility(self, self.synthesizer_dict)
#
#         self.generate_lyric_audio_signal.connect(self._tts_utility.generate_lyric_audio)
#         self.get_voice_conditioning_latent_signal.connect(self._tts_utility.get_voice_conditioning_latent)
#         self.do_tts_signal.connect(self._tts_utility.do_tts)
#
#         self._tts_utility.cache_synthesizer_signal.connect(self._cache_synthesizer)
#
#     def _create_progress_ring_window(self):
#         self._progress_ring_window: ProgressRingWindow = ProgressRingWindow(self.main_window)
#
#         if self._tts_utility:
#             self._tts_utility.update_progress_text_signal.connect(self._progress_ring_window.set_text)
#             self._progress_ring_window.cancel_signal.connect(lambda: self._tts_utility.notice_cancel_job())
#
#     def _cache_synthesizer(self, synthesizer_name: str, synthesizer: Synthesizer):
#         self.synthesizer_dict[synthesizer_name] = synthesizer
