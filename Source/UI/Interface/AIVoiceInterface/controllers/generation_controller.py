"""
Generation Controller Mixin

Handles audio generation, progress tracking, and generation state management.
"""
import os
import time
from PySide6.QtCore import Slot
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox

from Source.Utility.indextts_utility import IndexTTSUtility


class GenerationControllerMixin:
    """Mixin for audio generation control operations."""

    def _on_generate_clicked(self):
        """生成语音"""
        if getattr(self, "_synthesis_in_progress", False):
            InfoBar.info(
                title="正在生成",
                content="请等待当前生成完成",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return
        # 检查环境是否就绪
        if not self._check_env_ready_with_warning():
            return
        
        # 检查模型是否已加载
        if not self._main_window.indextts_job.is_model_loaded:
            InfoBar.warning(
                title="请先加载模型",
                content="需要先加载模型才能生成语音",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return
        
        character = self._character_manager.selected_character
        if not character:
            InfoBar.warning(
                title="请先选择角色",
                content="需要先创建并选择一个角色",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        if not character.reference_audio_path or not os.path.exists(character.reference_audio_path):
            InfoBar.warning(
                title="请导入参考音频",
                content="需要先导入音色参考音频",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        text = self.text_edit.toPlainText().strip()
        if not text:
            InfoBar.warning(
                title="请输入文本",
                content="合成文本不能为空",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        # 确定情感模式
        if self.emo_mode_same.isChecked():
            emo_mode = IndexTTSUtility.EMO_MODE_SAME_AS_SPEAKER
            emo_vector = None
        else:
            emo_mode = IndexTTSUtility.EMO_MODE_VECTOR
            emo_vector = [
                self.emo_sliders[label].value() / 100.0
                for label in IndexTTSUtility.EMO_LABELS
            ]

        # 输出路径与历史记录：按项目/角色写入 temp_output/<project>/<角色>/，并生成序列文件名
        try:
            output_paths = self._get_current_history_store().build_output_paths(character.id, character.name, count=3)
        except Exception:
            # 极端情况下 build_output_paths 失败时，仍尽量保持按项目隔离，避免写入全局 temp_output
            try:
                store = self._get_current_history_store()
                temp_dir = getattr(store, "base_dir", "") or ""
            except Exception:
                temp_dir = ""
            if not temp_dir:
                temp_dir = os.path.join(os.getcwd(), "temp_output")
            os.makedirs(temp_dir, exist_ok=True)
            ts = int(time.time())
            output_paths = [os.path.join(temp_dir, f"temp_{ts}_v{i + 1}.wav") for i in range(3)]

        # 组逻辑：合成文本不变则并入上一组；否则新建一组
        try:
            group_id = self._get_current_history_store().get_or_create_group_id(character.id, character.name, text)
        except Exception:
            group_id = str(int(time.time() * 1000))
        self._history_pending = {
            "character_id": character.id,
            "character_name": character.name,
            "text": text,
            "group_id": group_id,
        }

        # 清空旧输出 UI，并预渲染 3 个样本为“生成中”遮罩态
        try:
            self._output_wav_paths = ["", "", ""]
            for w in getattr(self, "output_player_widgets", []):
                w.set_audio_path("")
                try:
                    w.set_loading(True, 0.0)
                except Exception:
                    pass
            # 点击生成后立刻展示 3 个预渲染播放器（避免出现“空态音符 + 底部进度/文本”）
            self._set_output_empty_state(False)
        except Exception:
            pass

        # 开始生成
        self._synthesis_in_progress = True
        self._main_window.indextts_job.synthesize_variants_action(
            spk_audio_path=character.reference_audio_path,
            text=text,
            output_paths=output_paths,
            emo_mode=emo_mode,
            emo_vector=emo_vector,
        )

        # 更新 UI 状态
        self.generate_btn.setEnabled(False)


    def _on_emo_mode_changed(self):
        """情感模式切换"""
        self.vector_panel.setVisible(self.emo_mode_vector.isChecked())
        # 展开情感向量面板时，让窗口向外增高而不是压缩上方组件
        if self.emo_mode_vector.isChecked():
            self._grow_window_to_fit_contents()


    def _update_generate_btn_state(self):
        """更新生成按钮状态"""
        character = self._character_manager.selected_character
        job = self._main_window.indextts_job

        ref_audio = ""
        try:
            if character is not None and character.reference_audio_path:
                ref_audio = str(character.reference_audio_path)
        except Exception:
            ref_audio = ""

        can_generate = bool(
            job.is_model_loaded
            and character is not None
            and ref_audio
            and os.path.exists(ref_audio)
        )
        self.generate_btn.setEnabled(bool(can_generate))


    @Slot(float, str)
    def _on_progress_updated(self, progress: float, text: str):
        """进度更新回调"""
        # 生成结果区域不再展示“总进度条/底部状态文本”（仅使用每个样本卡片的遮罩进度）
        return


    @Slot(int, str)
    def _on_variant_generated(self, index: int, wav_path: str):
        """某个候选样本生成完成回调。"""
        try:
            if 0 <= int(index) < 3:
                self._output_wav_paths[int(index)] = wav_path
                if hasattr(self, "output_player_widgets") and int(index) < len(self.output_player_widgets):
                    self.output_player_widgets[int(index)].set_audio_path(wav_path)
                    try:
                        self.output_player_widgets[int(index)].set_loading(False)
                    except Exception:
                        pass
                self._set_output_empty_state(False)
        except Exception:
            pass


    @Slot(int, float, str)
    def _on_variant_progress(self, index: int, progress: float, text: str):
        """单个样本实时进度：更新对应播放器遮罩进度条。"""
        try:
            idx = int(index)
            if hasattr(self, "output_player_widgets") and 0 <= idx < len(self.output_player_widgets):
                self.output_player_widgets[idx].set_loading_progress(float(progress))
        except Exception:
            pass


    @Slot(bool)
    def _on_job_completed(self, success: bool):
        """任务完成回调"""
        # 先处理“模型加载”路径：补齐失败提示/一键重试
        is_model_load_flow = bool(getattr(self, "_model_load_in_progress", False)) and (not bool(getattr(self, "_synthesis_in_progress", False)))
        if is_model_load_flow:
            # 停止 watchdog
            try:
                if getattr(self, "_model_load_watchdog", None) is not None:
                    self._model_load_watchdog.stop()
            except Exception:
                pass

            # 清理标志
            try:
                self._model_load_in_progress = False
            except Exception:
                pass

            # 先把 FP16 开关放开（若模型成功加载，_update_model_status 会再禁用）
            try:
                if getattr(self, "fp16_checkbox", None) is not None:
                    self.fp16_checkbox.setEnabled(True)
            except Exception:
                pass

            if not success:
                last_fp16 = bool(getattr(self, "_model_load_last_fp16", False))

                try:
                    rec, reason = self._recommend_fp16()
                except Exception:
                    rec, reason = (True, "")

                if not last_fp16:
                    msg = (
                        "模型加载失败，常见原因：显存不足（尤其 8GB）、驱动/环境异常或模型文件不完整。\n\n"
                        "建议开启 FP16（半精度）降低显存占用后重试。"
                    )
                    if reason:
                        msg += f"\n\n{reason}"

                    ok = False
                    try:
                        box = MessageBox("模型加载失败", msg, self._main_window)
                        self._tune_message_box(box)
                        box.yesButton.setText("开启 FP16 并重试")
                        box.cancelButton.setText("取消")
                        ok = (box.exec() == 1)
                    except Exception:
                        ok = False

                    if ok:
                        try:
                            if getattr(self, "fp16_checkbox", None) is not None:
                                self.fp16_checkbox.setChecked(True)
                        except Exception:
                            pass
                        try:
                            self._on_load_model_clicked()
                        except Exception:
                            pass
                else:
                    hint = (
                        "模型加载失败（已启用 FP16）。\n"
                        "建议：\n"
                        "- 关闭占用显存的软件（游戏/浏览器硬件加速等）\n"
                        "- 更新 NVIDIA 驱动\n"
                        "- 确认模型文件完整（必要时重新下载）"
                    )
                    if reason:
                        hint += f"\n\n{reason}"
                    try:
                        InfoBar.error(
                            title="模型加载失败",
                            content=hint,
                            parent=self,
                            position=InfoBarPosition.TOP,
                            duration=9000,
                        )
                    except Exception:
                        pass

        self._update_model_status()
        self._update_generate_btn_state()

        # job_completed(True) 同时用于“模型加载完成”和“语音生成完成”。
        # 只有当我们确实处于“合成中”时，才更新生成结果状态文本。
        if not self._synthesis_in_progress:
            return

        self._synthesis_in_progress = False

        # 结束后，确保所有遮罩都退出
        try:
            for w in getattr(self, "output_player_widgets", []):
                w.set_loading(False)
        except Exception:
            pass
        
        if success:
            any_ok = False
            try:
                any_ok = any(p and os.path.exists(p) for p in getattr(self, "_output_wav_paths", []))
            except Exception:
                any_ok = False
            if any_ok:
                self._set_output_empty_state(False)

                # 写入历史记录（最多 3 个样本）
                try:
                    pending = getattr(self, "_history_pending", None) or {}
                    cid = str(pending.get("character_id", ""))
                    cname = str(pending.get("character_name", ""))
                    gid = str(pending.get("group_id", ""))
                    txt = str(pending.get("text", ""))
                    if cid and gid:
                        self._get_current_history_store().append_samples(
                            cid,
                            cname,
                            gid,
                            txt,
                            list(getattr(self, "_output_wav_paths", []) or []),
                        )
                except Exception:
                    pass

                # 若历史窗口已打开，刷新内容
                try:
                    self._refresh_history_window_if_open()
                except Exception:
                    pass
            else:
                # 没有任何样本产出：回到空态音符
                try:
                    self._output_wav_paths = ["", "", ""]
                    for w in getattr(self, "output_player_widgets", []):
                        w.set_audio_path("")
                except Exception:
                    pass
                self._set_output_empty_state(True)
        else:
            try:
                self._output_wav_paths = ["", "", ""]
                for w in getattr(self, "output_player_widgets", []):
                    w.set_audio_path("")
            except Exception:
                pass
            self._set_output_empty_state(True)

        # 清理 pending
        try:
            self._history_pending = None
        except Exception:
            pass


    @Slot(bool)
    def _on_download_job_completed(self, success: bool):
        """下载任务完成回调"""
        if success:
            self._check_env_and_model()


    def _check_env_and_model(self):
        """检查环境和模型状态"""
        # 注意：此方法会在界面 refresh() 时被调用，必须保持非阻塞。
        # 这里只做“是否存在独立 venv python”的快速判断；更完整的依赖检查
        # 由 EnvCheckWorker 在后台线程完成。
        env_ok = False
        try:
            from Source.Utility.indextts_runtime_utility import get_runtime_paths

            env_ok = bool(os.path.exists(get_runtime_paths().venv_python))
        except Exception:
            env_ok = False

        # 检查模型文件
        model_dir = IndexTTSUtility.get_default_model_dir()
        model_ok, _ = IndexTTSUtility.check_model_files(model_dir)

        # 记录快照，供点击逻辑使用
        self._env_ok_fast = bool(env_ok)
        self._model_files_ok = bool(model_ok)
        
        # 更新下载/删除按钮状态（若正在异步检测，不覆盖按钮文案/禁用状态）
        if not self._env_check_pending:
            self._update_download_btn_state(bool(env_ok), bool(model_ok))
            try:
                if getattr(self, "download_btn", None) is not None:
                    self.download_btn.setEnabled(True)
            except Exception:
                pass
        self._env_ready = bool(env_ok and model_ok)

        # 更新模型状态
        self._update_model_status()


    def _grow_window_to_fit_contents(self):
        """当内容区展开时，让主窗口向外增高以容纳内容。

        Qt 默认不会因为子控件 show/hide 自动调整顶层窗口尺寸；
        这里在关键交互点触发一次增高，避免布局被压缩导致控件观感重叠。
        """
        try:
            win = getattr(self, "_main_window", None) or self.window()
            if win is None:
                return

            # 触发布局重算
            try:
                if self.layout() is not None:
                    self.layout().activate()
            except Exception:
                pass

            # 缓存一次“窗口额外高度”（标题栏/导航栏等），避免随着 resize 反复漂移导致越长越高
            if not hasattr(self, "_window_extra_h_cache"):
                try:
                    extra0 = int(win.height()) - int(self.height())
                    self._window_extra_h_cache = max(0, min(600, extra0))
                except Exception:
                    self._window_extra_h_cache = 0

            hint_h = 0
            try:
                hint_h = max(int(self.sizeHint().height()), int(self.minimumSizeHint().height()))
            except Exception:
                hint_h = int(self.height())

            # 估算非 client 区与外围控件占用的高度差
            extra_h = 0
            try:
                extra_h = int(getattr(self, "_window_extra_h_cache", 0) or 0)
            except Exception:
                extra_h = 0

            desired_h = int(hint_h + extra_h + 16)
            if desired_h > int(win.height()):
                win.resize(int(win.width()), desired_h)
        except Exception:
            pass


