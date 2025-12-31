import os
import time
from typing import Optional

from PySide6.QtCore import Signal

# noinspection PyPackageRequirements
from Source.Task.audio_normalize_task import AudioNormalizeTask
from Source.Utility.config_utility import config_utility
from Source.Utility.file_utility import FileUtility


class SampleUtility(FileUtility):
    NORMALIZE_TARGET_LOUDNESS_CONFIG_NAME = "NormalizeTargetLoudness"
    """ 标准化目标响度设置名 (dB LUFS) """

    LOUDNESS_STANDARD_DICT: {
        str: int
    } = {
        "-24 LKFS (ITU-R BS.1770-4)": -24,
        "-23 LUFS (EBU R128)":        -23,
        "-18 LUFS (EBU R128 S2)":     -18,
        "-16 LUFS (Apple Music)":     -16,
        "-14 LUFS (Youtube)":         -14,
        "-12 LUFS":                   -12
    }

    DEFAULT_NORMALIZED_LOUDNESS: int = -23

    # 信号定义
    show_check_list_window_signal = Signal(str, list)

    def __init__(self, sample_job):
        from Source.Job.sample_job import SampleJob
        sample_job: SampleJob
        super().__init__(sample_job)

    def normalize_sample(self, dir_path: str):
        start_time = time.time()
        if not os.path.isdir(dir_path):
            self.error_signal.emit(f"素材目录路径不合法:\n{dir_path}")
            self.finish_signal.emit("结果", "任务中止", "error")
            return

        sample_path_list = self.get_files(dir_path, [".wav", ".flac", ".aac", ".m4a", ".mp3", ".ogg", ".opus", ".wma", ".ac3"])

        if len(sample_path_list) == 0:
            self.finish_signal.emit("结果", "目录内没有素材", "warning")
            return

        if not self.backup_directory(dir_path):
            self.finish_signal.emit("结果", "任务中止", "error")
            return

        self.update_progress_text_signal.emit(f"标准化素材...")
        self.total_task_count = len(sample_path_list)
        self.update_progress_total_count_signal.emit(self.total_task_count)

        normalize_target_loudness: Optional[int] = config_utility.get_config(SampleUtility.NORMALIZE_TARGET_LOUDNESS_CONFIG_NAME)
        if not normalize_target_loudness:
            normalize_target_loudness = SampleUtility.DEFAULT_NORMALIZED_LOUDNESS

        for sample_path in sample_path_list:
            task = AudioNormalizeTask(self, sample_path, normalize_target_loudness)
            self.active_task_list.append(task)

        self.remove_empty_directory(dir_path)

        def __on_all_task_finished():
            self.remove_empty_directory(dir_path)
            end_time = time.time()
            print(f"标准化素材" + " 耗时: {:.3f}秒;".format(end_time - start_time))
            self.finish_signal.emit("结果", f"标准化素材完成, 共处理{self.total_task_count}个素材.", "success")

        self.on_all_task_finished = __on_all_task_finished

        self.completed_task_count = 0
        self.start_all_task()

    def update_wwise_project_sample_job(self, update_sample_dir_path: str, wwise_project_sample_dir_path: str):
        self.update_progress_text_signal.emit("收集更新素材...")
        update_sample_path_list: [str] = self.get_files(update_sample_dir_path, [".wav"])
        if len(update_sample_path_list) == 0:
            self.finish_signal.emit("结果", "目录内没有素材", "warning")
            return

        update_sample_path_dict: {
            str: str
        } = {}
        sample_check_list: [(str, bool)] = []
        for update_sample_path in update_sample_path_list:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            sample_name: str = os.path.basename(update_sample_path)
            if sample_name not in update_sample_path_dict.keys():
                update_sample_path_dict[sample_name] = [update_sample_path]
            else:
                update_sample_path_dict[sample_name].append(update_sample_path)

        self.update_progress_text_signal.emit("检查更新素材合法性...")
        for update_sample_name, update_sample_path_list in update_sample_path_dict.items():
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            if len(update_sample_path_list) == 1:
                continue
            for update_sample_path in update_sample_path_list:
                check_str: str = f"素材\"{update_sample_name}\"重复, 请确保唯一性: 路径\"{update_sample_path}\"."
                sample_check_list.append((check_str, False))

        if len(sample_check_list) > 0:
            self.show_check_list_window_signal.emit("素材问题", sample_check_list)
            self.finish_signal.emit("结果", "任务中止, 请先排查完素材的问题再执行", "warning")
            return

        self.update_progress_total_count_signal.emit(len(update_sample_path_dict))

        self.backup_directory(update_sample_dir_path)

        if self.cancel_job:
            self.finish_signal.emit("任务中止", "", "warning")
            return

        self.update_progress_text_signal.emit("收集Wwise工程素材...")
        wwise_project_sample_path_list: [str] = self.get_files(wwise_project_sample_dir_path, [".wav"])

        wwise_project_sample_path_dict: {
            str: [str]
        } = {}
        for wwise_project_sample_path in wwise_project_sample_path_list:
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            sample_name: str = os.path.basename(wwise_project_sample_path)
            if sample_name not in wwise_project_sample_path_dict.keys():
                wwise_project_sample_path_dict[sample_name] = [wwise_project_sample_path]
            else:
                wwise_project_sample_path_dict[sample_name].append(wwise_project_sample_path)

        sample_not_found_dir_path = f"{update_sample_dir_path}/未找到的素材"
        sample_not_changed_dir_path = f"{update_sample_dir_path}/不需要更新的素材"
        sample_updated_dir_path = f"{update_sample_dir_path}/成功更新的素材"

        current_count: int = 0
        update_count: int = 0
        not_changed_count: int = 0
        not_found_count: int = 0
        for update_sample_name, update_sample_path_list in update_sample_path_dict.items():
            if self.cancel_job:
                self.finish_signal.emit("任务中止", "", "warning")
                return
            self.update_progress_text_signal.emit(f"更新素材...\n\"{update_sample_name}\"")
            if update_sample_name in wwise_project_sample_path_dict.keys():
                src_sample_path: str = update_sample_path_list[0]
                is_update: bool = False
                for wwise_project_sample_path in wwise_project_sample_path_dict[update_sample_name]:
                    result, is_copy = self.sync_file(src_sample_path, wwise_project_sample_path, False)
                    if not result:
                        self.finish_signal.emit("结果", "任务中止", "error")
                        return
                    if is_copy:
                        is_update = True
                        update_count += 1
                    else:
                        not_changed_count += 1

                if is_update:
                    dst_sample_path: str = f"{sample_updated_dir_path}/{update_sample_name}"
                else:
                    dst_sample_path: str = f"{sample_not_changed_dir_path}/{update_sample_name}"
                if not self.move_file(src_sample_path, dst_sample_path):
                    self.finish_signal.emit("结果", "任务中止", "error")
                    return
            else:
                not_found_count += 1
                src_sample_path: str = update_sample_path_list[0]
                dst_sample_path: str = f"{sample_not_found_dir_path}/{update_sample_name}"
                if not self.move_file(src_sample_path, dst_sample_path):
                    self.finish_signal.emit("结果", "任务中止", "error")
                    return
            current_count += 1
            self.update_progress_current_count_signal.emit(current_count)

        self.remove_empty_directory(update_sample_dir_path)

        result_content_str: str = f"更新Wwise工程素材完成"
        if update_count > 0:
            result_content_str += f"\n更新了{update_count}个素材"
        else:
            result_content_str += f"\n没有变动"

        self.finish_signal.emit("结果", result_content_str, "success")
