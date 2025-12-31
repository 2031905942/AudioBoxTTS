import json
import os
import pathlib
import subprocess
import uuid
from os import path
from typing import Optional

import main
from pydub import AudioSegment
from Source.Utility.file_utility import FileUtility


class OVRLipSyncUtility(FileUtility):
    OVRLIPSYNC_APPLICATION_PATH = f"{main.ROOT_PATH}/ThirdParty/OVRLipSync/Windows/OVRLipSync.exe" if main.is_windows_os() else f"{main.ROOT_PATH}/ThirdParty/OVRLipSync/macOS/OVRLipSync"

    def __init__(self, ovr_lip_sync_job):
        super().__init__(ovr_lip_sync_job)

    def check_ovr_lip_sync_validity(self):
        if main.is_windows_os():
            return path.isfile(OVRLipSyncUtility.OVRLIPSYNC_APPLICATION_PATH)
        else:
            try:
                subprocess.run(OVRLipSyncUtility.OVRLIPSYNC_APPLICATION_PATH, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return True
            except FileNotFoundError:
                self.error_signal.emit(f"OVRLipSync应用不存在:\n{OVRLipSyncUtility.OVRLIPSYNC_APPLICATION_PATH}")
                return False

    def export_voice_sample_viseme(self, dir_path: str, tar_path: str):
        if not os.path.isdir(dir_path):
            self.error_signal.emit(f"语音素材目录路径不合法:\n{dir_path}")
            self.finish_signal.emit("结果", "任务中止", "error")
            return

        if not os.path.isdir(dir_path):
            self.error_signal.emit(f"导出视素目录路径不合法:\n{tar_path}")
            self.finish_signal.emit("结果", "任务中止", "error")
            return

        sample_path_list: [str] = self.get_files(dir_path, [".mp3", ".wav"])
        sample_path_list = [x for x in sample_path_list if "Voice Line" in x and "-" not in x]

        if len(sample_path_list) == 0:
            self.finish_signal.emit("结果", "目录内没有满足条件的台本语音素材", "warning")
            return

        self.update_progress_text_signal.emit(f"使用OVRLipSync导出语音素材视素...")
        self.update_progress_total_count_signal.emit(len(sample_path_list))

        process_count: int = 0
        for sample_path in sample_path_list:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            sample_md5 = self.calculate_file_hash(sample_path)
            if sample_md5 is None:
                self.finish_signal.emit("结果", "任务中止", "error")
                return

            viseme_json_name = f"{pathlib.Path(sample_path).stem.replace(' ', '_')}.json"
            viseme_json_path = f"{tar_path}/{viseme_json_name}"
            if os.path.isfile(viseme_json_path):
                with open(viseme_json_path, encoding="utf-8") as json_file:
                    exist_viseme_info = json.load(json_file)
                    if exist_viseme_info["md5"] == sample_md5:
                        continue

            self.update_progress_text_signal.emit(f"使用OVRLipSync导出语音素材视素...\n\"{sample_path}\"")
            viseme_list = self.export_viseme(sample_path)
            if viseme_list is None:
                self.finish_signal.emit("结果", "任务中止", "error")
                return

            new_viseme_info = {}
            new_viseme_info["md5"] = sample_md5
            new_viseme_info["visemes"] = viseme_list
            json_object = json.dumps(new_viseme_info)
            with open(viseme_json_path, "w", encoding="utf-8") as json_file:
                json_file.write(json_object)

            process_count += 1
            self.update_progress_current_count_signal.emit(process_count)

        self.finish_signal.emit("结果", f"使用OVRLipSync导出语音素材视素完成, 共处理{process_count}个语音素材.", "success")

    def export_viseme(self, file_path: str) -> Optional[list]:
        if not self.check_ovr_lip_sync_validity():
            return None
        viseme_list = []
        extension: str = pathlib.Path(file_path).suffix
        convert_audio_file_path = ""
        if extension == ".mp3":
            audio_segment = AudioSegment.from_mp3(file_path)
        else:
            audio_segment = AudioSegment.from_file(file_path)
        if extension == ".mp3" or audio_segment.channels > 1 or audio_segment.sample_width > 2:
            convert_audio_file_name = str(uuid.uuid4())
            convert_audio_file_path = f"{pathlib.Path(file_path).parent}/{convert_audio_file_name}.wav"
            if main.is_windows_os():
                convert_audio_file_path = convert_audio_file_path.replace("/", "\\")
            audio_segment = audio_segment.set_sample_width(2)
            audio_segment = audio_segment.set_channels(1)
            audio_segment.export(convert_audio_file_path, format="wav")
            file_path = convert_audio_file_path

        args = [OVRLipSyncUtility.OVRLIPSYNC_APPLICATION_PATH, "--print-viseme-distribution", file_path]
        popen = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        for stdout_line in iter(popen.stdout.readline, ""):
            viseme_distribution_list = [float(x) for x in stdout_line.strip().split(";")]
            if len(viseme_distribution_list) == 15:
                viseme_distribution_list = viseme_distribution_list[-5:]
                is_all_zero = True
                for viseme_distribution in viseme_distribution_list:
                    if viseme_distribution > 0:
                        is_all_zero = False
                if is_all_zero:
                    viseme_distribution_list = []

                viseme_distribution_dict = {}
                for i in range(len(viseme_distribution_list)):
                    if viseme_distribution_list[i] > 0:
                        viseme_distribution_dict[i] = viseme_distribution_list[i]
                viseme_list.append(viseme_distribution_list)
        popen.stdout.close()
        return_code = popen.wait()
        if convert_audio_file_path != "":
            self.delete_file(convert_audio_file_path)
        if return_code:
            self.error_signal.emit(f'使用OVRLipSync导出语音素材的视素失败"{file_path}":\n{popen.stderr.readline().strip()}')
            return None
        else:
            return viseme_list
