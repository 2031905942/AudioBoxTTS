import os
import pathlib

from PySide6.QtCore import QMutexLocker

import numpy
import pyloudnorm
import soundfile
from pydub import AudioSegment
from pydub.silence import detect_leading_silence
from pyloudnorm import Meter
from Source.Task.base_task import BaseTask
from Source.Utility.base_utility import BaseUtility


class AudioNormalizeTask(BaseTask):
    def __init__(self, utility: BaseUtility, src_path: str, normalize_target_loudness: float):
        super().__init__(utility)
        self.src_path = str(pathlib.PurePosixPath(src_path))
        self.normalize_target_loudness = normalize_target_loudness

    def run(self):
        if not os.path.isfile(self.src_path):
            self.signals.error.emit({
                "message": f"标准化音频\"{self.src_path}\"失败:\n文件路径不合法"
            })
            return
        try:
            # 检查中断标志
            with QMutexLocker(self._lock):
                if not self._is_running:
                    self.signals.interrupted.emit({})
                    return  # 主动终止任务
            extension = pathlib.Path(self.src_path).suffix.lower()
            if extension == ".mp3":
                audio_segment = AudioSegment.from_mp3(self.src_path)
            else:
                audio_segment = AudioSegment.from_file(self.src_path)

            # 移除前后空白
            audio_segment = AudioNormalizeTask.strip_silence(audio_segment)

            # 移除直流偏置
            # audio_segment = audio_segment.remove_dc_offset()
            export_path = str(pathlib.PurePosixPath(self.src_path).with_suffix(".wav"))
            audio_segment.export(export_path, format="wav")
            if export_path.lower() != self.src_path.lower():
                os.remove(self.src_path)

            # 响度标准化
            audio_data, sample_rate = soundfile.read(export_path)
            audio_info = soundfile.info(export_path)
            audio_duration = audio_info.duration
            block_size = min(0.400, audio_duration)

            block_size = AudioNormalizeTask.my_floor(block_size, 2)
            loudness_meter = Meter(sample_rate, block_size=block_size)  # create BS.1770 meter
            loudness = loudness_meter.integrated_loudness(audio_data)

            audio_data = pyloudnorm.normalize.loudness(audio_data, loudness, self.normalize_target_loudness)

            soundfile.write(export_path, audio_data, sample_rate)
            self.signals.finished.emit({})
        except Exception as exception:
            self.signals.error.emit({
                "message": f"标准化音频\"{self.src_path}\"发生异常:\n{exception}"
            })

    @staticmethod
    def trim_leading_silence(x: AudioSegment) -> AudioSegment:
        return x[detect_leading_silence(x, silence_threshold=-60, chunk_size=5):]

    @staticmethod
    def trim_trailing_silence(x: AudioSegment) -> AudioSegment:
        return AudioNormalizeTask.trim_leading_silence(x.reverse()).reverse()

    @staticmethod
    def strip_silence(x: AudioSegment) -> AudioSegment:
        return AudioNormalizeTask.trim_trailing_silence(AudioNormalizeTask.trim_leading_silence(x))

    @staticmethod
    def my_floor(a, precision=0):
        return numpy.true_divide(numpy.floor(a * 10 ** precision), 10 ** precision)
