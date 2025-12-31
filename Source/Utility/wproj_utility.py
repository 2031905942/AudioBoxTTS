import os
import re
import uuid
from pathlib import Path, PurePosixPath
from typing import Optional

from lxml.etree import Element
from PySide6.QtCore import Signal

import jellyfish
import main
from Source.Utility.config_utility import config_utility, ConfigUtility, ProjectData
from Source.Utility.file_utility import FileUtility
from Source.Utility.xml_utility import XmlUtility

ACTOR_MIXER_HIERARCHY = "Actor-Mixer Hierarchy"
INTERACTIVE_MUSIC_HIERARCHY = "Interactive Music Hierarchy"
EVENTS = "Events"
IMPORT_CHARACTER_TYPE_LIST = ["BO", "CH", "HO", "MON", "VEH"]
IMPORT_CHARACTER_TYPE_DICT = {
    "BO":  "Boss",
    "CH":  "Character",
    "HO":  "Hero",
    "MON": "Monster",
    "VEH": "Vehicle",
    "VO":  "Story"
}
CUSTOM_IMPORT_CHARACTER_TYPE_DICT = {}
IMPORT_STORY_VOICE_TYPE_LIST = ["VO"]
IMPORT_SAMPLE_TYPE_LIST = IMPORT_CHARACTER_TYPE_LIST + IMPORT_STORY_VOICE_TYPE_LIST
IMPORT_CONTAINER_TYPE_LIST = ["BL", "RD", "SQ", "SW"]


class WorkUnitInfo:
    def __init__(self):
        self.element: Optional[Element] = None
        self.work_unit_type: Optional[str] = None
        self.file_path: Optional[str] = None
        self.parent_work_unit_id: Optional[str] = None
        self.path_to_parent_work_unit: Optional[str] = None
        self.modified: bool = False


class ElementInfo:
    def __init__(self):
        self.work_unit_id: Optional[str] = None
        self.parent_element: Optional[Element] = None


class WwiseObjectInfo:
    def __init__(self):
        self.element_list: list[Element] = []


class AudioFileInfo:
    def __init__(self):
        self.language: Optional[str] = None
        self.audio_file_source_elements: Optional[set[Element]] = None
        self.plugin_media_source_elements: Optional[set[Element]] = None
        self.plugin_name: Optional[str] = None
        self.ideal_audio_file_path: Optional[str] = None
        self.temp_audio_file_path: Optional[str] = None
        self.work_unit_type: Optional[str] = None


