'''
import base64
import json
import os.path
import pathlib
import uuid

from PySide6.QtCore import Signal

import requests
import torch
import torchaudio
from Source.TTS.Utility.Text import cleaners
from Source.Utility import tts_config_utility
from Source.Utility.tts_config_utility import VoiceData
from Source.Utility.voice_excel_utility import VoiceExcelUtility
from TTS.api import TTS
from TTS.tts.models.xtts import Xtts
from TTS.tts.utils.fairseq import rehash_fairseq_vits_checkpoint
from TTS.utils.audio.numpy_transforms import save_wav
from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer
from pydub import AudioSegment
from torch import LongTensor

APPID = "8zf98msantbsgrpy"
ACCESS_TOKEN = "QpeqeploYv2sGhHs80MpGR7C269qk_aj"
CLUSTER = "general"

VOICE_TYPE = "VOV301_bytesing3_yinyoushiren"
HOST = "speech.bytedance.com"
API_URL = f"https://{HOST}/api/v1/tts"

HTTP_HEADER = {
    "Authorization": f"Bearer;{ACCESS_TOKEN}"
}


class TTSUtility(VoiceExcelUtility):
    cache_synthesizer_signal = Signal(str, object)

    def __init__(self, voice_job, synthesizer_dict: dict[str:Synthesizer]):
        super().__init__(voice_job)
        self.xtts = synthesizer_dict.get("xtts", None)
        self.vits = synthesizer_dict.get("vits", None)
        # self.bark = synthesizer_dict.get("bark", None)
        # self.freevc = synthesizer_dict.get("freevc", None)

    def generate_lyric_audio(self, excel_path: str, generate_dir_path: str):
        self.update_progress_text_signal.emit(f"读取歌词工作簿...\n\"{excel_path}\"")
        workbook = self.load_workbook(excel_path)
        if not workbook:
            # self._print_log_error(f"无法加载工作簿: \"{excel_file_path}\".")
            self.finish_signal.emit("结果", "任务中止", "error")
            return

        worksheet_index = 0
        lyric_info_list = []
        for worksheet in workbook.worksheets:
            lyric_info_list.append({})
            lyric_info_list[worksheet_index]["lyric_dict"] = {}
            last_column = worksheet.max_column
            while not self.get_cell_value(worksheet, 1, last_column):
                last_column -= 1
            start_time = self.get_cell_value(worksheet, 1, last_column - 1)
            end_time = self.get_cell_value(worksheet, 1, last_column)
            for row in range(2, worksheet.max_row + 1):
                resource_name = self.get_cell_value(worksheet, row, 2)
                lyric = self.get_cell_value(worksheet, row, 3)
                if resource_name and lyric and start_time and end_time:
                    lyric_info_list[worksheet_index]["lyric_dict"][resource_name] = lyric
                    lyric_info_list[worksheet_index]["start_time"] = int(start_time)
                    lyric_info_list[worksheet_index]["end_time"] = int(end_time)
            worksheet_index += 1

        total_count = 0
        for lyric_info in lyric_info_list:
            lyric_dict = lyric_info.get("lyric_dict", {})
            if len(lyric_dict.keys()) > total_count:
                total_count = len(lyric_dict.keys())
        self.update_progress_total_count_signal.emit(total_count)

        current_count = 0
        for _ in range(total_count):
            if self.cancel_job:
                self.finish_signal.emit("结果", "歌词音频合成中止", "warning")
                return
            resource_concat_str = ""
            total_lyric = ""
            generate_file_name = ""
            for lyric_info in lyric_info_list:
                lyric_dict = lyric_info.get("lyric_dict", {})
                resource_name = list(lyric_dict.keys())[0]
                resource_concat_str = f"{resource_concat_str}\n{resource_name}"
                if not generate_file_name:
                    generate_file_name = resource_name
                else:
                    generate_file_name = f"{generate_file_name}+{resource_name}"
                lyric = lyric_dict[resource_name]
                if not total_lyric:
                    total_lyric = lyric
                else:
                    total_lyric = f"{total_lyric}\n{lyric}"
                if len(lyric_dict.keys()) > 1:
                    lyric_dict.pop(resource_name)

            total_lyric = total_lyric.replace("\n", " ")

            generate_file_name = f"{generate_file_name}"
            generate_file_path = f"{generate_dir_path}/{generate_file_name}.wav"
            self.update_progress_text_signal.emit(f"音频合成...\n{generate_file_name}\n词句ID:{resource_concat_str}")
            request_json = {
                "app":     {
                    "appid":   APPID,
                    "token":   "access_token",
                    "cluster": CLUSTER
                },
                "user":    {
                    "uid": "Dragonheir: Silent Gods"
                },
                "audio":   {
                    "voice_type": VOICE_TYPE,
                    "encoding":   "wav",
                },
                "request": {
                    "reqid":            str(uuid.uuid4()),
                    "text":             total_lyric,
                    "operation":        "query",
                    "with_frontend":    1,
                    "frontend_type":    "unitTson",
                    "pure_english_opt": 1,
                    "skip_bgm":         True
                }
            }

            try:
                resp = requests.post(API_URL, json.dumps(request_json), headers=HTTP_HEADER)
                print(f"resp body: \n{resp.json()}")
                if "data" in resp.json():
                    data = resp.json()["data"]
                    file_to_save = open(generate_file_path, "wb")
                    file_to_save.write(base64.b64decode(data))
                    file_to_save.close()
                    audio_file = AudioSegment.from_wav(generate_file_path)
                    sentence_time_list = []
                    audio_file_name_list = generate_file_name.split("+")
                    for i in range(len(lyric_info_list)):
                        lyric_info = lyric_info_list[i]
                        audio_file_name = audio_file_name_list[i]
                        start_time = int(lyric_info["start_time"])
                        end_time = int(lyric_info["end_time"])
                        sentence_time_list.append((start_time, end_time, audio_file_name))
                    for start_time, end_time, audio_file_name in sentence_time_list:
                        new_audio_file = audio_file[start_time: end_time]
                        new_audio_file_name = f"VO S1Report {audio_file_name}"
                        new_audio_file_path = f"{generate_dir_path}/{new_audio_file_name}.wav"
                        index = 1
                        while os.path.isfile(new_audio_file_path):
                            new_audio_file_path = f"{generate_dir_path}/{new_audio_file_name}-{index}.wav"
                            index += 1
                        new_audio_file.export(new_audio_file_path, format="wav")

            except Exception as error:
                self.error_signal.emit(f"歌词音频合成发生异常:\n{error}")
                # self._print_log_error(f"歌词音频合成发生异常: {traceback.format_exc()}.")

            current_count += 1
            self.update_progress_current_count_signal.emit(current_count)

        self.finish_signal.emit("结果", "歌词音频合成完成", "success")

    def get_voice_conditioning_latent(self, voice_id: str, sample_voice_dir_path: str):
        self.update_progress_text_signal.emit(f"收集训练样本...\n\"{sample_voice_dir_path}\"")
        sample_path_list: [str] = self.get_files(sample_voice_dir_path, [".wav"])
        if not sample_path_list:
            self.finish_signal.emit("结果", "没有收集到训练样本, 声线训练中止", "warning")
        if self.cancel_job:
            self.finish_signal.emit("结果", "任务中止", "warning")
            return

        self.update_progress_text_signal.emit(f"加载xtts模型...")
        model_manager = ModelManager(TTS.get_models_file_path(), tts_config_utility.TTS_RESOURCE_DIR_PATH, True, False)
        model_path, _, _ = model_manager.download_model("tts_models/multilingual/multi-dataset/xtts_v2")
        if not self.xtts:
            self.xtts = Synthesizer(model_dir=model_path, use_cuda=torch.cuda.is_available())
            self.cache_synthesizer_signal.emit("xtts", self.xtts)
        xtts: Xtts = self.xtts.tts_model
        if self.cancel_job:
            self.finish_signal.emit("结果", "任务中止", "warning")
            return

        self.update_progress_text_signal.emit(f"训练声线潜变量...")
        gpt_cond_latent, speaker_embedding = xtts.get_conditioning_latents(sample_path_list)
        if self.cancel_job:
            self.finish_signal.emit("结果", "任务中止", "warning")
            return

        self.update_progress_text_signal.emit(f"保存声线潜变量文件...")
        voice_dir_path = tts_config_utility.tts_config_utility.get_voice_dir_path(voice_id)
        conditioning_latents_path = f"{voice_dir_path}/xtts_condition_latents.pt"
        torch.save(gpt_cond_latent, conditioning_latents_path)

        speaker_embedding_path = f"{voice_dir_path}/xtts_speaker_embedding.pt"
        torch.save(speaker_embedding, speaker_embedding_path)
        if self.cancel_job:
            self.finish_signal.emit("结果", "任务中止", "warning")
            return

        # self._init_vits()


        vits_speaker_embedding_path = f"{voice_dir_path}/vits_speaker_embedding.pth"
        speaker_encoder_model_path = f"{tts_config_utility.TTS_RESOURCE_DIR_PATH}/SpeakerEncoder/model_se.pth"
        speaker_encoder_config_path = f"{tts_config_utility.TTS_RESOURCE_DIR_PATH}/SpeakerEncoder/config_se.json"
        self.update_progress_text_signal.emit(f"加载Embedding管理器...")
        from TTS.tts.utils.managers import EmbeddingManager
        embedding_manager = EmbeddingManager(encoder_model_path=speaker_encoder_model_path, encoder_config_path=speaker_encoder_config_path, use_cuda=torch.cuda.is_available())
        self.update_progress_text_signal.emit(f"计算声线Embedding...")
        speaker_embedding = embedding_manager.compute_embedding_from_clip(sample_path_list)
        from TTS.tts.utils.managers import save_file
        self.update_progress_text_signal.emit(f"保存声线Embedding文件...")
        save_file(speaker_embedding, vits_speaker_embedding_path)
        # if not self.bark:
        #     self.update_progress_text_signal.emit(f"加载bark模型...")
        #     config = BarkConfig()
        #     config.CACHE_DIR = f"{tts_config_utility.TTS_RESOURCE_DIR_PATH}/tts/bark"
        #     config.DEF_SPEAKER_DIR = f"{tts_config_utility.TTS_RESOURCE_DIR_PATH}/Voice"
        #     from transformers import BertTokenizer
        #     bark = Bark(config)
        #     bark.load_checkpoint(config, checkpoint_dir=config.CACHE_DIR, text_model_path=f"{config.CACHE_DIR}/text_2.pt", coarse_model_path=f"{config.CACHE_DIR}/coarse_2.pt",
        #                          fine_model_path=f"{config.CACHE_DIR}/fine_2.pt", eval=True)
        #     self.bark = bark
        #     self.cache_synthesizer_signal.emit("bark", bark)
        # if self.cancel_job:
        #     self.finish_signal.emit("结果", "任务中止", "warning")
        #     return
        #
        # from TTS.tts.layers.bark.inference_funcs import generate_voice
        # speaker_npz_path = f"{voice_dir_path}/voice.npz"
        # self.update_progress_text_signal.emit(f"训练声线特征...")
        # try:
        #     generate_voice(sample_path_list[0], self.bark, speaker_npz_path)
        # except Exception as error:
        #     self.error_signal.emit(f"训练声线特征发生异常:\n{error}")
        #     self.finish_signal.emit("结果", "任务中止", "error")
        #     return

        self.finish_signal.emit("结果", "声线训练完成", "success")

    def do_tts(self, voice_id: str, arg_dict: dict):
        self.update_progress_text_signal.emit(f"加载模型...")
        text = arg_dict["text"]
        language = arg_dict["language"]
        generate_dir_path = arg_dict["generate_dir_path"]
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        voice_name: str = tts_config_utility.tts_config_utility.config_data[voice_id][VoiceData.VOICE_NAME]
        voice_dir_path: str = tts_config_utility.tts_config_utility.get_voice_dir_path(voice_id)

        if language == "en":
            conditioning_latents_path = f"{voice_dir_path}/xtts_condition_latents.pt"
            speaker_embedding_path = f"{voice_dir_path}/xtts_speaker_embedding.pt"
            if not os.path.isfile(conditioning_latents_path) or not os.path.isfile(speaker_embedding_path):
                self.error_signal.emit("未训练声线模型, 请先执行声线训练.")
                self.finish_signal.emit("结果", "任务中止", "warning")
                return

            if not self.xtts:
                model_manager = ModelManager(TTS.get_models_file_path(), tts_config_utility.TTS_RESOURCE_DIR_PATH, True, False)
                model_path, _, _ = model_manager.download_model("tts_models/multilingual/multi-dataset/xtts_v2")
                if self.cancel_job:
                    self.finish_signal.emit("结果", "任务中止", "warning")
                    return
                self.xtts = Synthesizer(model_dir=model_path, use_cuda=torch.cuda.is_available())
                self.cache_synthesizer_signal.emit("xtts", self.xtts)
            if self.cancel_job:
                self.finish_signal.emit("结果", "任务中止", "warning")
                return

            xtts: Xtts = self.xtts.tts_model

            conditioning_latents = None
            speaker_embedding = None
            try:
                conditioning_latents = torch.load(conditioning_latents_path, map_location=device)
                speaker_embedding = torch.load(speaker_embedding_path, map_location=device)
            except Exception as error:
                self.error_signal.emit(f"加载声线潜变量文件发生异常:\n{error}")
                self.finish_signal.emit("结果", "任务中止", "error")
            if self.cancel_job:
                self.finish_signal.emit("结果", "任务中止", "warning")
                return
            self.update_progress_text_signal.emit(f"文本转语音...")
            output: dict = {}
            try:
                output = xtts.inference(text, language, conditioning_latents, speaker_embedding)
            except Exception as error:
                self.error_signal.emit(f"文本转语音发生异常:\n{error}")
                self.finish_signal.emit("结果", "任务中止", "error")
                return
            if self.cancel_job:
                self.finish_signal.emit("结果", "任务中止", "warning")
                return
            self.update_progress_text_signal.emit(f"写入音频...")
            if output:
                if isinstance(output["wav"], list):
                    for j, g in enumerate(output):
                        generate_audio_path = f"{generate_dir_path}/{voice_name}_{j}.wav"
                        torchaudio.save(generate_audio_path, g.squeeze(0).cpu(), 24000)
                else:
                    generate_audio_path = f"{generate_dir_path}/{voice_name}.wav"
                    torchaudio.save(generate_audio_path, torch.tensor(output["wav"]).unsqueeze(0), 24000)
        elif language == "ja":
            vits_speaker_embedding_path = f"{voice_dir_path}/vits_speaker_embedding.pth"
            speaker_encoder_model_path = f"{tts_config_utility.TTS_RESOURCE_DIR_PATH}/SpeakerEncoder/model_se.pth"
            speaker_encoder_config_path = f"{tts_config_utility.TTS_RESOURCE_DIR_PATH}/SpeakerEncoder/config_se.json"
            self.update_progress_text_signal.emit(f"加载Embedding管理器...")
            from TTS.tts.utils.managers import EmbeddingManager
            embedding_manager = EmbeddingManager(encoder_model_path=speaker_encoder_model_path, encoder_config_path=speaker_encoder_config_path, use_cuda=torch.cuda.is_available())
            # model_manager = ModelManager(TTS.get_models_file_path(), tts_config_utility.TTS_RESOURCE_DIR_PATH, True, False)
            # model_path, model_config, _ = model_manager.download_model("voice_conversion_models/multilingual/vctk/freevc24")
            # if not self.freevc:
            #     self.freevc = Synthesizer(vc_checkpoint=model_path, vc_config=model_config, use_cuda=torch.cuda.is_available())
            #     self.cache_synthesizer_signal.emit("freevc", self.freevc)
            # sample_path_list: [str] = self.get_files(voice_dir_path, [".wav"])

            # speaker_npz_path = f"{voice_dir_path}/voice.npz"
            # if not os.path.isfile(speaker_npz_path):
            #     self.error_signal.emit("未训练声线模型, 请先执行声线训练.")
            #     self.finish_signal.emit("结果", "任务中止", "warning")
            #     return
            # if not self.bark:
            #     config = BarkConfig()
            #     config.CACHE_DIR = f"{tts_config_utility.TTS_RESOURCE_DIR_PATH}/tts/bark"
            #     config.DEF_SPEAKER_DIR = f"{tts_config_utility.TTS_RESOURCE_DIR_PATH}/Voice"
            #     bark = Bark.init_from_config(config)
            #     bark.load_checkpoint(config, checkpoint_dir=config.CACHE_DIR, text_model_path=f"{config.CACHE_DIR}/text_2.pt", coarse_model_path=f"{config.CACHE_DIR}/coarse_2.pt",
            #                          fine_model_path=f"{config.CACHE_DIR}/fine_2.pt", eval=True)
            #     self.bark = bark
            #     self.cache_synthesizer_signal.emit("bark", bark)
            if self.cancel_job:
                self.finish_signal.emit("结果", "任务中止", "warning")
                return

            # from TTS.tts.layers.bark.hubert.kmeans_hubert import CustomHubert
            # hubert_model = CustomHubert(checkpoint_path=self.bark.config.LOCAL_MODEL_PATHS["hubert"]).to(device)
            # from TTS.tts.layers.bark.hubert.tokenizer import HubertTokenizer
            # tokenizer = HubertTokenizer.load_from_checkpoint(self.bark.config.LOCAL_MODEL_PATHS["hubert_tokenizer"], map_location=device)
            # from TTS.tts.layers.bark.inference_funcs import load_npz
            # voice_prompt = load_npz(speaker_npz_path)

            text = text.replace('\n', ' ').replace('\r', '').replace(" ", "")
            text = f"[JA]{text}[JA]"
            stn_tst, _ = self._get_text(text)
            x_tst = stn_tst.unsqueeze(0).to(device)
            x_tst_lengths = LongTensor([stn_tst.size(0)]).to(device)
            sid = LongTensor([0]).to(device)
            self._init_vits()
            voice_pth_path_list: [str] = self.get_files(f"{tts_config_utility.TTS_RESOURCE_DIR_PATH}/tts/vits", [".pth"])
            vits_speaker_embedding_path = f"{voice_dir_path}/vits_speaker_embedding.pth"
            vits_speaker_embedding = torch.load(vits_speaker_embedding_path, map_location=device)
            for voice_pth_path in voice_pth_path_list:
                speaker_name = pathlib.Path(voice_pth_path).stem
                self.update_progress_text_signal.emit(f"音频推理: \"{speaker_name}\"...")
                state_dict = rehash_fairseq_vits_checkpoint(voice_pth_path)
                self.vits.load_state_dict(state_dict, strict=False, assign=True)
                self.vits.to(device)
                # try:
                audio = self.vits.inference(x_tst, aux_input={
                    "x_lengths":    x_tst_lengths,
                    "d_vectors":    None,
                    "speaker_ids":  sid,
                    "language_ids": None,
                    "durations":    None
                })
                wav = audio["model_outputs"][0, 0].data.cpu().float().numpy()
                generate_audio_path = f"{generate_dir_path}/{voice_name}-{speaker_name}.wav"
                save_wav(wav=wav, path=generate_audio_path, sample_rate=24000)
                from TTS.tts.utils.synthesis import embedding_to_torch
                reference_wav = embedding_to_torch(wav, device=device)
                reference_speaker_embedding = embedding_manager.compute_embedding_from_clip(generate_audio_path)
                d_vector = embedding_to_torch(vits_speaker_embedding, device=device)
                reference_d_vector = embedding_to_torch(reference_speaker_embedding, device=device)
                # output = self.vits.inference_voice_conversion(reference_wav, d_vector=d_vector, reference_d_vector=reference_d_vector)
                # model_outputs = output.squeeze()
                # waveform = model_outputs.numpy()
                # wav = waveform.squeeze()
                # conversion_wav_path = f"{generate_dir_path}/{voice_name}-{speaker_name}-vc.wav"
                # save_wav(wav=wav, path=conversion_wav_path, sample_rate=24000)

                # wav = self.freevc.voice_conversion(generate_audio_path, sample_path_list[0])
                # save_wav(wav=wav, path=f"{generate_dir_path}/{voice_name}-{speaker_name}-freevc.wav", sample_rate=24000)

                # audio, sr = torchaudio.load(generate_audio_path)
                # if audio.shape[0] == 2:  # Stereo to mono if needed
                #     audio = audio.mean(0, keepdim=True)
                # from encodec.utils import convert_audio
                # audio = convert_audio(audio, sr, self.bark.config.sample_rate, self.bark.encodec.channels)
                # audio = audio.unsqueeze(0).to(device)
                # semantic_vectors = hubert_model.forward(audio[0], input_sample_hz=self.bark.config.sample_rate)
                # semantic_tokens = tokenizer.get_token(semantic_vectors)
                # semantic_tokens = semantic_tokens.cpu().numpy()
                # wav = self.bark.semantic_to_waveform(semantic_tokens, voice_prompt)[0]
                # save_wav(wav=wav, path=generate_audio_path, sample_rate=24000)

                # except Exception as error:
                #     self.error_signal.emit(f"文本转语音发生异常:\n{error}")
                #     self.finish_signal.emit("结果", "任务中止", "error")
                #     return

        self.finish_signal.emit("结果", "文本转语音完成", "success")

    def _init_vits(self):
        if self.vits:
            return
        self.update_progress_text_signal.emit(f"加载vits模型...")
        from TTS.tts.configs.vits_config import VitsConfig
        from TTS.tts.models.vits import Vits
        config = VitsConfig()
        config.model_args.num_speakers = 804
        config.model_args.num_chars = len(symbols)
        config.model_args.init_discriminator = False
        config.model_args.inference_noise_scale = 0.6
        config.model_args.inference_noise_scale_dp = 0.668
        config.model_args.length_scale = 1.1
        config.model_args.use_d_vector_file = True
        vits = Vits(config)
        vits.eval()
        self.vits = vits
        self.cache_synthesizer_signal.emit("vits", self.vits)

    def _get_text(self, text):
        text_norm, clean_text = self._text_to_sequence(text, symbols, ["zh_ja_mixture_cleaners"])
        text_norm = self._intersperse(text_norm, 0)
        text_norm = LongTensor(text_norm)
        return text_norm, clean_text

'''

