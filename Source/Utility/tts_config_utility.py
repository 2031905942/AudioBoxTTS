'''
import json
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QFile

from Source.Utility.file_utility import FileUtility
from main import ROOT_PATH

TTS_RESOURCE_DIR_PATH = f"{ROOT_PATH}/Resource/TTS"
TTS_VOICE_DIR_PATH = f"{TTS_RESOURCE_DIR_PATH}/Voice"


class VoiceData:
    VOICE_NAME = "VoiceName"
    IS_BUILD_IN = "IsBuildIn"
    DESCRIPTION = "Description"


class TTSConfigUtility(FileUtility):
    _CONFIG_FILE_NAME = "Config.json"

    def __init__(self):
        self.config_data: {} = {}
        self.config_file_path: str = ""
        self.config_file_path = f"{TTS_RESOURCE_DIR_PATH}/{TTSConfigUtility._CONFIG_FILE_NAME}"
        self.create_directory(TTS_RESOURCE_DIR_PATH)
        self.create_directory(TTS_VOICE_DIR_PATH)
        self._read_config_data()
        self.sync_tts_voice_data_from_tts_voice_dir()

    def add_voice_data(self, voice_id: str, voice_name: str) -> bool:
        if not voice_id:
            self._print_log_error("无法添加声线数据, 声线ID为空.")
            return False
        if not voice_name:
            self._print_log_error("无法添加声线数据, 声线名称为空.")
            return False
        if voice_id not in self.config_data.keys():
            self.config_data[voice_id] = {
                VoiceData.VOICE_NAME: voice_name
            }
            return self._write_config_data()
        else:
            if self.config_data[voice_id][VoiceData.VOICE_NAME] != voice_name:
                self.config_data[voice_id][VoiceData.VOICE_NAME] = voice_name
                return self._write_config_data()
        return True

    def delete_voice_data(self, voice_id: str) -> bool:
        if not voice_id:
            self._print_log_error("无法删除声线数据, 声线ID为空.")
            return False
        if voice_id not in self.config_data.keys():
            return True
        else:
            self.config_data.pop(voice_id)
            return self._write_config_data()

    def set_voice_data_config(self, voice_id: str, config_name: str, config_value) -> bool:
        if not voice_id:
            self._print_log_error("无法设置声线数据, 声线ID为空.")
            return False
        if not config_name:
            self._print_log_error("无法设置声线数据, 设置名称为空.")
            return False
        voice_data: Optional[dict] = self.config_data.get(voice_id)
        if not voice_data:
            self._print_log_error(f"无法设置声线数据, 声线ID\"{voice_id}\"数据不存在.")
            return False
        if config_value != self.config_data[voice_id].get(config_name):
            self.config_data[voice_id][config_name] = config_value
            return self._write_config_data()
        return True

    def remove_voice_data(self, voice_id: str) -> bool:
        if not voice_id:
            self._print_log_error("无法删除声线数据, 声线ID为空.")
            return False
        if voice_id in self.config_data.keys():
            self.config_data.pop(voice_id)
            self._write_config_data()

    def get_voice_data_config(self, voice_id: str, config_name: str) -> Optional:
        if not voice_id:
            self._print_log_error("无法获取声线数据的设置, 声线ID为空.")
            return None
        if not config_name:
            self._print_log_error("无法获取声线数据的设置, 设置名称为空.")
            return None

        if voice_id in self.config_data.keys():
            return self.config_data[voice_id].get(config_name, "")
        else:
            self._print_log_error(f"无法获取声线数据的设置, 声线ID\"{voice_id}\"数据不存在.")
            return None

    def get_voice_data_by_voice_name(self, voice_name: str) -> Optional[tuple[str, dict]]:
        if not voice_name:
            self._print_log_error("无法获取声线数据, 声线名称为空.")
            return None

        for voice_id, voice_data in self.config_data.items():
            if voice_data.get(VoiceData.VOICE_NAME) == voice_name:
                return voice_id, voice_data
        return None

    def get_voice_dir_path(self, voice_id: str) -> Optional[str]:
        if not voice_id:
            self._print_log_error("无法获取声线数据的设置, 声线ID为空.")
            return None
        if voice_id not in self.config_data.keys():
            self._print_log_error(f"无法获取声线数据的设置, 声线ID\"{voice_id}\"数据不存在.")
            return None
        voice_name: str = self.config_data[voice_id][VoiceData.VOICE_NAME]
        dir_path = f"{TTS_VOICE_DIR_PATH}/{voice_name}"
        dir_path = str(Path(dir_path).resolve())
        return dir_path

    def sync_tts_voice_data_from_tts_voice_dir(self):
        dir_path_list = [TTS_VOICE_DIR_PATH]
        voice_name_set: set[str] = set()
        is_config_data_change = False
        for dir_path in dir_path_list:
            scan_dir_iterator = os.scandir(dir_path)
            for dir_entry in scan_dir_iterator:
                dir_entry: os.DirEntry
                if not dir_entry.is_dir():
                    continue
                voice_name: str = dir_entry.name
                voice_name_set.add(voice_name)
                voice_data = self.get_voice_data_by_voice_name(voice_name)
                voice_id = ""
                if not voice_data:
                    import uuid
                    voice_id = str(uuid.uuid4())
                    if self.add_voice_data(voice_id, voice_name):
                        is_config_data_change = True
                else:
                    voice_id = voice_data[0]
                is_build_in = False
                is_build_in_from_config = self.get_voice_data_config(voice_id, VoiceData.IS_BUILD_IN)
                if is_build_in != is_build_in_from_config:
                    self.set_voice_data_config(voice_id, VoiceData.IS_BUILD_IN, is_build_in)
                    is_config_data_change = True
        remove_voice_id_list: list[str] = []
        for voice_id, voice_data in self.config_data.items():
            if voice_data.get(VoiceData.VOICE_NAME) not in voice_name_set:
                remove_voice_id_list.append(voice_id)
                is_config_data_change = True
        for remove_voice_id in remove_voice_id_list:
            self.config_data.pop(remove_voice_id)
        if is_config_data_change:
            self._write_config_data()

    def rename_voice_data(self, voice_name: str, new_voice_name: str) -> bool:
        if not new_voice_name:
            self._print_log_error(f"无法重命名声线, 新声线名称为空.")
            return False
        if self.get_voice_data_by_voice_name(new_voice_name) is not None:
            self._print_log_error(f"无法重命名声线, 新声线名称已经存在.")
            return False
        _, voice_data = self.get_voice_data_by_voice_name(voice_name)
        voice_data: dict
        parent_dir = TTS_VOICE_DIR_PATH

        voice_dir = f"{parent_dir}/{voice_name}"
        new_voice_dir = f"{parent_dir}/{new_voice_name}"

        try:
            os.rename(voice_dir, new_voice_dir)
        except Exception as error:
            self._print_log_error(f"重命名目录\"{voice_dir}\"至\"{new_voice_dir}\"发生异常\n{error}")
            return False

        voice_data[VoiceData.VOICE_NAME] = new_voice_name
        return self._write_config_data()

    def _read_config_data(self) -> bool:
        if QFile.exists(self.config_file_path):
            try:
                config_file = open(self.config_file_path)
                self.config_data = json.load(config_file)
                config_file.close()
            except Exception as error:
                self._print_log_error(f"读取声线配置文件\"{self.config_file_path}\"发生异常:\n{error}")
                return False
            return True
        return False

    def _write_config_data(self) -> bool:
        try:
            self.config_data = dict(sorted(self.config_data.items(), key=lambda item: item[0]))
            config_file = open(self.config_file_path, "w")
            json.dump(self.config_data, config_file, indent=4)
            config_file.close()
        except Exception as error:
            self._print_log_error(f"写入声线配置文件\"{self.config_file_path}\"发生异常:\n{error}")
            return False
        return True

    def _print_log_error(self, log: str):
        print(f"[{self.__class__.__name__}][Error] {log}")


tts_config_utility = TTSConfigUtility()
'''