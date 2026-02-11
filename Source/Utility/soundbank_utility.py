import json
import os.path
import pathlib
from typing import Optional

from Source.Task.file_copy_task import FileCopyTask
from Source.Task.file_delete_task import FileDeleteTask
from Source.Task.file_sync_task import FileSyncTask
from Source.Utility.config_utility import config_utility, ProjectData
from Source.Utility.file_utility import FileUtility
from Source.Utility.wproj_utility import WprojUtility


class SoundbankUtility(WprojUtility, FileUtility):
    SOUNDBANKS_INFO_NAME = "SoundbanksInfo"
    PLATFORM_INFO_NAME = "PlatformInfo"
    PLUGIN_INFO_NAME = "PluginInfo"
    PRESERVE_FILE_SET = {SOUNDBANKS_INFO_NAME, PLATFORM_INFO_NAME, PLUGIN_INFO_NAME}

    def __init__(self, job):
        super().__init__(job)
        self.sync_count = 0
        self._sync_task_dest_path_to_rel: dict[str, str] = {}
        self._updated_rel_path_list: list[str] = []
        self._copied_rel_path_list: list[str] = []
        self._deleted_rel_path_list: list[str] = []

    @staticmethod
    def _format_path_list(title: str, path_list: list[str], limit: int = 50) -> str:
        if not path_list:
            return f"{title}: （无）"

        shown = path_list[:limit]
        remaining = len(path_list) - len(shown)
        lines = [f"{title}: ({len(path_list)})"]
        lines.extend([f"- {p}" for p in shown])
        if remaining > 0:
            lines.append(f"... 以及 {remaining} 项未显示")
        return "\n".join(lines)

    def sync_soundbank_job(self, project_id: str):
        result, _, _, _ = self.clean_generated_soundbanks_dir(project_id)
        if not result:
            return
        wwise_project_path = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wwise_project_dir_path = os.path.dirname(wwise_project_path)
        wproj_root_element = self.read_wwise_project_file(wwise_project_path)
        wwise_version = self.get_wwise_version(wproj_root_element)
        wwise_version_year = int(wwise_version.split(".")[0])
        is_new_wwise_version = wwise_version_year >= 2022

        unity_soundbank_dir_path = config_utility.get_config(ProjectData.UNITY_WWISE_BANK_PATH, project_id)
        language_check_dict = config_utility.get_project_language_check_dict_config(project_id)
        soundbank_path_list = self.get_soundbank_path_list(wproj_root_element)
        soundbank_path_list = [f"{wwise_project_dir_path}/{x}" for x in soundbank_path_list]
        generated_soundbank_dir_path = f"{wwise_project_dir_path}/GeneratedSoundBanks"
        generated_soundbank_dir_file_path_set: set[str] = set()

        project_info_json_path = f"{generated_soundbank_dir_path}/ProjectInfo.json"
        project_info_xml_path = f"{generated_soundbank_dir_path}/ProjectInfo.xml"
        if os.path.isfile(project_info_json_path):
            generated_soundbank_dir_file_path_set.add(project_info_json_path)
        if os.path.isfile(project_info_xml_path):
            generated_soundbank_dir_file_path_set.add(project_info_xml_path)

        self.update_progress_text_signal.emit(f"同步声音库...")
        wwopus_dir_path = f"{generated_soundbank_dir_path}/ExternalSource"
        wwopus_relative_path_list = []
        if os.path.isdir(wwopus_dir_path):
            wwopus_path_list = self.get_files(wwopus_dir_path, [".wwopus"])
            wwopus_relative_path_list = [x[len(generated_soundbank_dir_path) + 1:] for x in wwopus_path_list]

        for soundbank_path in soundbank_path_list:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return

            current_dir_file_list = self.get_files(soundbank_path, [".bnk", ".wem", "json", "xml"], is_recursively=False)
            generated_soundbank_dir_file_path_set.update(current_dir_file_list)

            generated_soundbank_dir_file_path_set.update([f"{soundbank_path}/{x}" for x in wwopus_relative_path_list])

            if is_new_wwise_version:
                streamed_dir_path = f"{soundbank_path}/Media"
                current_dir_file_list = self.get_files(streamed_dir_path, [".wem"], is_recursively=False)
                generated_soundbank_dir_file_path_set.update(current_dir_file_list)

            if language_check_dict:
                for language, check_state in language_check_dict.items():
                    if check_state:
                        language_dir_path = f"{soundbank_path}/{language}"
                        current_dir_file_list = self.get_files(language_dir_path, [".bnk", ".wem", "json", "xml"], is_recursively=False)
                        generated_soundbank_dir_file_path_set.update(current_dir_file_list)
                        if is_new_wwise_version:
                            streamed_language_dir_path = f"{soundbank_path}/Media/{language}"
                            current_dir_file_list = self.get_files(streamed_language_dir_path, [".wem"], is_recursively=False)
                            generated_soundbank_dir_file_path_set.update(current_dir_file_list)

        generated_soundbank_dir_file_path_set = set([x[len(generated_soundbank_dir_path) + 1:] for x in generated_soundbank_dir_file_path_set])
        unity_soundbank_dir_file_list = self.get_files(unity_soundbank_dir_path, [".meta"], True)
        unity_soundbank_dir_file_path_set = set([x[len(unity_soundbank_dir_path) + 1:] for x in unity_soundbank_dir_file_list])
        if "OriginalAudioFilesManifest.json" in unity_soundbank_dir_file_path_set:
            unity_soundbank_dir_file_path_set.remove("OriginalAudioFilesManifest.json")
        new_file_set = generated_soundbank_dir_file_path_set - unity_soundbank_dir_file_path_set
        delete_file_set = unity_soundbank_dir_file_path_set - generated_soundbank_dir_file_path_set
        sync_file_set = generated_soundbank_dir_file_path_set & unity_soundbank_dir_file_path_set

        self._sync_task_dest_path_to_rel.clear()
        self._updated_rel_path_list.clear()
        self._copied_rel_path_list = sorted(new_file_set)
        self._deleted_rel_path_list = sorted(delete_file_set)

        total_file_count = len(new_file_set) + len(delete_file_set) + len(sync_file_set)
        self.total_task_count = total_file_count
        self.completed_task_count = 0
        copy_file_count = 0
        self.sync_count = 0
        delete_file_count = 0
        if total_file_count == 0:
            self.finish_signal.emit("结果", f"打包声音库目录没有音频文件需要同步", "warning")
            return

        self.update_progress_total_count_signal.emit(total_file_count)
        for new_file in new_file_set:
            source_path = f"{generated_soundbank_dir_path}/{new_file}"
            if pathlib.Path(new_file).suffix == ".wwopus":
                new_wwopus_file = new_file[new_file.index("ExternalSource/"):]
                source_path = f"{generated_soundbank_dir_path}/{new_wwopus_file}"
            task = FileCopyTask(self, source_path, f"{unity_soundbank_dir_path}/{new_file}")
            self.active_task_list.append(task)
            copy_file_count += 1

        for sync_file in sync_file_set:
            source_path = f"{generated_soundbank_dir_path}/{sync_file}"
            if pathlib.Path(sync_file).suffix == ".wwopus":
                new_wwopus_file = sync_file[sync_file.index("ExternalSource/"):]
                source_path = f"{generated_soundbank_dir_path}/{new_wwopus_file}"
            dest_path = f"{unity_soundbank_dir_path}/{sync_file}"
            self._sync_task_dest_path_to_rel[dest_path] = sync_file
            task = FileSyncTask(self, source_path, dest_path)
            self.active_task_list.append(task)

        for delete_file in delete_file_set:
            task = FileDeleteTask(self, f"{unity_soundbank_dir_path}/{delete_file}")
            self.active_task_list.append(task)
            delete_file_count += 1

        def __on_all_task_finished():
            self.remove_empty_directory(unity_soundbank_dir_path)

            copied_list = sorted(self._copied_rel_path_list)
            updated_list = sorted(set(self._updated_rel_path_list))
            deleted_list = sorted(self._deleted_rel_path_list)

            summary = f"同步声音库完成（新增 {len(copied_list)} / 更新 {len(updated_list)} / 删除 {len(deleted_list)}）"
            if len(copied_list) == 0 and len(updated_list) == 0 and len(deleted_list) == 0:
                summary = "同步声音库完成（没有变动）"

            detail_parts: list[str] = [
                summary,
                "",
                self._format_path_list("新增文件", copied_list),
                "",
                self._format_path_list("更新文件", updated_list),
                "",
                self._format_path_list("删除文件", deleted_list),
            ]

            self.finish_signal.emit("结果", "\n".join(detail_parts), "success")

        self.on_all_task_finished = __on_all_task_finished

        self.start_all_task()

    def on_single_task_finished(self, data: Optional[dict]):
        if data:
            is_same = data.get("is_same")
            if is_same is False:
                self.sync_count += 1
                dest_path = data.get("dest_path")
                if dest_path:
                    rel = self._sync_task_dest_path_to_rel.get(dest_path)
                    if rel:
                        self._updated_rel_path_list.append(rel)

    def clean_generated_soundbanks_dir_job(self, project_id: str):
        result, delete_file_count, has_json_modified, has_xml_modified = self.clean_generated_soundbanks_dir(project_id)
        if not result:
            return

        result_content_str: str = "清理打包声音库目录完成\n"
        if delete_file_count == 0:
            result_content_str += "没有变动"
        else:
            result_content_str += f"删除了{delete_file_count}个文件"
        if has_json_modified:
            result_content_str += "\njson文件有修改, 请注意提交"
        if has_xml_modified:
            result_content_str += "\nxml文件有修改, 请注意提交"
        self.finish_signal.emit("结果", result_content_str, "success")

    def clean_generated_soundbanks_dir(self, project_id: str) -> tuple[bool, int, bool, bool]:
        wwise_project_path = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wwise_project_dir_path = os.path.dirname(wwise_project_path)
        wproj_root_element = self.read_wwise_project_file(wwise_project_path)
        wwise_version = self.get_wwise_version(wproj_root_element)
        wwise_version_year = int(wwise_version.split(".")[0])
        is_new_soundbanks_info_structure = wwise_version_year >= 2022

        soundbank_dir_path_list = self.get_soundbank_path_list(wproj_root_element)
        soundbank_dir_path_list = [f"{wwise_project_dir_path}/{x}" for x in soundbank_dir_path_list]
        generated_soundbank_dir_path = f"{wwise_project_dir_path}/GeneratedSoundBanks"

        new_file_path_set: set[str] = set()
        new_soundbank_path_set: set[str] = set()
        exist_file_path_set: set[str] = set()

        has_json_modified = False
        has_xml_modified = False

        project_info_json_path = f"{generated_soundbank_dir_path}/ProjectInfo.json"
        if os.path.isfile(project_info_json_path):
            is_json_modified = False
            with open(project_info_json_path, encoding='utf-8') as json_file:
                project_info: dict = json.load(json_file).get("ProjectInfo")
            if project_info.get("FileHash"):
                project_info.pop("FileHash")
                is_json_modified = True

            if is_json_modified:
                json_object = json.dumps({
                    "ProjectInfo": project_info
                }, indent=1)
                with open(project_info_json_path, "w", encoding="utf-8") as json_file:
                    json_file.write(json_object)
                has_json_modified = True

        project_info_xml_path = f"{generated_soundbank_dir_path}/ProjectInfo.xml"
        if os.path.isfile(project_info_xml_path):
            is_xml_modified = False
            project_info_element = self.read_xml(project_info_xml_path)

            file_hash_element = project_info_element.find("./FileHash")
            if file_hash_element is not None:
                project_info_element.remove(file_hash_element)
                is_xml_modified = True

            if is_xml_modified:
                self.write_wwise_xml(project_info_element, project_info_xml_path)
                has_xml_modified = True

        for soundbank_dir_path in soundbank_dir_path_list:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return False, 0, has_json_modified, has_xml_modified
            exist_file_path_set.update(self.get_files(soundbank_dir_path))

            if self.get_generate_xml_metadata(project_id) is True:
                for name in SoundbankUtility.PRESERVE_FILE_SET:
                    file_path = f"{soundbank_dir_path}/{name}.xml"
                    new_file_path_set.add(file_path)

            if self.get_generate_json_metadata(project_id) is True:
                for name in SoundbankUtility.PRESERVE_FILE_SET:
                    file_path = f"{soundbank_dir_path}/{name}.json"
                    new_file_path_set.add(file_path)

            self.update_progress_text_signal.emit(f"读取\"{SoundbankUtility.SOUNDBANKS_INFO_NAME}\"...")

            soundbanks_info_json_path = f"{soundbank_dir_path}/{SoundbankUtility.SOUNDBANKS_INFO_NAME}.json"
            soundbanks_info_xml_path = f"{soundbank_dir_path}/{SoundbankUtility.SOUNDBANKS_INFO_NAME}.xml"
            if not os.path.isfile(soundbanks_info_json_path):
                if not os.path.isfile(soundbanks_info_xml_path):
                    self.error_signal.emit(
                            f"\"{SoundbankUtility.SOUNDBANKS_INFO_NAME}\"文件不存在, 清理打包声音库目录功能需要此文件, 请在Wwise工程设置中勾选相关选项生成此文件, json或xml皆可, 建议生成json文件.")
                    self.finish_signal.emit("结果", "任务中止", "error")
                    return False, 0, has_json_modified, has_xml_modified

            if os.path.isfile(soundbanks_info_json_path):
                is_json_modified = False
                with open(soundbanks_info_json_path, encoding='utf-8') as json_file:
                    soundbanks_info: dict = json.load(json_file).get("SoundBanksInfo")

                if soundbanks_info.get("RootPaths"):
                    soundbanks_info.pop("RootPaths")
                    is_json_modified = True

                if soundbanks_info.get("FileHash"):
                    soundbanks_info.pop("FileHash")
                    is_json_modified = True

                if soundbanks_info.get("SoundBanks"):
                    for soundbank in soundbanks_info["SoundBanks"]:
                        soundbank: dict
                        if self.cancel_job:
                            self.finish_signal.emit("任务中止", "", "warning")
                            return False, 0, has_json_modified, has_xml_modified
                        soundbank_relative_path: str = soundbank.get("Path")
                        if soundbank.get("Hash"):
                            soundbank.pop("Hash")
                            is_json_modified = True
                        soundbank_relative_path = soundbank_relative_path.replace("\\", "/")
                        soundbank_path = f"{soundbank_dir_path}/{soundbank_relative_path}"
                        new_file_path_set.add(soundbank_path)
                        new_soundbank_path_set.add(soundbank_path)

                        if is_new_soundbanks_info_structure and soundbank.get("Media"):
                            for media in soundbank.get("Media"):
                                media: dict
                                if self.cancel_job:
                                    self.finish_signal.emit("任务中止", "", "warning")
                                    return False, 0, has_json_modified, has_xml_modified
                                if media.get("Streaming") != "true":
                                    continue
                                wem_relative_path: str = media.get("Path")
                                wem_relative_path = wem_relative_path.replace("\\", "/")
                                wem_path = f"{soundbank_dir_path}/{wem_relative_path}"
                                new_file_path_set.add(wem_path)

                if not is_new_soundbanks_info_structure and soundbanks_info.get("StreamedFiles"):
                    for streamed_file in soundbanks_info["StreamedFiles"]:
                        streamed_file: dict
                        if self.cancel_job:
                            self.finish_signal.emit("任务中止", "", "warning")
                            return False, 0, has_json_modified, has_xml_modified
                        wem_name = f"{streamed_file.get('Id')}.wem"
                        wem_language: str = streamed_file.get("Language")
                        if wem_language == "SFX":
                            wem_path = f"{soundbank_dir_path}/{wem_name}"
                        else:
                            wem_path = f"{soundbank_dir_path}/{wem_language}/{wem_name}"
                        new_file_path_set.add(wem_path)

                if is_json_modified:
                    json_object = json.dumps({
                        "SoundBanksInfo": soundbanks_info
                    }, indent=1)
                    with open(soundbanks_info_json_path, "w", encoding="utf-8") as json_file:
                        json_file.write(json_object)
                    has_json_modified = True

            platform_info_json_path = f"{soundbank_dir_path}/{SoundbankUtility.PLATFORM_INFO_NAME}.json"
            if os.path.isfile(platform_info_json_path):
                is_json_modified = False
                with open(platform_info_json_path, encoding='utf-8') as json_file:
                    platform_info: dict = json.load(json_file).get("PlatformInfo")
                if platform_info.get("FileHash"):
                    platform_info.pop("FileHash")
                    is_json_modified = True

                if is_json_modified:
                    json_object = json.dumps({
                        "PlatformInfo": platform_info
                    }, indent=1)
                    with open(platform_info_json_path, "w", encoding="utf-8") as json_file:
                        json_file.write(json_object)
                    has_json_modified = True

            plugin_info_json_path = f"{soundbank_dir_path}/{SoundbankUtility.PLUGIN_INFO_NAME}.json"
            if os.path.isfile(plugin_info_json_path):
                is_json_modified = False
                with open(plugin_info_json_path, encoding='utf-8') as json_file:
                    plugin_info: dict = json.load(json_file).get("PluginInfo")
                if plugin_info.get("FileHash"):
                    plugin_info.pop("FileHash")
                    is_json_modified = True

                if is_json_modified:
                    json_object = json.dumps({
                        "PluginInfo": plugin_info
                    }, indent=1)
                    with open(plugin_info_json_path, "w", encoding="utf-8") as json_file:
                        json_file.write(json_object)
                    has_json_modified = True

            if os.path.isfile(soundbanks_info_xml_path):
                is_xml_modified = False
                soundbanks_info_element = self.read_xml(soundbanks_info_xml_path)
                root_paths_element = soundbanks_info_element.find("./RootPaths")
                if root_paths_element is not None:
                    soundbanks_info_element.remove(root_paths_element)
                    is_xml_modified = True

                file_hash_element = soundbanks_info_element.find("./FileHash")
                if file_hash_element is not None:
                    soundbanks_info_element.remove(file_hash_element)
                    is_xml_modified = True

                soundbank_element_list = soundbanks_info_element.findall("./SoundBanks/SoundBank")
                for soundbank_element in soundbank_element_list:
                    if self.cancel_job:
                        self.finish_signal.emit("任务中止", "", "warning")
                        return False, 0, has_json_modified, has_xml_modified
                    soundbank_relative_path = soundbank_element.find("Path").text
                    if "Hash" in soundbank_element.attrib.keys():
                        soundbank_element.attrib.pop("Hash")
                        is_xml_modified = True
                    soundbank_relative_path = soundbank_relative_path.replace("\\", "/")
                    soundbank_path = f"{soundbank_dir_path}/{soundbank_relative_path}"
                    new_file_path_set.add(soundbank_path)
                    new_soundbank_path_set.add(soundbank_path)
                if is_new_soundbanks_info_structure:
                    streamed_file_element_list = soundbanks_info_element.findall("./SoundBanks/SoundBank/Media/File[@Streaming='true']")
                    for streamed_file_element in streamed_file_element_list:
                        wem_relative_path = streamed_file_element.find("Path").text
                        wem_relative_path = wem_relative_path.replace("\\", "/")
                        wem_path = f"{soundbank_dir_path}/{wem_relative_path}"
                        new_file_path_set.add(wem_path)
                else:
                    streamed_file_element_list = soundbanks_info_element.findall("./StreamedFiles/File")
                    for streamed_file_element in streamed_file_element_list:
                        wem_name = f"{streamed_file_element.get('Id')}.wem"
                        wem_language = streamed_file_element.get("Language")
                        if wem_language == "SFX":
                            wem_path = f"{soundbank_dir_path}/{wem_name}"
                        else:
                            wem_path = f"{soundbank_dir_path}/{wem_language}/{wem_name}"
                        new_file_path_set.add(wem_path)
                if is_xml_modified:
                    self.write_wwise_xml(soundbanks_info_element, soundbanks_info_xml_path)
                    has_xml_modified = True

            platform_info_xml_path = f"{soundbank_dir_path}/PlatformInfo.xml"
            if os.path.isfile(platform_info_xml_path):
                is_xml_modified = False
                platform_info_element = self.read_xml(platform_info_xml_path)

                root_paths_element = platform_info_element.find("./RootPaths")
                if root_paths_element is not None:
                    platform_info_element.remove(root_paths_element)
                    is_xml_modified = True

                file_hash_element = platform_info_element.find("./FileHash")
                if file_hash_element is not None:
                    platform_info_element.remove(file_hash_element)
                    is_xml_modified = True

                if is_xml_modified:
                    self.write_wwise_xml(platform_info_element, platform_info_xml_path)
                    has_xml_modified = True

            plugin_info_xml_path = f"{soundbank_dir_path}/PluginInfo.xml"
            if os.path.isfile(plugin_info_xml_path):
                is_xml_modified = False
                plugin_info_element = self.read_xml(plugin_info_xml_path)

                file_hash_element = plugin_info_element.find("./FileHash")
                if file_hash_element is not None:
                    plugin_info_element.remove(file_hash_element)
                    is_xml_modified = True

                if is_xml_modified:
                    self.write_wwise_xml(plugin_info_element, plugin_info_xml_path)
                    has_xml_modified = True

        if self.get_generate_per_banks_metadata_file(project_id) is True:
            if self.get_generate_xml_metadata(project_id) is True:
                for new_soundbank_path in new_soundbank_path_set:
                    xml_file_path = str(pathlib.PurePosixPath(new_soundbank_path).with_suffix(".xml"))
                    new_file_path_set.add(xml_file_path)
                    if os.path.isfile(xml_file_path):
                        is_xml_modified = False
                        soundbanks_info_element = self.read_xml(xml_file_path)

                        file_hash_element = soundbanks_info_element.find("./FileHash")
                        if file_hash_element is not None:
                            soundbanks_info_element.remove(file_hash_element)
                            is_xml_modified = True

                        soundbank_element_list = soundbanks_info_element.findall("./SoundBanks/SoundBank")
                        for soundbank_element in soundbank_element_list:
                            if "Hash" in soundbank_element.attrib.keys():
                                soundbank_element.attrib.pop("Hash")
                                is_xml_modified = True
                        if is_xml_modified:
                            self.write_wwise_xml(soundbanks_info_element, xml_file_path)
                            has_xml_modified = True

            if self.get_generate_json_metadata(project_id) is True:
                for new_soundbank_path in new_soundbank_path_set:
                    json_file_path = str(pathlib.PurePosixPath(new_soundbank_path).with_suffix(".json"))
                    new_file_path_set.add(json_file_path)
                    if os.path.isfile(json_file_path):
                        is_json_modified = False
                        with open(json_file_path, encoding='utf-8') as json_file:
                            soundbanks_info: dict = json.load(json_file).get("SoundBanksInfo")

                        if soundbanks_info.get("FileHash"):
                            soundbanks_info.pop("FileHash")
                            is_json_modified = True

                        if soundbanks_info.get("SoundBanks"):
                            for soundbank in soundbanks_info["SoundBanks"]:
                                soundbank: dict
                                if soundbank.get("Hash"):
                                    soundbank.pop("Hash")
                                    is_json_modified = True

                        if is_json_modified:
                            json_object = json.dumps({
                                "SoundBanksInfo": soundbanks_info
                            }, indent=1)
                            with open(json_file_path, "w", encoding="utf-8") as json_file:
                                json_file.write(json_object)
                            has_json_modified = True

        delete_file_count = 0

        self.update_progress_text_signal.emit(f"清理文件...")

        generated_soundbank_dir_list = [file.path.replace("\\", "/") for file in os.scandir(generated_soundbank_dir_path) if file.is_dir()]
        for dir_path in generated_soundbank_dir_list:
            if pathlib.Path(dir_path).name == "ExternalSource":
                continue
            if dir_path not in soundbank_dir_path_list:
                exist_file_path_set.update(self.get_files(dir_path))
        delete_file_set = set(exist_file_path_set) - set(new_file_path_set)
        for delete_file in delete_file_set:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return False, delete_file_count, has_json_modified, has_xml_modified
            if self.delete_file(delete_file):
                delete_file_count += 1

        self.remove_empty_directory(generated_soundbank_dir_path)
        return True, delete_file_count, has_json_modified, has_xml_modified