class WprojUtility(XmlUtility, FileUtility):
    # 信号定义
    show_wwise_object_check_window_signal = Signal(str, list)
    show_check_window_signal = Signal(str, list)
    validate_import_sample_name_succeeded_signal = Signal(str)
    """ 验证入库的素材的命名成功的信号 """

    def __init__(self, base_job):
        super().__init__(base_job)

        from Source.Job.wproj_job import WprojJob
        self._wproj_job: WprojJob = base_job

        self.wwise_project_dir_path: Optional[str] = None

        self.wwise_project_originals_dir_path: Optional[str] = None

        self.wwise_project_sfx_dir_path: Optional[str] = None

        self.wwise_project_voice_dir_path: Optional[str] = None

        self.wwise_project_plugin_dir_path: Optional[str] = None

        self.wwise_object_info_dict: dict[str, WwiseObjectInfo] = {}
        """ Wwise对象信息字典 """

        self.element_info_dict: dict[Element, ElementInfo] = {}
        """ 元素信息字典 """

        self.work_unit_info_dict: dict[str, WorkUnitInfo] = {}
        """ 工作单元信息字典 """

        self.audio_file_info_dict: dict[str, AudioFileInfo] = {}
        """ 音频文件信息字典 """

    def read_wwise_project_file(self, file_path: str) -> Element | None:
        if not file_path:
            self.error_signal.emit("读取Wwise工程文件失败, 路径为空.")
            return None
        if not os.path.isfile(file_path):
            self.error_signal.emit(f"读取Wwise工程文件失败, 路径不合法:\n\"{file_path}\".")
            return None
        root_element = self.read_xml(file_path)
        return root_element

    @staticmethod
    def is_wwise_project_valid(project_id: str | None) -> bool:
        if not project_id:
            return False
        project_data: dict[str, str] = config_utility.get_project_data(project_id)
        wwise_project_path: str = project_data.get(ProjectData.WWISE_PROJECT_PATH)
        if wwise_project_path and os.path.isfile(wwise_project_path):
            return True
        return False

    @staticmethod
    def get_wwise_version(wproj_root_element: Element) -> str | None:
        if wproj_root_element is None:
            return None
        wwise_version = wproj_root_element.get("WwiseVersion")
        if wwise_version:
            wwise_version = re.sub("[^0-9.]+", "", wwise_version)
        return wwise_version

    @staticmethod
    def _get_settings_user_override(wsettings: Optional[Element]) -> bool:
        if wsettings is None:
            return False
        settings_user_override_property = wsettings.find("./UserProjectSettingsInfo/UserProjectSettings/PropertyList/Property[@Name='SettingsUserOverride']")
        return settings_user_override_property is not None and settings_user_override_property.attrib.get("Value", False)

    @staticmethod
    def get_platform_list(wproj_root_element: Element) -> list[str]:
        platform_list: list[str] = []
        if not wproj_root_element:
            return platform_list
        platform_element_list: list[Element] = wproj_root_element.findall("./ProjectInfo/Project/Platforms/Platform")
        if platform_element_list:
            for platform_element in platform_element_list:
                platform: str = platform_element.get("Name")
                platform_list.append(platform)
            platform_list.sort()
        return platform_list

    @staticmethod
    def get_language_list(wproj_root_element: Element) -> list[str]:
        language_list: list[str] = []
        if wproj_root_element is None:
            return language_list
        language_element_list: list[Element] = wproj_root_element.findall("./ProjectInfo/Project/LanguageList/Language")
        if language_element_list:
            for language_element in language_element_list:
                language: str = language_element.get("Name")
                if language and language != "SFX" and language != "External" and language != "Mixed":
                    language_list.append(language)
            language_list.sort()
        return language_list

    @staticmethod
    def get_reference_language(wproj_root_element: Element) -> str:
        reference_language: Optional[str] = None
        if not wproj_root_element:
            return reference_language
        reference_language_element: Optional[Element] = wproj_root_element.find(
                "./ProjectInfo/Project/PropertyList/Property[@Name='DefaultLanguage']")
        # reference_language_element: Optional[Element] = wproj_root_element.find(
        #         "./ProjectInfo/Project/SharedValues/SharedPropertyList[@ClassName='Project']/PropertyList/Property[@Name='DefaultLanguage']/ValueList/Value")
        if reference_language_element is not None:
            reference_language = reference_language_element.get("Value")
        return reference_language

    def get_generate_all_banks_metadata_file(self, project_id) -> Optional[bool]:
        wproj_file_path = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wsettings_file_path = Path(wproj_file_path).with_suffix(f".{main.get_current_user_name()}.wsettings")
        if os.path.isfile(wsettings_file_path):
            wsettings = self.read_wwise_project_file(str(wsettings_file_path))
            if WprojUtility._get_settings_user_override(wsettings):
                generate_main_soundbank_property = wsettings.find("./UserProjectSettingsInfo/UserProjectSettings/PropertyList/Property[@Name='GenerateMainSoundBank']")
                return generate_main_soundbank_property is None or generate_main_soundbank_property.attrib.get("Value", "True") == "True"

        if not os.path.isfile(wproj_file_path):
            return None
        wproj = self.read_wwise_project_file(wproj_file_path)
        if wproj is None:
            return None
        generate_main_soundbank_property = wproj.find("./ProjectInfo/Project/PropertyList/Property[@Name='GenerateMainSoundBank']")
        return generate_main_soundbank_property is None or generate_main_soundbank_property.attrib.get("Value", "True") == "True"

    def get_generate_per_banks_metadata_file(self, project_id) -> Optional[bool]:
        wproj_file_path = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wsettings_file_path = Path(wproj_file_path).with_suffix(f".{main.get_current_user_name()}.wsettings")
        if os.path.isfile(wsettings_file_path):
            wsettings = self.read_wwise_project_file(str(wsettings_file_path))
            if WprojUtility._get_settings_user_override(wsettings):
                generate_multiple_banks_property = wsettings.find("./UserProjectSettingsInfo/UserProjectSettings/PropertyList/Property[@Name='GenerateMultipleBanks']")
                return generate_multiple_banks_property is not None and generate_multiple_banks_property.attrib.get("Value", "False") == "True"

        if not os.path.isfile(wproj_file_path):
            return None
        wproj = self.read_wwise_project_file(wproj_file_path)
        if wproj is None:
            return None
        generate_multiple_banks_property = wproj.find("./ProjectInfo/Project/PropertyList/Property[@Name='GenerateMultipleBanks']")
        return generate_multiple_banks_property is not None and generate_multiple_banks_property.attrib.get("Value", "False") == "True"

    def get_generate_xml_metadata(self, project_id) -> Optional[bool]:
        wproj_file_path = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wsettings_file_path = Path(wproj_file_path).with_suffix(f".{main.get_current_user_name()}.wsettings")
        if os.path.isfile(wsettings_file_path):
            wsettings = self.read_wwise_project_file(str(wsettings_file_path))
            if WprojUtility._get_settings_user_override(wsettings):
                generate_soundbank_xml_property = wsettings.find("./UserProjectSettingsInfo/UserProjectSettings/PropertyList/Property[@Name='GenerateSoundBankXML']")
                return generate_soundbank_xml_property is None or generate_soundbank_xml_property.attrib.get("Value", "True") == "True"

        if not os.path.isfile(wproj_file_path):
            return None
        wproj = self.read_wwise_project_file(wproj_file_path)
        if wproj is None:
            return None
        generate_soundbank_xml_property = wproj.find("./ProjectInfo/Project/PropertyList/Property[@Name='GenerateSoundBankXML']")
        return generate_soundbank_xml_property is None or generate_soundbank_xml_property.attrib.get("Value", "True") == "True"

    def get_generate_json_metadata(self, project_id) -> Optional[bool]:
        wproj_file_path = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wsettings_file_path = Path(wproj_file_path).with_suffix(f".{main.get_current_user_name()}.wsettings")
        if os.path.isfile(wsettings_file_path):
            wsettings = self.read_wwise_project_file(str(wsettings_file_path))
            if WprojUtility._get_settings_user_override(wsettings):
                generate_soundbank_json_property = wsettings.find("./UserProjectSettingsInfo/UserProjectSettings/PropertyList/Property[@Name='GenerateSoundBankJSON']")
                return generate_soundbank_json_property is not None and generate_soundbank_json_property.attrib.get("Value", "False") == "True"

        if not os.path.isfile(wproj_file_path):
            return None
        wproj = self.read_wwise_project_file(wproj_file_path)
        if wproj is None:
            return None
        generate_soundbank_json_property = wproj.find("./ProjectInfo/Project/PropertyList/Property[@Name='GenerateSoundBankJSON']")
        return generate_soundbank_json_property is not None and generate_soundbank_json_property.attrib.get("Value", "False") == "True"

    @staticmethod
    def get_original_sample_path(wproj_root_element: Element) -> str:
        path = ""
        if wproj_root_element is None:
            return path
        misc_setting_entry_element: Element | None = wproj_root_element.find("./ProjectInfo/Project/MiscSettings/MiscSettingEntry[@Name='Originals']")
        if misc_setting_entry_element is not None:
            path = misc_setting_entry_element.text
        return path

    @staticmethod
    def get_soundbank_path_list(wproj_root_element: Element) -> list[str]:
        path_list: list[str] = []
        if wproj_root_element is None:
            return path_list
        element_list: list[Element] = wproj_root_element.findall("./ProjectInfo/Project/PropertyList/Property[@Name='SoundBankPaths']/ValueList/Value")
        if element_list:
            for element in element_list:
                path: str = element.text
                path = path.replace("\\", "/")
                if path.endswith("/"):
                    path = path[0:-1]
                path_list.append(path)
            path_list.sort()
        return path_list

    def sync_original_dir_structure_job(self, project_id: str):
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wproj_root_element: Element = self.read_wwise_project_file(wwise_project_path)
        original_dir_path: str = WprojUtility.get_original_sample_path(wproj_root_element)
        if not original_dir_path:
            original_dir_path = "Originals"
        wwise_project_dir_path: str = os.path.dirname(wwise_project_path)
        self.wwise_project_dir_path = wwise_project_dir_path
        wwise_project_originals_dir_path: str = f"{wwise_project_dir_path}/{original_dir_path}"
        self.wwise_project_originals_dir_path = wwise_project_originals_dir_path

        wwise_project_sfx_dir_path: str = f"{wwise_project_originals_dir_path}/SFX"
        self.wwise_project_sfx_dir_path = wwise_project_sfx_dir_path

        wwise_project_voice_dir_path = f"{wwise_project_originals_dir_path}/Voices"
        self.wwise_project_voice_dir_path = wwise_project_voice_dir_path

        self.wwise_project_plugin_dir_path = f"{wwise_project_originals_dir_path}/Plugins"

        element_info_dict = self.element_info_dict
        element_info_dict.clear()
        wwise_object_info_dict = self.wwise_object_info_dict
        wwise_object_info_dict.clear()
        work_unit_info_dict = self.work_unit_info_dict
        work_unit_info_dict.clear()
        audio_file_info_dict = self.audio_file_info_dict
        audio_file_info_dict.clear()

        work_unit_dir_name_list = [ACTOR_MIXER_HIERARCHY, INTERACTIVE_MUSIC_HIERARCHY, EVENTS]

        actor_mixer_format_tag_list = ["ActorMixer", "Folder", "PluginMediaSource", "RandomSequenceContainer", "SwitchContainer", "Sound"]
        actor_mixer_reference_object_tag_list = ("AudioFileSource", "ActiveSource", "PluginMediaSource")

        interactive_music_format_tag_list = ["AudioFileSource", "AudioSourceRef", "Folder", "MusicPlaylistContainer", "MusicSwitchContainer", "MusicClip", "MusicTrack", "MusicSegment"]
        interactive_music_reference_object_tag_list = ("AudioSourceRef", "AudioNodeRef", "ObjectRef", "SegmentRef")

        work_unit_path_list: list[str] = []
        for work_unit_dir_name in work_unit_dir_name_list:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            work_unit_dir_path = f"{wwise_project_dir_path}/{work_unit_dir_name}"
            self.update_progress_text_signal.emit(f"收集工作单元...\n\"{work_unit_dir_name}\"")
            work_unit_path_list += self.get_files(work_unit_dir_path, [".wwu"])

        total_count = len(work_unit_path_list)
        self.update_progress_total_count_signal.emit(total_count)
        current_count = 0
        self.update_progress_current_count_signal.emit(current_count)
        for work_unit_path in work_unit_path_list:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            self.update_progress_text_signal.emit(f"读取工作单元...\n\"{os.path.basename(work_unit_path)}\"")
            wwise_document_element = self.read_xml(work_unit_path)
            work_unit_id: str = wwise_document_element.get("ID")

            if work_unit_path.startswith(f"{wwise_project_dir_path}/{ACTOR_MIXER_HIERARCHY}"):
                work_unit_type = ACTOR_MIXER_HIERARCHY
            elif work_unit_path.startswith(f"{wwise_project_dir_path}/{INTERACTIVE_MUSIC_HIERARCHY}"):
                work_unit_type = INTERACTIVE_MUSIC_HIERARCHY
            else:
                work_unit_type = EVENTS

            # 更新元素信息字典和Wwise对象信息字典
            element_iter = wwise_document_element.iter()
            for element in element_iter:
                for child_element in element:
                    if self.cancel_job:
                        self.finish_signal.emit("任务中止", "", "warning")
                        return
                    element_info_dict[child_element] = ElementInfo()
                    element_info_dict[child_element].parent_element = element
                    element_info_dict[child_element].work_unit_id = work_unit_id
                    if (work_unit_type == ACTOR_MIXER_HIERARCHY and (child_element.tag in actor_mixer_format_tag_list or child_element.tag in actor_mixer_reference_object_tag_list)) or (
                            work_unit_type == INTERACTIVE_MUSIC_HIERARCHY and (
                            child_element.tag in interactive_music_format_tag_list or child_element.tag in interactive_music_reference_object_tag_list)) or (
                            work_unit_type == EVENTS and child_element.tag == "ObjectRef"):
                        element_id = child_element.get("ID")
                        if element_id not in wwise_object_info_dict.keys():
                            wwise_object_info_dict[element_id] = WwiseObjectInfo()
                        wwise_object_info = wwise_object_info_dict[element_id]
                        if child_element not in wwise_object_info.element_list:
                            wwise_object_info.element_list.append(child_element)

            self._update_work_unit_info_dict(work_unit_path, wwise_document_element)
            current_count += 1
            self.update_progress_current_count_signal.emit(current_count)

        actor_mixer_path_tag_list = ["ActorMixer", "Folder", "RandomSequenceContainer", "SwitchContainer"]
        interactive_music_path_tag_list = ["Folder", "MusicPlaylistContainer", "MusicSwitchContainer"]

        current_count = 0
        self.update_progress_current_count_signal.emit(current_count)
        for work_unit_info in work_unit_info_dict.values():
            if self.cancel_job:
                self._write_work_unit(True)
                return
            file_path = work_unit_info.file_path
            wwise_document_element = work_unit_info.element
            work_unit_type = work_unit_info.work_unit_type
            if work_unit_type == EVENTS:
                current_count += 1
                self.update_progress_current_count_signal.emit(current_count)
                continue

            if work_unit_type == ACTOR_MIXER_HIERARCHY:
                allow_underscore = True
                format_tag_list = actor_mixer_format_tag_list
                path_tag_list = actor_mixer_path_tag_list
            else:
                allow_underscore = False
                format_tag_list = interactive_music_format_tag_list
                path_tag_list = interactive_music_path_tag_list

            self.update_progress_text_signal.emit(f"格式化Wwise对象...\n\"{os.path.basename(file_path)}\"")
            self._format_specific_tag_element_name(wwise_document_element, format_tag_list, allow_underscore)

            if self.cancel_job:
                self._write_work_unit(True)
                return

            self.update_progress_text_signal.emit(f"计算引用工作单元路径...\n\"{os.path.basename(file_path)}\"")
            self._calculate_reference_work_unit_path(wwise_document_element, path_tag_list)

            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return

            self.update_progress_text_signal.emit(f"收集音频文件路径...\n\"{os.path.basename(file_path)}\"")
            self._collect_audio_file_path(wwise_document_element, work_unit_type)

            current_count += 1
            self.update_progress_current_count_signal.emit(current_count)

        total_count = len(audio_file_info_dict.keys())
        self.update_progress_total_count_signal.emit(total_count)
        current_count = 0
        self.update_progress_current_count_signal.emit(current_count)
        for audio_file_path, audio_file_info in audio_file_info_dict.items():
            self.update_progress_text_signal.emit(f"计算音频文件理想命名与路径...\n\"{os.path.basename(audio_file_path)}\"")
            audio_file_name = Path(audio_file_path).stem
            audio_file_dir_path = str(PurePosixPath(audio_file_path).parent)
            audio_file_extension = Path(audio_file_path).suffix
            audio_file_source_elements = audio_file_info.audio_file_source_elements
            is_audio_file_source = audio_file_source_elements is not None
            plugin_media_source_elements = audio_file_info.plugin_media_source_elements
            is_plugin_media_source = plugin_media_source_elements is not None
            language = audio_file_info.language
            work_unit_type = audio_file_info.work_unit_type
            ideal_audio_file_name = ""
            ideal_audio_file_dir_path = ""

            # 得出音频文件的理想命名并直接对引用其的AudioFileSource的命名与音频文件的理想命名做同步
            if is_audio_file_source:
                if len(audio_file_source_elements) == 1:
                    # 如果只有唯一的AudioFileSource对象引用, 直接使用其名字作为理想的文件命名
                    audio_file_source_element = next(iter(audio_file_source_elements))
                    audio_file_source_name = audio_file_source_element.get("Name")
                    if work_unit_type == ACTOR_MIXER_HIERARCHY:
                        sound_element = self._get_audio_file_source_sound_element(audio_file_source_element)
                        sound_name = sound_element.get("Name")
                        audio_file_source_list = self._get_children_list_from_sound_element(sound_element, language)
                        if self._is_audio_file_source_active_source(audio_file_source_element):
                            # 如果AudioFileSource是激活对象, 可直接将这个AudioFileSource的命名设置成所属Sound对象的命名
                            ideal_audio_file_name = sound_name
                        elif len(audio_file_source_list) == 2:
                            # 如果AudioFileSource不是激活对象, 且某语言下的子对象有两个, 可直接将这个AudioFileSource的命名设置成所属Sound对象的命名+" (备用)"
                            ideal_audio_file_name = f"{sound_name} (备用)"
                        else:
                            # 如果AudioFileSource不是激活对象, 且某语言下的子对象多于两个, 则需要不断确认备用的命名是否被占用, 找出未被占用的命名并使用
                            audio_file_source_name_list = [x.get("Name") for x in audio_file_source_list]

                            index = 0
                            ideal_audio_file_name = f"{sound_name} (备用-{index})"
                            while audio_file_source_name != ideal_audio_file_name and ideal_audio_file_name in audio_file_source_name_list:
                                index += 1
                                ideal_audio_file_name = f"{sound_name} (备用-{index})"
                    else:
                        ideal_audio_file_name = audio_file_source_name
                else:
                    # 如果有多个AudioFileSource对象引用, 要比较当前音频文件名与各个AudioFileSource名字的相似度(使用Damerau–Levenshtein Distance算法), 采用相似度最高的名字作为理想的文件命名
                    greatest_audio_file_name_similarity: float = 1
                    for audio_file_source_element in audio_file_source_elements:
                        audio_file_source_name = audio_file_source_element.get("Name")
                        if work_unit_type == ACTOR_MIXER_HIERARCHY:
                            sound_element = self._get_audio_file_source_sound_element(audio_file_source_element)
                            sound_name = sound_element.get("Name")
                            audio_file_source_list = self._get_children_list_from_sound_element(sound_element, language)
                            if self._is_audio_file_source_active_source(audio_file_source_element):
                                # 如果AudioFileSource是激活对象, 可直接将这个AudioFileSource的命名设置成所属Sound对象的命名
                                current_ideal_audio_file_name = sound_name
                            elif len(audio_file_source_list) == 2:
                                # 如果AudioFileSource不是激活对象, 且某语言下的子对象有两个, 可直接将这个AudioFileSource的命名设置成所属Sound对象的命名+" (备用)"
                                current_ideal_audio_file_name = f"{sound_name} (备用)"
                            else:
                                # 如果AudioFileSource不是激活对象, 且某语言下的子对象多于两个, 则需要不断确认备用的命名是否被占用, 找出未被占用的命名并使用
                                audio_file_source_name_list = [x.get("Name") for x in audio_file_source_list]
                                index = 0
                                current_ideal_audio_file_name = f"{sound_name} (备用-{index})"
                                while audio_file_source_name != current_ideal_audio_file_name and current_ideal_audio_file_name in audio_file_source_name_list:
                                    index += 1
                                    current_ideal_audio_file_name = f"{sound_name} (备用-{index})"
                        else:
                            current_ideal_audio_file_name = audio_file_source_name
                        edit_time = jellyfish.damerau_levenshtein_distance(current_ideal_audio_file_name, audio_file_name)
                        audio_file_name_similarity = edit_time / max(len(current_ideal_audio_file_name), len(audio_file_name))
                        if audio_file_name_similarity < greatest_audio_file_name_similarity:
                            ideal_audio_file_name = current_ideal_audio_file_name
                            greatest_audio_file_name_similarity = audio_file_name_similarity
                ideal_audio_file_source_object_name = ideal_audio_file_name
                if language != "SFX":
                    if "(备用" in ideal_audio_file_source_object_name:
                        insert_index = ideal_audio_file_source_object_name.index("(备用")
                        ideal_audio_file_source_object_name = f"{ideal_audio_file_source_object_name[:insert_index]} ({language}) {ideal_audio_file_source_object_name[insert_index:]}"
                    else:
                        ideal_audio_file_source_object_name = f"{ideal_audio_file_source_object_name} ({language})"

                # 得出音频文件的理想命名后, 可直接对所有引用的AudioFileSource对象做命名同步了
                for audio_file_source_element in audio_file_source_elements:
                    audio_file_source_id = audio_file_source_element.get("ID")
                    audio_file_source_name = audio_file_source_element.get("Name")
                    if audio_file_source_name != ideal_audio_file_source_object_name and work_unit_type != INTERACTIVE_MUSIC_HIERARCHY:
                        audio_file_source_element.set("Name", ideal_audio_file_source_object_name)
                        self._sync_all_reference_element_name(audio_file_source_element)
                        # if work_unit_type == INTERACTIVE_MUSIC_HIERARCHY:
                        #     for element in wwise_object_info_dict[audio_file_source_id].element_list:
                        #         if element.tag != "AudioSourceRef":
                        #             continue
                        #         # 如果引用音频文件的音乐片段的名字与音频文件的名字不一样, 则使用音频文件的名字作为音乐片段的名字
                        #         self._sync_music_clip_name_to_audio_source_ref_name(element)
                    if work_unit_type == INTERACTIVE_MUSIC_HIERARCHY:
                        # 如果音乐轨道里只有一个音频文件引用, 则使用其名字作为轨道名字
                        music_track_element = self._get_parent_element(self._get_parent_element(audio_file_source_element))
                        self._sync_music_track_name_to_audio_file_source_name(music_track_element)

                        # 如果音乐里只有一个音频轨道, 则使用其名字作为音乐名字
                        music_segment_element: Element = self._get_parent_element(self._get_parent_element(music_track_element))
                        self._sync_music_segment_name_to_music_track_name(music_segment_element)
            # 对于PluginMediaSource的音频文件名, 当前命名就是理想命名, 保持不变, 仅作格式化
            elif is_plugin_media_source:
                ideal_audio_file_name = audio_file_name

            # 得出音频文件的理想路径
            if work_unit_type == ACTOR_MIXER_HIERARCHY:
                path_tag_list = actor_mixer_path_tag_list.copy()
                if is_plugin_media_source:
                    path_tag_list.append("Sound")
            else:
                path_tag_list = interactive_music_path_tag_list
            ideal_audio_file_name_split = set(ideal_audio_file_name.split(" "))
            largest_intersect = -1
            if is_audio_file_source:
                for audio_file_source_element in audio_file_source_elements:
                    current_audio_file_dir_path = ""
                    recursive_element = audio_file_source_element
                    while recursive_element in element_info_dict.keys():
                        parent_element = element_info_dict[recursive_element].parent_element
                        if parent_element.tag in path_tag_list:
                            parent_element_name = parent_element.get("Name")
                            current_audio_file_dir_path = f"{parent_element_name}/{current_audio_file_dir_path}"
                        elif parent_element.tag == "WorkUnit":
                            break
                        recursive_element = parent_element

                    work_unit_id = element_info_dict[audio_file_source_element].work_unit_id
                    work_unit_info = work_unit_info_dict[work_unit_id]
                    if work_unit_info.path_to_parent_work_unit:
                        current_audio_file_dir_path = f"{work_unit_info.path_to_parent_work_unit}/{current_audio_file_dir_path}"

                    while work_unit_info.parent_work_unit_id:
                        work_unit_info = work_unit_info_dict[work_unit_info.parent_work_unit_id]
                        if work_unit_info.path_to_parent_work_unit:
                            current_audio_file_dir_path = f"{work_unit_info.path_to_parent_work_unit}/{current_audio_file_dir_path}"

                    current_audio_file_dir_path = current_audio_file_dir_path[:-1]
                    if work_unit_type == INTERACTIVE_MUSIC_HIERARCHY:
                        current_audio_file_dir_path = f"BGM/{current_audio_file_dir_path}"
                    current_audio_file_dir_path_split = set(current_audio_file_dir_path.split("/"))
                    current_intersect = len(ideal_audio_file_name_split.intersection(current_audio_file_dir_path_split))
                    if current_intersect > largest_intersect:
                        ideal_audio_file_dir_path = current_audio_file_dir_path
                        largest_intersect = current_intersect
                    elif current_intersect == largest_intersect and audio_file_dir_path.endswith(current_audio_file_dir_path):
                        ideal_audio_file_dir_path = current_audio_file_dir_path

            elif is_plugin_media_source:
                for plugin_media_source_element in plugin_media_source_elements:
                    current_audio_file_dir_path = ""
                    recursive_element = plugin_media_source_element
                    while recursive_element in element_info_dict.keys():
                        parent_element = element_info_dict[recursive_element].parent_element
                        if parent_element.tag in path_tag_list:
                            parent_element_name = parent_element.get("Name")
                            current_audio_file_dir_path = f"{parent_element_name}/{current_audio_file_dir_path}"
                        elif parent_element.tag == "WorkUnit":
                            break
                        recursive_element = parent_element

                    work_unit_id = element_info_dict[plugin_media_source_element].work_unit_id
                    work_unit_info = work_unit_info_dict[work_unit_id]
                    if work_unit_info.path_to_parent_work_unit:
                        current_audio_file_dir_path = f"{work_unit_info.path_to_parent_work_unit}/{current_audio_file_dir_path}"

                    while work_unit_info.parent_work_unit_id:
                        work_unit_info = work_unit_info_dict[work_unit_info.parent_work_unit_id]
                        if work_unit_info.path_to_parent_work_unit:
                            current_audio_file_dir_path = f"{work_unit_info.path_to_parent_work_unit}/{current_audio_file_dir_path}"

                    current_audio_file_dir_path = current_audio_file_dir_path[:-1]
                    current_audio_file_dir_path_split = set(current_audio_file_dir_path.split("/"))
                    current_intersect = len(ideal_audio_file_name_split.intersection(current_audio_file_dir_path_split))
                    if current_intersect > largest_intersect:
                        ideal_audio_file_dir_path = current_audio_file_dir_path
                        largest_intersect = current_intersect

            ideal_audio_file_path = f"{ideal_audio_file_dir_path}/{ideal_audio_file_name}{audio_file_extension}"
            if audio_file_info.language == "SFX":
                if is_audio_file_source:
                    ideal_audio_file_path = f"{wwise_project_sfx_dir_path}/{ideal_audio_file_path}"
                elif is_plugin_media_source:
                    ideal_audio_file_path = f"{self.wwise_project_plugin_dir_path}/{audio_file_info.plugin_name}/{ideal_audio_file_path}"
            else:
                ideal_audio_file_path = f"{wwise_project_voice_dir_path}/{language}/{ideal_audio_file_path}"
            audio_file_info.ideal_audio_file_path = ideal_audio_file_path

            if audio_file_path != ideal_audio_file_path:
                # 得出音频文件的理想路径后, 如果与现有的音频文件路径不同, 则先将这些音频文件重命名成不重复的哈希值并移动到一个临时的地方, 防止后续的整理可能出现的重名冲突或文件系统大小写不区分造成的冲突
                self._temp_move_audio_file(audio_file_path, audio_file_info)

            current_count += 1
            self.update_progress_current_count_signal.emit(current_count)

        self.update_progress_text_signal.emit(f"整理音频文件...")
        self._sync_audio_file(audio_file_info_dict)

        self._write_work_unit()

    def clean_akd_file_job(self, project_id: str):
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wproj_root_element: Element = self.read_wwise_project_file(wwise_project_path)
        original_dir_path: str = WprojUtility.get_original_sample_path(wproj_root_element)
        if not original_dir_path:
            original_dir_path = "Originals"
        wwise_project_dir_path: str = os.path.dirname(wwise_project_path)
        wwise_project_originals_dir_path: str = f"{wwise_project_dir_path}/{original_dir_path}"

        if self.cancel_job:
            self.finish_signal.emit("任务中止", "", "warning")
            return

        self.update_progress_text_signal.emit("收集文件...")
        file_path_list: list[str] = self.get_files(wwise_project_originals_dir_path, [".wav", ".akd"])

        if self.cancel_job:
            self.finish_signal.emit("任务中止", "", "warning")
            return

        wav_id_path_set: set[str] = set([x[:-4] for x in file_path_list if x.endswith(".wav")])
        akd_id_path_set: set[str] = set([x[:-4] for x in file_path_list if x.endswith(".akd")])
        delete_akd_id_path_set: set[str] = akd_id_path_set - wav_id_path_set
        delete_count: int = 0
        for delete_akd_id_path in delete_akd_id_path_set:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return

            delete_akd_path = f"{delete_akd_id_path}.akd"
            self.update_progress_text_signal.emit(f"删除文件...\n\"{os.path.basename(delete_akd_path)}\"")

            if not self.delete_file(delete_akd_path):
                self.finish_signal.emit("结果", "任务中止", "error")
                return

            delete_count += 1

        self._remove_originals_empty_directory(wwise_project_originals_dir_path)

        result_content_str: str = f"清理Akd文件完成"
        if delete_count > 0:
            result_content_str += f"\n清理了{delete_count}个文件"
        else:
            result_content_str += f"\n没有变动"

        self.finish_signal.emit("结果", result_content_str, "success")

    def clean_unused_sample_job(self, project_id: str):
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wproj_root_element: Element = self.read_wwise_project_file(wwise_project_path)
        original_dir_path: str = WprojUtility.get_original_sample_path(wproj_root_element)
        if not original_dir_path:
            original_dir_path = "Originals"
        wwise_project_dir_path: str = os.path.dirname(wwise_project_path)
        wwise_project_originals_dir_path: str = f"{wwise_project_dir_path}/{original_dir_path}"

        if self.cancel_job:
            self.finish_signal.emit("任务中止", "", "warning")
            return

        actor_mixer_hierarchy_dir_path: str = f"{wwise_project_dir_path}/{ACTOR_MIXER_HIERARCHY}"
        interactive_music_hierarchy_dir_path: str = f"{wwise_project_dir_path}/{INTERACTIVE_MUSIC_HIERARCHY}"
        self.update_progress_text_signal.emit("收集工作单元...")
        wwu_path_list: list[str] = self.get_files(actor_mixer_hierarchy_dir_path, [".wwu"])
        wwu_path_list += self.get_files(interactive_music_hierarchy_dir_path, [".wwu"])

        used_sample_path_list: list[str] = []
        for wwu_path in wwu_path_list:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            self.update_progress_text_signal.emit(f"读取工作单元...\n\"{os.path.basename(wwu_path)}\"")
            wwu_root_element = self.read_xml(wwu_path)
            if wwu_root_element is None:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            audio_file_source_element_list: list[Element] = wwu_root_element.findall(".//AudioFileSource")
            for audio_file_source_element in audio_file_source_element_list:
                audio_file_source_element: Element
                language: str = audio_file_source_element.find("Language").text
                audio_file_path = audio_file_source_element.find("AudioFile").text
                audio_file_path = audio_file_path.replace("\\", "/")

                if language == "SFX":
                    audio_file_path = f"{wwise_project_originals_dir_path}/SFX/{audio_file_path}"
                else:
                    audio_file_path = f"{wwise_project_originals_dir_path}/Voices/{language}/{audio_file_path}"
                audio_file_path = audio_file_path.lower()
                if audio_file_path not in used_sample_path_list:
                    used_sample_path_list.append(audio_file_path)

            plugin_media_source_elements = wwu_root_element.findall(".//PluginMediaSource")
            for plugin_media_source_element in plugin_media_source_elements:
                source_plugin_element = plugin_media_source_element.getparent().getparent()
                plugin_name = source_plugin_element.get("PluginName")
                relative_path = plugin_media_source_element.find("./PropertyList/Property[@Name='DataFileName']").get("Value")
                audio_file_path = Path(f"{wwise_project_originals_dir_path}/Plugins/{plugin_name}/{relative_path}")
                audio_file_path_str = audio_file_path.as_posix().lower()
                if audio_file_path_str not in used_sample_path_list:
                    used_sample_path_list.append(audio_file_path_str)

        if self.cancel_job:
            self.finish_signal.emit("任务中止", "", "warning")
            return

        self.update_progress_text_signal.emit("收集素材...")
        exist_sample_path_list: list[str] = self.get_files(wwise_project_originals_dir_path, [".wav"])
        exist_sample_path_list = [x.lower() for x in exist_sample_path_list if not x.startswith(f"{wwise_project_originals_dir_path}/ExternalSource/")]

        if self.cancel_job:
            self.finish_signal.emit("任务中止", "", "warning")
            return

        used_sample_path_set: set[str] = set(used_sample_path_list)
        exist_sample_path_set: set[str] = set(exist_sample_path_list)

        delete_sample_path_set: set[str] = exist_sample_path_set - used_sample_path_set

        delete_count: int = 0
        for delete_sample_path in delete_sample_path_set:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return

            delete_sample_akd_path = f"{delete_sample_path[:-3]}akd"
            self.update_progress_text_signal.emit(f"删除无用素材...\n\"{os.path.basename(delete_sample_path)}\"")

            if not self.delete_file(delete_sample_path):
                self.finish_signal.emit("结果", "任务中止", "error")
                return

            if Path(delete_sample_akd_path).is_file():
                if not self.delete_file(delete_sample_akd_path):
                    self.finish_signal.emit("结果", "任务中止", "error")
                    return

            delete_count += 1

        self._remove_originals_empty_directory(wwise_project_originals_dir_path)

        result_content_str: str = f"清理无用素材完成"
        if delete_count > 0:
            result_content_str += f"\n清理了{delete_count}个素材"
        else:
            result_content_str += f"\n没有变动"

        self.finish_signal.emit("结果", result_content_str, "success")

    '''
    def sync_external_source_list(self, project_id: str):
        self.update_progress_text_signal.emit(f"刷新外部源列表...")
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wwise_project_dir_path = os.path.dirname(wwise_project_path)
        wproj_root_element: Element = self.read_wproj_file(wwise_project_path)
        original_dir_path: str = WprojUtility.get_original_sample_path(wproj_root_element)
        if not original_dir_path:
            original_dir_path = "Originals"
        external_source_dir_path = f"{wwise_project_dir_path}/{original_dir_path}/ExternalSource"
        audio_path_list = self.get_files(external_source_dir_path, [".wav"])
        audio_path_list.sort()

        generated_soundbank_dir_path = f"{wwise_project_dir_path}/GeneratedSoundBanks"
        external_source_list_file_name = "ExternalSourceList.xml"
        external_source_list_path = f"{generated_soundbank_dir_path}/{external_source_list_file_name}"
        if not os.path.isfile(external_source_list_path):
            external_source_list_root_element = Element("ExternalSourcesList", {
                "SchemaVersion": "1",
                "Root":          f"./{original_dir_path}/ExternalSource"
            })
            self.write_wwise_xml(external_source_list_root_element, external_source_list_path)
        external_source_list_root_element = self.read_xml(external_source_list_path)

        source_element_list = external_source_list_root_element.findall("Source")
        for source_element in source_element_list:
            external_source_list_root_element.remove(source_element)
        for audio_path in audio_path_list:
            relative_audio_path = audio_path[len(external_source_dir_path) + 1:]
            source_element = Element("Source", {
                "Path":          relative_audio_path,
                "Conversion":    "SFX",
                "Destination":   f"ExternalSource/{relative_audio_path}",
                "AnalysisTypes": "2"
            })
            external_source_list_root_element.append(source_element)

        from xml import etree
        etree.ElementTree.indent(external_source_list_root_element, "\t")
        self.write_wwise_xml(external_source_list_root_element, external_source_list_path)
        result_content_str: str = f"刷新外部源列表完成"
        if len(audio_path_list) > 0:
            result_content_str += f"\n找到{len(audio_path_list)}个外部源"
        else:
            result_content_str += f"\n没有找到外部源"
        self.finish_signal.emit("结果", result_content_str, "success")

    def convert_external_source(self, project_id: str):
        self.update_progress_text_signal.emit(f"转码外部源...")
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wwise_project_dir_path = os.path.dirname(wwise_project_path)
        wproj_root_element = self.read_wproj_file(wwise_project_path)

        original_dir_path: str = WprojUtility.get_original_sample_path(wproj_root_element)
        if not original_dir_path:
            original_dir_path = "Originals"
        external_source_dir_path = f"{wwise_project_dir_path}/{original_dir_path}/ExternalSource"
        soundbank_dir_path_list: list[str] = self.get_soundbank_path_list(wproj_root_element)
        soundbank_dir_path_list = [f"{wwise_project_dir_path}/{x}" for x in soundbank_dir_path_list]
        soundbank_external_source_dir_path_list = [f"{x}/ExternalSource" for x in soundbank_dir_path_list]
        generated_soundbank_dir_path = f"{wwise_project_dir_path}/GeneratedSoundBanks"
        external_source_list_file_name = "ExternalSourceList.xml"
        external_source_list_path = f"{generated_soundbank_dir_path}/{external_source_list_file_name}"
        if not os.path.isfile(external_source_list_path):
            for soundbank_external_source_dir_path in soundbank_external_source_dir_path_list:
                if os.path.isdir(soundbank_external_source_dir_path):
                    shutil.rmtree(soundbank_external_source_dir_path)
            self.error_signal.emit("外部源列表不存在, 清空外部源转码目录.")
            self.finish_signal.emit("任务中止", "", "warning")
            return

        self.update_progress_text_signal.emit(f"检查外部源列表...")
        external_source_xml_element_root = self.read_xml(external_source_list_path)
        if external_source_xml_element_root is None:
            self.finish_signal.emit("任务中止", "", "error")
            return
        external_source_element_list: list[Element] = external_source_xml_element_root.findall("Source")
        external_source_path_set: set[str] = set([f"{external_source_dir_path}/{element.get('Path')}" for element in external_source_element_list])

        missing_external_source_set: set[str] = set()
        for external_source_path in external_source_path_set:
            if not os.path.isfile(external_source_path):
                missing_external_source_set.add(external_source_path)
        if len(missing_external_source_set) > 0:
            missing_external_source_list: list = [(x, None, None) for x in missing_external_source_set]
            self.show_wwise_object_check_window_signal.emit("外部源缺失列表", missing_external_source_list)
            self.finish_signal.emit("任务中止", "请先排查完外部源缺失的问题再执行", "error")
            return

        self.update_progress_text_signal.emit(f"清理废弃外部源转码文件...")
        external_source_destination_relative_path_set: set[str] = set([element.get("Destination") for element in external_source_element_list])
        for soundbank_dir_path in soundbank_dir_path_list:
            if not os.path.isdir(soundbank_dir_path):
                continue
            external_source_destinatione_path_set: set[str] = set([f"{soundbank_dir_path}/{x}"[:-3] + "wem" for x in external_source_destination_relative_path_set])
            delete_external_source_path_set = set(self.get_files(f"{soundbank_dir_path}/ExternalSource", [".wem"])) - external_source_destinatione_path_set
            for delete_external_source_path in delete_external_source_path_set:
                self.delete_file(delete_external_source_path)
        self.remove_empty_directory(generated_soundbank_dir_path)

        wwise_project_version: str = self.get_wwise_version(wproj_root_element)
        wwise_project_version = wwise_project_version[:wwise_project_version.index(".")]
        # 获取对应Wwise工程的Wwise设计工具路径
        wwise_authoring_path = self.get_best_match_wwise_authoring_path(project_id)
        if not wwise_authoring_path:
            self.finish_signal.emit("任务中止", "", "warning")
            return

        if main.is_windows_os():
            wwise_project_path = wwise_project_path.replace("/", "\\")
            wwise_console_path = f"{os.path.dirname(wwise_authoring_path)}/WwiseConsole.exe"
            wwise_console_path = wwise_console_path.replace("/", "\\")
            external_source_list_path = external_source_list_path.replace("/", "\\")
        else:
            wwise_console_path = f"{wwise_authoring_path}/Contents/Tools/WwiseConsole.sh"
        import subprocess
        self.update_progress_text_signal.emit(f"转码外部源...")
        if int(wwise_project_version) >= 2024:
            process = subprocess.run([f"{wwise_console_path}", "convert-external-source", f"{wwise_project_path}", "--source-file", f"{external_source_list_path}"], capture_output=True)
        else:
            process = subprocess.run([f"{wwise_console_path}", "convert-external-source", f"{wwise_project_path}", "--source-file", f"{external_source_list_path}", "--no-wwise-dat"],
                                     capture_output=True)
        if process.returncode == 1:
            self.error_signal.emit(f"转码外部源发生异常:\n{process.stdout.decode()}")
            self.finish_signal.emit("结果", "任务中止", "error")
            return

        self.finish_signal.emit("结果", "转码外部源完成", "success")
    '''

    def get_best_match_wwise_authoring_path(self, project_id: str) -> str:
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wproj_root_element = self.read_wwise_project_file(wwise_project_path)
        wwise_project_version: str = self.get_wwise_version(wproj_root_element)
        wwise_project_version = wwise_project_version[:wwise_project_version.index(".")]
        # 获取对应Wwise工程的Wwise设计工具路径
        wwise_authoring_list: Optional[list[str]] = config_utility.get_config(ConfigUtility.WWISE_AUTHORING_LIST_CONFIG_NAME)
        if not wwise_authoring_list or len(wwise_authoring_list) == 0:
            self.error_signal.emit(f"未添加Wwise设计工具, 请在设置中添加Wwise设计工具后继续.")
            return ""

        from packaging.version import Version
        best_match_wwise_authoring_path = ""
        best_match_wwise_authoring_version: Version = Version("0")
        for wwise_authoring_path in wwise_authoring_list:
            if main.is_windows_os() and not os.path.isfile(wwise_authoring_path) or not main.is_windows_os() and not os.path.isdir(wwise_authoring_path):
                self.error_signal.emit(f"无法在以下路径找到Wwise设计工具, 请确认:\n\"{wwise_authoring_path}\"")
                continue
            wwise_authoring_version = config_utility.get_wwise_authoring_version(wwise_authoring_path)
            wwise_authoring_large_version = wwise_authoring_version[:wwise_authoring_version.index(".")]
            if wwise_authoring_large_version != wwise_project_version:
                continue
            if Version(wwise_authoring_version) > best_match_wwise_authoring_version:
                best_match_wwise_authoring_version = Version(wwise_authoring_version)
                best_match_wwise_authoring_path = wwise_authoring_path

        if best_match_wwise_authoring_path == "":
            self.error_signal.emit(f"没有找到Wwise工程所需版本\"{wwise_project_version}\"的Wwise设计工具, 请在设置中添加符合版本条件的Wwise设计工具后继续.")
        return best_match_wwise_authoring_path

    def validate_sample_name_for_import_job(self, dir_path: str):
        self.update_progress_text_signal.emit("收集素材...")
        sample_path_list = self.get_files(dir_path, [".wav"])

        is_all_valid = True

        check_list = []

        file_name_character_invalid_check_list = ("素材名不合法, 不允许有除了英文数字以及半角下划线\"_\"外的其他字符", False, [])

        container_abbr_invalid_check_list = (f"容器元素命名不合法, 容器类型仅支持\"{IMPORT_CONTAINER_TYPE_LIST}\"", False, [])
        container_element_invalid_check_list = ("容器元素命名不合法, 不符合\"(容器缩写)-(...)\"的规范", False, [])

        import_sample_type_list = IMPORT_SAMPLE_TYPE_LIST
        if len(CUSTOM_IMPORT_CHARACTER_TYPE_DICT) > 0:
            import_sample_type_list += CUSTOM_IMPORT_CHARACTER_TYPE_DICT.keys()
        sample_type_invalid_check_list = (f"素材名不合法, 素材类型(第1个元素)仅支持\"{import_sample_type_list}\"", False, [])

        character_sample_element_length_invalid_check_list = ("角色素材命名不合法, 素材命名中的元素至少需要4个及以上(不含容器定义元素)", False, [])

        story_voice_sample_element_length_invalid_check_list = ("剧情语音素材命名不合法, 素材命名中的元素至少需要2个(纯数字ID式的素材)及以上(不含容器定义元素)", False, [])

        rename_failed_check_list = ("重命名素材名失败, 已存在理想命名的文件占位", False, [])
        rename_succeeded_check_list = ("以下素材已成功执行重命名以符合规范", False, [])

        exist_sample_type_set: set[str] = set()

        for sample_path in sample_path_list:
            is_valid = True
            file_name = os.path.basename(sample_path)
            self.update_progress_text_signal.emit(f"检查素材命名规范...\n\"{file_name}\"")
            file_name_stem = Path(sample_path).stem
            parent_dir_path = os.path.dirname(sample_path)
            relative_dir_path = parent_dir_path[len(dir_path):]
            sample_name_invalid_check_str = (f"\"{file_name}\"; 相对目录路径: \"{relative_dir_path}\"", False, None)
            file_name_split = file_name_stem.split()
            for i in range(len(file_name_split)):
                file_name_element = file_name_split[i]
                # 不允许有除了英文数字以及半角下划线"_"外的其他字符
                file_name_element = self._string_capitalize(file_name_element)
                file_name_split[i] = file_name_element

                for letter in file_name_element:
                    if letter.isalnum() or letter == "_":
                        continue
                    if i == len(file_name_split) - 1 and letter == "-":
                        continue
                    file_name_character_invalid_check_list[2].append(sample_name_invalid_check_str)
                    is_valid = False
                    break

                if i == len(file_name_split) - 1 and "-" in file_name_element:
                    # 最后的元素如果包含"-", 则认为是以容器形式入库的, 进行容器的命名格式检查
                    container_split_list = list(filter(None, file_name_element.split("-")))
                    if len(container_split_list) != 2:
                        container_element_invalid_check_list[2].append(sample_name_invalid_check_str)
                        is_valid = False
                    else:
                        container_abbr = container_split_list[0]
                        container_abbr = container_abbr.upper()
                        container_split_list[0] = container_abbr
                        if container_abbr not in IMPORT_CONTAINER_TYPE_LIST:
                            container_abbr_invalid_check_list[2].append(sample_name_invalid_check_str)
                            is_valid = False
                        container_split_list[1] = self._string_capitalize(container_split_list[1])
                        container_element = "-".join(container_split_list)
                        file_name_split[i] = container_element

                if i == 0:
                    if file_name_element in IMPORT_CHARACTER_TYPE_LIST or file_name_element in CUSTOM_IMPORT_CHARACTER_TYPE_DICT:
                        exist_sample_type_set.add(file_name_element)
                        # 如果第一个元素是角色标识缩写, 则进行角色素材的命名规范检查
                        if len(file_name_split) < 4:
                            character_sample_element_length_invalid_check_list[2].append(sample_name_invalid_check_str)
                            is_valid = False
                        elif "-" in file_name_split[len(file_name_split) - 1] and len(file_name_split) < 5:
                            character_sample_element_length_invalid_check_list[2].append(sample_name_invalid_check_str)
                            is_valid = False
                        else:
                            for j in range(3, len(file_name_split)):
                                # 纯数字的元素, 去掉可能存在的前置的若干个0, 对于角色素材, 从第4个元素开始检查
                                file_name_number_element = file_name_split[j]
                                if file_name_number_element.isdigit():
                                    file_name_split[j] = str(int(file_name_number_element))

                    elif file_name_element in IMPORT_STORY_VOICE_TYPE_LIST:
                        if len(file_name_split) < 2:
                            story_voice_sample_element_length_invalid_check_list[2].append(sample_name_invalid_check_str)
                            is_valid = False
                        elif len(file_name_split) == 2:
                            second_element = file_name_split[1]
                            if not second_element.isdigit():
                                story_voice_sample_element_length_invalid_check_list[2].append(sample_name_invalid_check_str)
                                is_valid = False
                        elif len(file_name_split) == 3:
                            second_element = file_name_split[1]
                            is_third_element_container_element = "-" in file_name_split[2]
                            if second_element.isdigit() and not is_third_element_container_element:
                                story_voice_sample_element_length_invalid_check_list[2].append(sample_name_invalid_check_str)
                                is_valid = False
                            elif not second_element.isdigit() and is_third_element_container_element:
                                story_voice_sample_element_length_invalid_check_list[2].append(sample_name_invalid_check_str)
                                is_valid = False
                    else:
                        sample_type_invalid_check_list[2].append(sample_name_invalid_check_str)
                        is_valid = False

            if not is_valid:
                is_all_valid = False
                continue

            format_file_name = " ".join(file_name_split)
            format_file_name = f"{format_file_name}.wav"

            if format_file_name == file_name:
                continue

            rename_check_str = (f"\"{file_name}\" -> \"{format_file_name}\"; 相对目录路径: \"{relative_dir_path}\"", False, None)
            rename_file_path = f"{parent_dir_path}/{format_file_name}"

            if not os.path.isfile(rename_file_path):
                if self.move_file(sample_path, rename_file_path):
                    rename_succeeded_check_list[2].append(rename_check_str)
            else:
                if self.check_same_file(sample_path, rename_file_path):
                    if self.move_file(sample_path, rename_file_path):
                        rename_succeeded_check_list[2].append(rename_check_str)
                else:
                    rename_failed_check_list[2].append(rename_check_str)
                    is_valid = False

            if not is_valid:
                is_all_valid = False

        if len(file_name_character_invalid_check_list[2]) > 0:
            check_list.append(file_name_character_invalid_check_list)

        if len(sample_type_invalid_check_list[2]) > 0:
            check_list.append(sample_type_invalid_check_list)

        if len(character_sample_element_length_invalid_check_list[2]) > 0:
            check_list.append(character_sample_element_length_invalid_check_list)

        if len(story_voice_sample_element_length_invalid_check_list[2]) > 0:
            check_list.append(story_voice_sample_element_length_invalid_check_list)

        if len(container_element_invalid_check_list[2]) > 0:
            check_list.append(container_element_invalid_check_list)

        if len(container_abbr_invalid_check_list[2]) > 0:
            check_list.append(container_abbr_invalid_check_list)

        if len(rename_failed_check_list[2]) > 0:
            check_list.append(rename_failed_check_list)

        if len(rename_succeeded_check_list[2]) > 0:
            check_list.append(rename_succeeded_check_list)

        if len(check_list) > 0:
            self.show_check_window_signal.emit("素材命名规范检查列表", check_list)

        if not is_all_valid:
            self.finish_signal.emit("结果", "任务中止, 请先排查完素材命名规范的问题再执行", "error")
        else:
            self.show_result_info_bar_signal.emit("success", "结果", "检查素材命名规范通过")
            self.validate_import_sample_name_succeeded_signal.emit(dir_path)

    def find_sound_object_contain_inactive_source_job(self, project_id: str):
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wwise_project_dir_path: str = os.path.dirname(wwise_project_path)

        actor_mixer_hierarchy_dir_path: str = f"{wwise_project_dir_path}/{ACTOR_MIXER_HIERARCHY}"
        self.update_progress_text_signal.emit("收集工作单元...")
        wwu_path_list: list[str] = self.get_files(actor_mixer_hierarchy_dir_path, [".wwu"])
        check_str_dict: dict = {}
        sound_object_contain_inactive_source_count: int = 0
        for wwu_path in wwu_path_list:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            self.update_progress_text_signal.emit(f"读取工作单元...\n\"{os.path.basename(wwu_path)}\"")
            wwu_root_element = self.read_xml(wwu_path)
            if not wwu_root_element:
                self.finish_signal.emit("任务中止", "", "warning")
                return

            sound_element_list: list[Element] = wwu_root_element.findall(".//Sound")
            for sound_element in sound_element_list:
                if self.cancel_job:
                    self.finish_signal.emit("任务中止", "", "warning")
                    return
                sound_element: Element
                sound_name: str = sound_element.get("Name")
                sound_id: str = sound_element.get("ID")
                audio_file_source_element_list: list[Element] = sound_element.findall("./ChildrenList/AudioFileSource")
                audio_file_source_dict: {
                    str: str
                } = {}
                for audio_file_source_element in audio_file_source_element_list:
                    if self.cancel_job:
                        self.finish_signal.emit("任务中止", "", "warning")
                        return
                    audio_file_source_element: Element
                    audio_file_source_id: str = audio_file_source_element.get("ID")
                    language: str = audio_file_source_element.find("Language").text
                    audio_file_source_dict[audio_file_source_id] = language

                active_source_list: set[str] = set()
                active_source_element_list: list[Element] = sound_element.findall("./ActiveSourceList/ActiveSource")
                for active_source_element in active_source_element_list:
                    if self.cancel_job:
                        self.finish_signal.emit("任务中止", "", "warning")
                        return
                    active_source_element: Element
                    active_source_element_id: str = active_source_element.get("ID")
                    active_source_list.add(active_source_element_id)

                match: bool = False
                for audio_file_source_id, language in audio_file_source_dict.items():
                    if self.cancel_job:
                        self.finish_signal.emit("任务中止", "", "warning")
                        return
                    if audio_file_source_id not in active_source_list:
                        match = True
                        if language not in check_str_dict:
                            check_str_dict[language] = []
                        check_str_dict[language].append((sound_name, sound_id))

                if match:
                    sound_object_contain_inactive_source_count += 1

        for _, sound_name_list in check_str_dict.items():
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            sound_name_list: list[tuple[str, bool]]
            sound_name_list.sort(key=lambda sound_name_tuple: sound_name_tuple[0])

        check_list: list[tuple[str, str | None, list]] = []
        for language in sorted(check_str_dict.keys()):
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            check_list.append((language, None, check_str_dict[language]))

        if len(check_list) > 0:
            self.show_wwise_object_check_window_signal.emit("含有未激活素材的声音对象列表", check_list)
            self.finish_signal.emit("结果", f"查找含有未激活素材的声音对象完成\n查找到{sound_object_contain_inactive_source_count}个声音对象", "success")
        else:
            self.finish_signal.emit("结果", "查找含有未激活素材的声音对象完成\n不存在符合的声音对象", "success")

    def find_missing_language_voice_object_job(self, project_id: str):
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wwise_project_dir_path: str = os.path.dirname(wwise_project_path)

        actor_mixer_hierarchy_dir_path: str = f"{wwise_project_dir_path}/{ACTOR_MIXER_HIERARCHY}"
        self.update_progress_text_signal.emit("收集工作单元...")
        wwu_path_list: list[str] = self.get_files(actor_mixer_hierarchy_dir_path, [".wwu"])
        wproj_root_element: Element = self.read_wwise_project_file(wwise_project_path)
        language_list: list[str] = WprojUtility.get_language_list(wproj_root_element)
        language_set: set[str] = set(language_list)
        check_str_dict: dict = {}
        missing_language_voice_object_count: int = 0
        for wwu_path in wwu_path_list:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            self.update_progress_text_signal.emit(f"读取工作单元...\n\"{os.path.basename(wwu_path)}\"")
            wwu_root_element = self.read_xml(wwu_path)
            if not wwu_root_element:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            voice_element_list: list[Element] = wwu_root_element.findall(".//Property[@Name='IsVoice'][@Value='True']/../..")
            for voice_element in voice_element_list:
                if self.cancel_job:
                    self.finish_signal.emit("任务中止", "", "warning")
                    return
                voice_element: Element
                voice_name: str = voice_element.get("Name")
                voice_id: str = voice_element.get("ID")
                audio_file_source_element_list: list[Element] = voice_element.findall("./ChildrenList/AudioFileSource")
                exist_language_set: set[str] = set()
                for audio_file_source_element in audio_file_source_element_list:
                    if self.cancel_job:
                        self.finish_signal.emit("任务中止", "", "warning")
                        return
                    audio_file_source_element: Element
                    language: str = audio_file_source_element.find("Language").text
                    exist_language_set.add(language)

                missing_language_set: set[str] = language_set - exist_language_set
                if missing_language_set:
                    missing_language_voice_object_count += 1
                    for missing_language in missing_language_set:
                        if missing_language not in check_str_dict:
                            check_str_dict[missing_language] = []
                        check_str_dict[missing_language].append((voice_name, voice_id))

        for _, sound_name_list in check_str_dict.items():
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            sound_name_list: list[tuple[str, str]]
            sound_name_list.sort(key=lambda sound_name_tuple: sound_name_tuple[0])

        check_list: list[tuple[str, str | None, list]] = []
        for language in sorted(check_str_dict.keys()):
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            check_list.append((language, None, check_str_dict[language]))

        if len(check_list) > 0:
            self.show_wwise_object_check_window_signal.emit("缺失语言素材的语音对象列表", check_list)
            self.finish_signal.emit("结果", f"查找缺失语言素材的语音对象完成\n查找到{missing_language_voice_object_count}个语音对象", "success")
        else:
            self.finish_signal.emit("结果", "查找缺失语言素材的语音对象完成\n不存在符合的语音对象", "success")

    def find_wrong_referenced_voice_event_job(self, project_id: str):
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wwise_project_dir_path: str = os.path.dirname(wwise_project_path)

        events_dir_path: str = f"{wwise_project_dir_path}/{EVENTS}/Story"
        self.update_progress_text_signal.emit("收集工作单元...")
        wwu_path_list: list[str] = self.get_files(events_dir_path, [".wwu"])
        check_str_list: list = []
        wrong_referenced_voice_event_count: int = 0
        for wwu_path in wwu_path_list:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            self.update_progress_text_signal.emit(f"读取工作单元...\n\"{os.path.basename(wwu_path)}\"")
            wwu_root_element = self.read_xml(wwu_path)
            if not wwu_root_element:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            event_element_list: list[Element] = wwu_root_element.findall(".//Event")
            for event_element in event_element_list:
                if self.cancel_job:
                    self.finish_signal.emit("任务中止", "", "warning")
                    return
                event_element: Element
                event_name: str = event_element.get("Name")
                event_id: str = event_element.get("ID")
                object_ref_element = event_element.find(".//ObjectRef")
                if object_ref_element is None:
                    wrong_referenced_voice_event_count += 1
                    check_str_list.append((event_name, event_id, None))
                else:
                    wrong_referenced_voice_event_count += 1
                    object_ref_name = object_ref_element.get("Name")
                    if object_ref_name != event_name.replace("_", " "):
                        check_str_list.append((event_name, event_id, None))

        if len(check_str_list) > 0:
            self.show_wwise_object_check_window_signal.emit("错误引用语音对象的语音事件对象列表", check_str_list)
            self.finish_signal.emit("结果", f"查找错误引用语音对象的语音事件对象完成\n查找到{wrong_referenced_voice_event_count}个语音事件对象", "success")
        else:
            self.finish_signal.emit("结果", "查找错误引用语音对象的语音事件对象完成\n不存在符合的语音事件对象", "success")

    def _update_work_unit_info_dict(self, work_unit_path: str, wwise_document_element: Element):
        """
        更新工作单元字典
        """
        work_unit_id: str = wwise_document_element.get("ID")
        parent_document_id: Optional[str] = wwise_document_element.get("ParentDocumentID")
        self.work_unit_info_dict[work_unit_id] = WorkUnitInfo()
        work_unit_info = self.work_unit_info_dict[work_unit_id]
        work_unit_info.element = wwise_document_element
        work_unit_info.file_path = work_unit_path
        if parent_document_id:
            work_unit_info.parent_work_unit_id = parent_document_id
        if work_unit_path.startswith(f"{self.wwise_project_dir_path}/{ACTOR_MIXER_HIERARCHY}"):
            work_unit_type = ACTOR_MIXER_HIERARCHY
        elif work_unit_path.startswith(f"{self.wwise_project_dir_path}/{INTERACTIVE_MUSIC_HIERARCHY}"):
            work_unit_type = INTERACTIVE_MUSIC_HIERARCHY
        else:
            work_unit_type = EVENTS
        work_unit_info.work_unit_type = work_unit_type

    def _format_specific_tag_element_name(self, wwise_document_element: Element, format_tag_list: list[str], allow_underscore=False):
        for element_tag in format_tag_list:
            element_list = wwise_document_element.findall(f".//{element_tag}")
            for element in element_list:
                # 格式化Wwise对象的名字, 首字母大写, 去掉多余空格, 使用空格取代"_"作为分隔符
                self._format_element_name(element, allow_underscore)
                if element_tag == "AudioSourceRef":
                    self._sync_music_clip_name_to_audio_source_ref_name(element)
                elif element_tag == "MusicTrack":
                    self._sync_music_track_name_to_audio_file_source_name(element)
                elif element_tag == "MusicSegment":
                    self._sync_music_segment_name_to_music_track_name(element)

    def _calculate_reference_work_unit_path(self, wwise_document_element: Element, path_tag_list: list[str]):
        """
        计算工作单元里引用工作单元的路径
        """
        reference_work_unit_element_list = wwise_document_element.findall(f".//WorkUnit[@PersistMode='Reference']")
        for reference_work_unit_element in reference_work_unit_element_list:
            recursive_element = reference_work_unit_element
            reference_work_unit_id = reference_work_unit_element.get("ID")
            relative_path = ""
            while recursive_element in self.element_info_dict.keys():
                parent_element = self._get_parent_element(recursive_element)
                if parent_element.tag in path_tag_list:
                    parent_element_name: str = parent_element.get("Name")
                    relative_path = f"{parent_element_name}/{relative_path}"
                elif parent_element.tag == "WorkUnit":
                    break
                recursive_element = parent_element
            if relative_path.endswith("/"):
                relative_path = relative_path[:-1]
            if relative_path:
                self.work_unit_info_dict[reference_work_unit_id].path_to_parent_work_unit = relative_path

    def _collect_audio_file_path(self, wwise_document_element: Element, work_unit_type: str):
        """
        收集音频文件路径
        """
        remove_audio_file_source_id_list: list[str] = []

        audio_file_source_element_list = wwise_document_element.findall(".//AudioFileSource")
        for audio_file_source_element in audio_file_source_element_list:
            language = audio_file_source_element.find("./Language").text
            relative_path = audio_file_source_element.find("./AudioFile").text
            if language == "SFX":
                audio_file_path = Path(f"{self.wwise_project_sfx_dir_path}/{relative_path}")
            else:
                audio_file_path = Path(f"{self.wwise_project_voice_dir_path}/{language}/{relative_path}")
            if audio_file_path.is_file():
                audio_file_path_str = audio_file_path.as_posix()
                audio_file_info = self.audio_file_info_dict.setdefault(audio_file_path_str, AudioFileInfo())
                audio_file_info.language = language
                audio_file_info.work_unit_type = work_unit_type
                if audio_file_info.audio_file_source_elements is None:
                    audio_file_info.audio_file_source_elements = set()
                audio_file_info.audio_file_source_elements.add(audio_file_source_element)
            else:
                # 如果对应的音频文件不存在了, 则直接删除AudioFileSource对象, 以及其所有的引用
                remove_audio_file_source_id_list.append(audio_file_source_element.get("ID"))

        plugin_media_source_elements = wwise_document_element.findall(".//PluginMediaSource")
        for plugin_media_source_element in plugin_media_source_elements:
            source_plugin_element = self._get_audio_file_source_sound_element(plugin_media_source_element)
            plugin_name = source_plugin_element.get("PluginName")
            language = source_plugin_element.find("./Language").text
            relative_path = plugin_media_source_element.find("./PropertyList/Property[@Name='DataFileName']").get("Value")
            audio_file_path = Path(f"{self.wwise_project_plugin_dir_path}/{plugin_name}/{relative_path}")
            if audio_file_path.is_file():
                audio_file_path_str = audio_file_path.as_posix()
                audio_file_info = self.audio_file_info_dict.setdefault(audio_file_path_str, AudioFileInfo())
                audio_file_info.language = language
                audio_file_info.work_unit_type = work_unit_type
                audio_file_info.plugin_name = plugin_name
                if audio_file_info.plugin_media_source_elements is None:
                    audio_file_info.plugin_media_source_elements = set()
                audio_file_info.plugin_media_source_elements.add(plugin_media_source_element)
            else:
                # 如果对应的音频文件不存在了, 则直接删除AudioFileSource对象, 以及其所有的引用
                remove_audio_file_source_id_list.append(plugin_media_source_element.get("ID"))

        for remove_audio_file_source_id in remove_audio_file_source_id_list:
            for element in self.wwise_object_info_dict[remove_audio_file_source_id].element_list:
                work_unit_id = self.element_info_dict[element].work_unit_id
                parent_element = self._get_parent_element(element)
                parent_element.remove(element)
                self.work_unit_info_dict[work_unit_id].modified = True

    def _format_element_name(self, element: Element, allow_underscore=False):
        name = element.get("Name")
        new_name = self._format_sample_name(name, allow_underscore)
        if new_name != name:
            self._print_log(f"格式化\"{element.tag}\"对象命名: \"{name}\" -> \"{new_name}\"")
            element.set("Name", new_name)
            self._sync_all_reference_element_name(element)

    def _format_sample_name(self, name: str, allow_underscore=False) -> str:
        new_name = name.strip()
        if not allow_underscore:
            new_name = new_name.replace("_", " ")

        def repl_func(m):
            """process regular expression match groups for word upper-casing problem"""
            return m.group(1) + m.group(2).upper()

        new_name = re.sub("(^|\\s)(\\S)", repl_func, new_name)

        return new_name

    def _sync_all_reference_element_name(self, element: Element):
        name: str = element.get("Name")
        element_id: str = element.get("ID")
        wwise_object_info = self.wwise_object_info_dict[element_id]
        for sync_element in wwise_object_info.element_list:
            sync_element.set("Name", name)
            work_unit_id = self.element_info_dict[element].work_unit_id
            work_unit_info = self.work_unit_info_dict[work_unit_id]
            work_unit_info.modified = True

    def _sync_music_clip_name_to_audio_source_ref_name(self, audio_source_ref_element: Element):
        # 如果引用音频文件的音乐片段的名字与音频文件的名字不一样, 则使用音频文件的名字作为音乐片段的名字
        audio_source_ref_name = audio_source_ref_element.get("Name")
        music_clip_element = self._get_parent_element(audio_source_ref_element)
        music_clip_name = music_clip_element.get("Name")
        if music_clip_name != audio_source_ref_name:
            music_clip_element.set("Name", audio_source_ref_name)
            self._sync_all_reference_element_name(music_clip_element)

    def _sync_music_track_name_to_audio_file_source_name(self, music_track_element: Element):
        # 如果音乐轨道里只有一个音频文件引用, 则使用其名字作为轨道名字
        music_track_name: str = music_track_element.get("Name")
        children_audio_file_source_element_list = music_track_element.findall("./ChildrenList/AudioFileSource")
        music_track_element_list = self._get_parent_element(music_track_element).findall("./MusicTrack")
        if len(children_audio_file_source_element_list) == 1 and len(music_track_element_list) == 1:
            audio_file_source_name = children_audio_file_source_element_list[0].get("Name")
            if music_track_name != audio_file_source_name:
                music_track_element.set("Name", audio_file_source_name)
                self._sync_all_reference_element_name(music_track_element)

    def _sync_music_segment_name_to_music_track_name(self, music_segment_element: Element):
        # 如果音乐里只有一个音频轨道, 则使用其名字作为音乐名字
        music_segment_name = music_segment_element.get("Name")
        music_track_element_list = music_segment_element.findall("./ChildrenList/MusicTrack")
        music_segment_element_list = self._get_parent_element(music_segment_element).findall("./MusicSegment")
        if len(music_track_element_list) == 1 and len(music_segment_element_list) == 1:
            music_track_name = music_track_element_list[0].get("Name")
            if music_segment_name != music_track_name:
                music_segment_element.set("Name", music_track_name)
                self._sync_all_reference_element_name(music_segment_element)

    def _get_parent_element(self, element: Element) -> Element:
        return self.element_info_dict[element].parent_element

    def _get_audio_file_source_sound_element(self, element: Element) -> Element:
        target_element = self._get_parent_element(element)
        target_element = self._get_parent_element(target_element)
        return target_element

    def _is_audio_file_source_active_source(self, element: Element) -> bool:
        target_audio_file_source_id = element.get("ID")
        target_sound_element = self._get_audio_file_source_sound_element(element)
        match_active_source_element = target_sound_element.find(f"./ActiveSourceList/ActiveSource[@ID='{target_audio_file_source_id}']")
        if match_active_source_element is not None:
            return True
        else:
            return False

    def _get_children_list_from_sound_element(self, element: Element, language: Optional[str] = None) -> list[Element]:
        if not language:
            return element.findall(f"./ChildrenList/*")
        else:
            return element.findall(f"./ChildrenList/*/Language[.='{language}']/..")

    def _temp_move_audio_file(self, audio_file_path: str, audio_file_info: AudioFileInfo):
        # 现有的音频文件路径与理想的音频文件路径不同(大小写区分), 需要移动或重命名, 先将这些文件都移动到一个临时的地方, 防止可能出现的重名冲突或文件系统大小写不区分造成的冲突
        temp_audio_file_path = uuid.uuid4()
        temp_audio_file_path = str(temp_audio_file_path)
        temp_audio_file_path = f"{self.wwise_project_originals_dir_path}/{temp_audio_file_path}"
        if self.move_file(audio_file_path, temp_audio_file_path):
            delete_sample_akd_path = f"{audio_file_path[:-3]}akd"
            if Path(delete_sample_akd_path).is_file():
                self.delete_file(delete_sample_akd_path)
            audio_file_info.temp_audio_file_path = temp_audio_file_path

    def _get_audio_file_relative_path(self, audio_file_info: AudioFileInfo) -> str:
        language = audio_file_info.language
        if not language or language == "SFX":
            if audio_file_info.plugin_media_source_elements is not None:
                relative_path = audio_file_info.ideal_audio_file_path[len(f"{self.wwise_project_plugin_dir_path}/{audio_file_info.plugin_name}/"):].replace("/", "\\")
            else:
                relative_path = audio_file_info.ideal_audio_file_path[len(self.wwise_project_sfx_dir_path) + 1:].replace("/", "\\")
        else:
            relative_path = audio_file_info.ideal_audio_file_path[len(f"{self.wwise_project_voice_dir_path}/{language}/"):].replace("/", "\\")
        return relative_path

    def _sync_audio_file(self, audio_file_info_dict: dict[str, AudioFileInfo]):
        current_count = 0
        self.update_progress_current_count_signal.emit(current_count)
        for audio_file_path, audio_file_info in audio_file_info_dict.items():
            language = audio_file_info.language
            temp_audio_file_path = audio_file_info.temp_audio_file_path
            ideal_audio_file_path = audio_file_info.ideal_audio_file_path
            if temp_audio_file_path and self.move_file(temp_audio_file_path, ideal_audio_file_path):
                self.update_progress_text_signal.emit(
                        f"移动音频文件...\n\"{os.path.basename(audio_file_path)}\"")
                # self._print_log(f"整理音频文件: {audio_file_path} -> {ideal_audio_file_path}")
                if audio_file_info.audio_file_source_elements is not None:
                    for audio_file_source_element in audio_file_info.audio_file_source_elements:
                        relative_path = self._get_audio_file_relative_path(audio_file_info)
                        audio_file_source_element.find("./AudioFile").text = relative_path
                        target_work_unit_id = self.element_info_dict[audio_file_source_element].work_unit_id
                        self.work_unit_info_dict[target_work_unit_id].modified = True
                elif audio_file_info.plugin_media_source_elements is not None:
                    for plugin_media_source_element in audio_file_info.plugin_media_source_elements:
                        relative_path = self._get_audio_file_relative_path(audio_file_info)
                        plugin_media_source_element.find("./PropertyList/Property[@Name='DataFileName']").set("Value", relative_path)
                        target_work_unit_id = self.element_info_dict[plugin_media_source_element].work_unit_id
                        self.work_unit_info_dict[target_work_unit_id].modified = True

            current_count += 1
            self.update_progress_current_count_signal.emit(current_count)

    def _write_work_unit(self, cancel=False):
        modified_wwu_count = 0
        total_count = len(self.work_unit_info_dict.keys())
        self.update_progress_text_signal.emit(f"写入工作单元...")
        self.update_progress_total_count_signal.emit(total_count)
        current_count = 0
        self.update_progress_current_count_signal.emit(current_count)
        for work_unit_info in self.work_unit_info_dict.values():
            if work_unit_info.modified:
                file_path: str = work_unit_info.file_path
                modified_wwu_count += 1
                self.update_progress_text_signal.emit(f"写入工作单元...\n\"{os.path.basename(file_path)}\"")
                self.write_wwise_xml(work_unit_info.element, file_path)
                work_unit_info.modified = False
            current_count += 1
            self.update_progress_current_count_signal.emit(current_count)

        self._remove_originals_empty_directory(self.wwise_project_originals_dir_path)

        if cancel:
            result_content_str = "任务中止"
        else:
            result_content_str = "同步素材目录结构完成"
        from Source.Job.wproj_job import WprojJob
        self._base_job: WprojJob
        if modified_wwu_count > 0:
            result_content_str += f"\n同步了{modified_wwu_count}个工作单元"
            from Source.Job.wproj_job import WprojJob
            self._base_job.on_sync_original_dir_structure_complete_signal.emit(True)
        else:
            result_content_str += f"\n没有变动"
            self._base_job.on_sync_original_dir_structure_complete_signal.emit(False)

        if cancel:
            self.finish_signal.emit("任务中止", result_content_str, "warning")
        else:
            self.finish_signal.emit("结果", result_content_str, "success")

    def _remove_originals_empty_directory(self, wwise_project_originals_dir_path):
        wwise_project_sfx_dir_path = f"{wwise_project_originals_dir_path}/SFX"
        wwise_project_voice_dir_path = f"{wwise_project_originals_dir_path}/Voices"
        self.remove_empty_directory(wwise_project_sfx_dir_path)
        if os.path.isdir(wwise_project_voice_dir_path):
            scan_dir_iterator = os.scandir(wwise_project_voice_dir_path)
            for dir_entry in scan_dir_iterator:
                if dir_entry.is_dir():
                    self.remove_empty_directory(dir_entry.path.replace("\\", "/"))

    def _string_capitalize(self, string: str) -> Optional[str]:
        if string is None:
            return None
        string_list = list(string)
        for i in range(len(string)):
            letter = string_list[i]
            if letter.isalpha():
                string_list[i] = letter.upper()
                break
        string = "".join(string_list)
        return string