#     def _text_to_sequence(self, text, symbols, cleaner_names):
#         '''Converts a string of text to a sequence of IDs corresponding to the symbols in the text.
#           Args:
#             text: string to convert to a sequence
#             cleaner_names: names of the cleaner functions to run the text through
#           Returns:
#             List of integers corresponding to the symbols in the text
#         '''
#         _symbol_to_id = {s: i for i, s in enumerate(symbols)}
#         sequence = []
#
#         clean_text = self._clean_text(text, cleaner_names)
#         for symbol in clean_text:
#             if symbol not in _symbol_to_id.keys():
#                 continue
#             symbol_id = _symbol_to_id[symbol]
#             sequence += [symbol_id]
#         return sequence, clean_text
#
#
#     def _clean_text(self, text, cleaner_names):
#         for name in cleaner_names:
#             cleaner = getattr(cleaners, name)
#             if not cleaner:
#                 raise Exception('Unknown cleaner: %s' % name)
#             text = cleaner(text)
#         return text
#
#     def _intersperse(self, lst, item):
#         result = [item] * (len(lst) * 2 + 1)
#         result[1::2] = lst
#         return result
#
#
# symbols = ["_", ",", ".", "!", "?", "-", "~", "\u2026", "A", "E", "I", "N", "O", "Q", "U", "a", "b", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "v", "w", "y",
#            "z", "\u0283", "\u02a7", "\u02a6", "\u026f", "\u0279", "\u0259", "\u0265", "\u207c", "\u02b0", "`", "\u2192", "\u2193", "\u2191", " "]