import os
import shutil
import subprocess
from os import path
from pathlib import Path
from typing import Optional

import main
from Source.Utility.config_utility import config_utility, ProjectData
from Source.Utility.file_utility import FileUtility
from Source.Utility.wproj_utility import WprojUtility
from Source.Utility.xml_utility import XmlUtility


class ExternalSourceUtility(FileUtility, XmlUtility):
    CRC_LOOKUP = [
        0x00000000, 0x04c11db7, 0x09823b6e, 0x0d4326d9, 0x130476dc, 0x17c56b6b, 0x1a864db2, 0x1e475005,
        0x2608edb8, 0x22c9f00f, 0x2f8ad6d6, 0x2b4bcb61, 0x350c9b64, 0x31cd86d3, 0x3c8ea00a, 0x384fbdbd,
        0x4c11db70, 0x48d0c6c7, 0x4593e01e, 0x4152fda9, 0x5f15adac, 0x5bd4b01b, 0x569796c2, 0x52568b75,
        0x6a1936c8, 0x6ed82b7f, 0x639b0da6, 0x675a1011, 0x791d4014, 0x7ddc5da3, 0x709f7b7a, 0x745e66cd,
        0x9823b6e0, 0x9ce2ab57, 0x91a18d8e, 0x95609039, 0x8b27c03c, 0x8fe6dd8b, 0x82a5fb52, 0x8664e6e5,
        0xbe2b5b58, 0xbaea46ef, 0xb7a96036, 0xb3687d81, 0xad2f2d84, 0xa9ee3033, 0xa4ad16ea, 0xa06c0b5d,
        0xd4326d90, 0xd0f37027, 0xddb056fe, 0xd9714b49, 0xc7361b4c, 0xc3f706fb, 0xceb42022, 0xca753d95,
        0xf23a8028, 0xf6fb9d9f, 0xfbb8bb46, 0xff79a6f1, 0xe13ef6f4, 0xe5ffeb43, 0xe8bccd9a, 0xec7dd02d,
        0x34867077, 0x30476dc0, 0x3d044b19, 0x39c556ae, 0x278206ab, 0x23431b1c, 0x2e003dc5, 0x2ac12072,
        0x128e9dcf, 0x164f8078, 0x1b0ca6a1, 0x1fcdbb16, 0x018aeb13, 0x054bf6a4, 0x0808d07d, 0x0cc9cdca,
        0x7897ab07, 0x7c56b6b0, 0x71159069, 0x75d48dde, 0x6b93dddb, 0x6f52c06c, 0x6211e6b5, 0x66d0fb02,
        0x5e9f46bf, 0x5a5e5b08, 0x571d7dd1, 0x53dc6066, 0x4d9b3063, 0x495a2dd4, 0x44190b0d, 0x40d816ba,
        0xaca5c697, 0xa864db20, 0xa527fdf9, 0xa1e6e04e, 0xbfa1b04b, 0xbb60adfc, 0xb6238b25, 0xb2e29692,
        0x8aad2b2f, 0x8e6c3698, 0x832f1041, 0x87ee0df6, 0x99a95df3, 0x9d684044, 0x902b669d, 0x94ea7b2a,
        0xe0b41de7, 0xe4750050, 0xe9362689, 0xedf73b3e, 0xf3b06b3b, 0xf771768c, 0xfa325055, 0xfef34de2,
        0xc6bcf05f, 0xc27dede8, 0xcf3ecb31, 0xcbffd686, 0xd5b88683, 0xd1799b34, 0xdc3abded, 0xd8fba05a,
        0x690ce0ee, 0x6dcdfd59, 0x608edb80, 0x644fc637, 0x7a089632, 0x7ec98b85, 0x738aad5c, 0x774bb0eb,
        0x4f040d56, 0x4bc510e1, 0x46863638, 0x42472b8f, 0x5c007b8a, 0x58c1663d, 0x558240e4, 0x51435d53,
        0x251d3b9e, 0x21dc2629, 0x2c9f00f0, 0x285e1d47, 0x36194d42, 0x32d850f5, 0x3f9b762c, 0x3b5a6b9b,
        0x0315d626, 0x07d4cb91, 0x0a97ed48, 0x0e56f0ff, 0x1011a0fa, 0x14d0bd4d, 0x19939b94, 0x1d528623,
        0xf12f560e, 0xf5ee4bb9, 0xf8ad6d60, 0xfc6c70d7, 0xe22b20d2, 0xe6ea3d65, 0xeba91bbc, 0xef68060b,
        0xd727bbb6, 0xd3e6a601, 0xdea580d8, 0xda649d6f, 0xc423cd6a, 0xc0e2d0dd, 0xcda1f604, 0xc960ebb3,
        0xbd3e8d7e, 0xb9ff90c9, 0xb4bcb610, 0xb07daba7, 0xae3afba2, 0xaafbe615, 0xa7b8c0cc, 0xa379dd7b,
        0x9b3660c6, 0x9ff77d71, 0x92b45ba8, 0x9675461f, 0x8832161a, 0x8cf30bad, 0x81b02d74, 0x857130c3,
        0x5d8a9099, 0x594b8d2e, 0x5408abf7, 0x50c9b640, 0x4e8ee645, 0x4a4ffbf2, 0x470cdd2b, 0x43cdc09c,
        0x7b827d21, 0x7f436096, 0x7200464f, 0x76c15bf8, 0x68860bfd, 0x6c47164a, 0x61043093, 0x65c52d24,
        0x119b4be9, 0x155a565e, 0x18197087, 0x1cd86d30, 0x029f3d35, 0x065e2082, 0x0b1d065b, 0x0fdc1bec,
        0x3793a651, 0x3352bbe6, 0x3e119d3f, 0x3ad08088, 0x2497d08d, 0x2056cd3a, 0x2d15ebe3, 0x29d4f654,
        0xc5a92679, 0xc1683bce, 0xcc2b1d17, 0xc8ea00a0, 0xd6ad50a5, 0xd26c4d12, 0xdf2f6bcb, 0xdbee767c,
        0xe3a1cbc1, 0xe760d676, 0xea23f0af, 0xeee2ed18, 0xf0a5bd1d, 0xf464a0aa, 0xf9278673, 0xfde69bc4,
        0x89b8fd09, 0x8d79e0be, 0x803ac667, 0x84fbdbd0, 0x9abc8bd5, 0x9e7d9662, 0x933eb0bb, 0x97ffad0c,
        0xafb010b1, 0xab710d06, 0xa6322bdf, 0xa2f33668, 0xbcb4666d, 0xb8757bda, 0xb5365d03, 0xb1f740b4
    ]

    OPUS_ENCODER_PATH = f"{main.ROOT_PATH}/ThirdParty/Opus/Windows/opusenc.exe" if main.is_windows_os() else f"{main.ROOT_PATH}/ThirdParty/Opus/macOS/opusenc"
    SUPPORT_AUDIO_FORMAT_LIST = [".aiff", ".flac", ".ogg", ".wav"]

    @staticmethod
    def check_opus_encoder_validity():
        return path.isfile(ExternalSourceUtility.OPUS_ENCODER_PATH)

    def convert_project_external_source_job(self, project_id: str):
        self.update_progress_text_signal.emit(f"读取Wwise工程信息...")
        wwise_project_path: str = config_utility.get_config(ProjectData.WWISE_PROJECT_PATH, project_id)
        wwise_project_dir_path = os.path.dirname(wwise_project_path)
        wproj_root_element = self.read_xml(wwise_project_path)
        if not wproj_root_element:
            self.finish_signal.emit("转码项目外部源任务中止", "", "error")
            return

        original_sample_dir_path = WprojUtility.get_original_sample_path(wproj_root_element)
        external_source_dir_path = f"{wwise_project_dir_path}/{original_sample_dir_path}/ExternalSource"

        self.remove_empty_directory(external_source_dir_path)
        source_audio_path_list = self.get_files(external_source_dir_path, ExternalSourceUtility.SUPPORT_AUDIO_FORMAT_LIST)
        source_audio_relative_path_dict = {}
        for source_audio_path in source_audio_path_list:
            source_audio_relative_path = source_audio_path[len(external_source_dir_path) + 1:]
            source_audio_relative_path_stem = str(Path(source_audio_relative_path).with_suffix(""))
            if source_audio_relative_path_stem not in source_audio_relative_path_dict:
                source_audio_relative_path_dict[source_audio_relative_path_stem] = source_audio_relative_path

        wwopus_dir_path = f"{wwise_project_dir_path}/GeneratedSoundBanks/ExternalSource"

        if len(source_audio_path_list) == 0:
            if path.isdir(wwopus_dir_path):
                shutil.rmtree(wwopus_dir_path)
            self.finish_signal.emit("转码项目外部源任务完成", "没有找到外部源, 删除所有外部源转码目录.", "warning")
            return

        wwopus_path_list = self.get_files(wwopus_dir_path, [".wwopus"])
        wwopus_relative_stem_path_set = set([str(Path(x[len(wwopus_dir_path) + 1:]).with_suffix("")) for x in wwopus_path_list])

        source_audio_relative_stem_path_set = set(source_audio_relative_path_dict.keys())
        new_audio_relative_stem_path_set = source_audio_relative_stem_path_set - wwopus_relative_stem_path_set
        remove_wwopus_relative_stem_path_set = wwopus_relative_stem_path_set - source_audio_relative_stem_path_set
        sync_audio_relative_stem_path_set = source_audio_relative_stem_path_set & wwopus_relative_stem_path_set

        self.update_progress_text_signal.emit(f"转码项目外部源...")
        for remove_wwopus_relative_stem_path in remove_wwopus_relative_stem_path_set:
            os.remove(f"{wwopus_dir_path}/{remove_wwopus_relative_stem_path}.wwopus")

        for sync_audio_relative_stem_path in sync_audio_relative_stem_path_set:
            sync_audio_relative_path = source_audio_relative_path_dict[sync_audio_relative_stem_path]
            sync_audio_path = f"{external_source_dir_path}/{sync_audio_relative_path}"
            audio_hash = self.calculate_file_hash(sync_audio_path)
            if not audio_hash:
                self.finish_signal.emit("转码项目外部源任务中止", "", "error")
                return
            wwopus_path = str(Path(f"{wwopus_dir_path}/{sync_audio_relative_path}").with_suffix(".wwopus"))
            with open(wwopus_path, 'rb') as file:
                file_content = file.read()
            opus_tags_page_content_offset = file_content.find(b"OpusTags")
            if opus_tags_page_content_offset >= 0:
                vendor_string_length_offset = opus_tags_page_content_offset + 8
                vendor_string_length = int.from_bytes(file_content[vendor_string_length_offset: vendor_string_length_offset + 4], "little")
                vendor_string_offset = opus_tags_page_content_offset + 12
                opus_hash = file_content[vendor_string_offset: vendor_string_offset + vendor_string_length].decode("utf-8")
                if audio_hash == opus_hash:
                    continue
            new_audio_relative_stem_path_set.add(sync_audio_relative_stem_path)

        for new_audio_relative_stem_path in new_audio_relative_stem_path_set:
            new_audio_relative_path = source_audio_relative_path_dict[new_audio_relative_stem_path]
            new_audio_path = f"{external_source_dir_path}/{new_audio_relative_path}"
            audio_hash = self.calculate_file_hash(new_audio_path)
            if not audio_hash:
                self.finish_signal.emit("转码项目外部源任务中止", "", "error")
                return
            wwopus_path = str(Path(f"{wwopus_dir_path}/{new_audio_relative_path}").with_suffix(".wwopus"))
            if path.isfile(wwopus_path):
                os.remove(wwopus_path)
            if not path.isdir(Path(wwopus_path).parent):
                os.makedirs(Path(wwopus_path).parent, exist_ok=True)
            if not self.convert_audio_to_opus(new_audio_path, wwopus_path):
                self.finish_signal.emit("转码项目外部源任务中止", "", "error")
                return

            with open(wwopus_path, 'rb') as file:
                file_content = file.read()

            # 将源音频的哈希值写入Opus的标签头中
            opus_tags_page_content = b"OpusTags"
            opus_tags_page_content += (len(audio_hash)).to_bytes(4, "little")
            opus_tags_page_content += audio_hash.encode("utf-8")
            opus_tags_page_content += int(0).to_bytes(4, "little")
            file_content = ExternalSourceUtility._set_ogg_page_content(file_content, opus_tags_page_content, 1)

            opus_head_page_content = ExternalSourceUtility._get_ogg_page_content(file_content, 0)
            channel_count_offset = 9
            channel_count = int.from_bytes(opus_head_page_content[channel_count_offset:channel_count_offset + 1], "little")

            sample_count = self._get_opus_sample_count(file_content)

            # 构造Wwise的文件头
            opus_content_size = len(file_content)
            file_content = opus_content_size.to_bytes(4, "little") + file_content
            file_content = b"data" + file_content

            # 构造Wave的文件头
            wave_header_content = b"WAVEfmt "
            wave_header_content += (36).to_bytes(4, "little")
            wave_header_content += (0x3040).to_bytes(2, "little")  # Opus格式的枚举值
            wave_header_content += channel_count.to_bytes(2, "little")  # 通道数
            wave_header_content += (48000).to_bytes(4, "little")  # 采样率, Opus固定为48000
            wave_header_content += (0).to_bytes(4, "little")  # 平均比特率暂时设为0
            wave_header_content += (0).to_bytes(4, "little")  # Block Size和Bits Per Sample均为0
            wave_header_content += (18).to_bytes(2, "little")  # Wwise包含额外的信息在Wave文件头, Extra Size固定为18
            wave_header_content += (0).to_bytes(2, "little")  # 2个字节的空白位
            wave_header_content += channel_count.to_bytes(1, "little")  # 通道数(uNumChannels)
            config_type = 0x1  # eConfigType (0=none, 1=standard, 2=ambisonic)
            channel_mask = 0x3 if channel_count == 2 else 0x4
            channel_layout = (config_type | (channel_mask << 4)).to_bytes(1, "little")
            wave_header_content += channel_layout
            wave_header_content += (0).to_bytes(2, "little")  # 2个字节的空白位
            wave_header_content += sample_count.to_bytes(8, "little")  # 音频的采样总数
            wave_header_content += (0).to_bytes(4, "little")  # 4个字节的空白位
            file_content = wave_header_content + file_content

            # 构建Riff文件头
            wave_content_size = len(file_content)
            file_content = wave_content_size.to_bytes(4, "little") + file_content
            file_content = b"RIFF" + file_content

            with open(wwopus_path, 'wb') as file:
                file.write(file_content)

        self.remove_empty_directory(wwopus_dir_path)

        self.finish_signal.emit("转码项目外部源任务完成", "", "success")

    def convert_audio_to_opus(self, source_audio_path: str, target_audio_path: str):
        if not ExternalSourceUtility.check_opus_encoder_validity():
            self.error_signal.emit(f"Opus转码失败\nOpus编码器不存在: \"{ExternalSourceUtility.OPUS_ENCODER_PATH}\"")
            return False

        if not path.isfile(source_audio_path):
            self.error_signal.emit(f"Opus转码失败\n源音频不存在: \"{source_audio_path}\"")
            return False

        source_audio_file_suffix = Path(source_audio_path).suffix.lower()
        if source_audio_file_suffix not in ExternalSourceUtility.SUPPORT_AUDIO_FORMAT_LIST:
            self.error_signal.emit(f"Opus转码失败\n源音频格式不支持: \"{source_audio_file_suffix}\", 仅支持{ExternalSourceUtility.SUPPORT_AUDIO_FORMAT_LIST}")
            return False

        if path.isfile(target_audio_path):
            os.remove(target_audio_path)

        args = [ExternalSourceUtility.OPUS_ENCODER_PATH, "--downmix-stereo", "--discard-comments", "--discard-pictures", source_audio_path, target_audio_path]
        process = subprocess.run(args, capture_output=True)
        if process.returncode != 0:
            self.error_signal.emit(f"Opus转码失败\n源音频文件\"{source_audio_path}\": {process.stderr}")
            return False
        return True

    def _get_opus_sample_count(self, file_content: bytes) -> Optional[int]:
        current_offset = 0
        sample_count = 0
        while current_offset < len(file_content):
            if file_content[current_offset: current_offset + 4] == b"OggS":
                position_offset = current_offset + 6
                position = int.from_bytes(file_content[position_offset: position_offset + 8], "little")
                sample_count = position
                number_page_segments_offset = current_offset + 26
                number_page_segments = int.from_bytes(file_content[number_page_segments_offset: number_page_segments_offset + 1], "little")
                segment_table_offset = current_offset + 27
                page_content_offset = current_offset + 27 + number_page_segments
                page_content_size = 0
                for j in range(0, number_page_segments):
                    page_content_size += int.from_bytes(file_content[segment_table_offset + j:segment_table_offset + j + 1], "little")
                current_offset = page_content_offset + page_content_size
                if current_offset >= len(file_content):
                    return sample_count
            else:
                return None

    @staticmethod
    def _get_ogg_page_content(file_content: bytes, page_sequence_number: int) -> Optional[bytes]:
        current_offset = 0
        for i in range(0, page_sequence_number + 1):
            if file_content[current_offset: current_offset + 4] == b"OggS":
                number_page_segments_offset = current_offset + 26
                number_page_segments = int.from_bytes(file_content[number_page_segments_offset: number_page_segments_offset + 1], "little")
                segment_table_offset = current_offset + 27
                page_content_offset = current_offset + 27 + number_page_segments
                page_content_size = 0
                for j in range(0, number_page_segments):
                    page_content_size += int.from_bytes(file_content[segment_table_offset + j:segment_table_offset + j + 1], "little")
                if i == page_sequence_number:
                    return file_content[page_content_offset: page_content_offset + page_content_size]
                else:
                    current_offset = page_content_offset + page_content_size
                    if current_offset >= len(file_content):
                        return None
            else:
                return None

    @staticmethod
    def _set_ogg_page_content(file_content: bytes, page_content: bytes, page_sequence_number: int, header_type: Optional[int] = None, granule_position: Optional[int] = None) -> Optional[bytes]:
        current_offset = 0
        file_content_bytearray = bytearray(file_content)
        for i in range(0, page_sequence_number + 1):
            if file_content_bytearray[current_offset: current_offset + 4] == b"OggS":
                number_page_segments_offset = current_offset + 26
                segment_table_offset = current_offset + 27
                number_page_segments = int.from_bytes(file_content_bytearray[number_page_segments_offset: number_page_segments_offset + 1], "little")
                page_content_offset = current_offset + 27 + number_page_segments
                page_content_size = 0
                for j in range(0, number_page_segments):
                    page_content_size += int.from_bytes(file_content_bytearray[segment_table_offset + j:segment_table_offset + j + 1], "little")
                if i == page_sequence_number:  # 找到当前页
                    # 设置页头类型
                    if header_type is not None:
                        header_type_offset = current_offset + 5
                        file_content_bytearray[header_type_offset: header_type_offset + 1] = int(header_type).to_bytes(1, "little")
                    # 设置位置信息
                    if granule_position is not None:
                        granule_position_offset = current_offset + 6
                        file_content_bytearray[granule_position_offset: granule_position_offset + 8] = int(granule_position).to_bytes(8, "little")
                    # 先将CRC校验位设零
                    crc_checksum_offset = current_offset + 22
                    file_content_bytearray[crc_checksum_offset: crc_checksum_offset + 4] = int(0).to_bytes(4, "little")
                    # 将内容删除
                    file_content_bytearray[page_content_offset: page_content_offset + page_content_size] = b""
                    # 将片段表删除
                    file_content_bytearray[segment_table_offset: segment_table_offset + number_page_segments] = b""
                    # 计算要设置的页内容的长度
                    page_content_size = len(page_content)
                    k = 1
                    # 求片段表
                    segment_table = b""
                    while k * 0xff < page_content_size:
                        segment_table += int(0xff).to_bytes(1, "little")
                        k += 1
                    number_page_segments = k
                    segment_table += (page_content_size - (number_page_segments - 1) * 0xff).to_bytes(1, "little")
                    # 设置页片段数量
                    file_content_bytearray[number_page_segments_offset: number_page_segments_offset + 1] = int(number_page_segments).to_bytes(1, "little")
                    # 设置页片段表
                    file_content_bytearray[segment_table_offset: segment_table_offset] = segment_table
                    # 设置新的页内容
                    page_content_offset = current_offset + 27 + number_page_segments
                    file_content_bytearray[page_content_offset: page_content_offset] = page_content
                    # 计算并新的CRC校验
                    new_crc_checksum = ExternalSourceUtility._get_oggs_checksum(file_content_bytearray[current_offset: page_content_offset + page_content_size]).to_bytes(4, "little")
                    file_content_bytearray[crc_checksum_offset: crc_checksum_offset + 4] = new_crc_checksum
                    return bytes(file_content_bytearray)
                else:
                    current_offset = page_content_offset + page_content_size
                    if current_offset >= len(file_content):
                        return None
            else:
                return None

    @staticmethod
    def _get_oggs_checksum(content: bytearray) -> int:
        crc_reg = 0
        for i in range(0, len(content)):
            crc_reg = (crc_reg << 8 & 0xffffffff) ^ ExternalSourceUtility.CRC_LOOKUP[((crc_reg >> 24) & 0xff) ^ content[i]]
        return crc_reg
