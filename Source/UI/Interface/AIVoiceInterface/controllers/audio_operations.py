"""
Audio Operations Mixin

Handles audio import, playback, and download operations.
"""
import os
import time
from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QFileDialog
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from qfluentwidgets import InfoBar, InfoBarPosition
from typing import Optional


class AudioOperationsMixin:
    """Mixin for audio-related operations."""

    def _on_import_audio(self):
        """导入参考音频"""
        if getattr(self, "_synthesis_in_progress", False):
            InfoBar.info(
                title="正在生成",
                content="生成进行中，暂不可导入参考音频",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
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

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择参考音频", "",
            "音频文件 (*.wav *.mp3 *.flac *.ogg);;所有文件 (*.*)"
        )
        
        if file_path:
            self._update_character_audio(character.id, file_path)


    def _on_audio_dropped(self, file_path: str):
        """处理拖拽导入的音频"""
        if getattr(self, "_synthesis_in_progress", False):
            InfoBar.info(
                title="正在生成",
                content="生成进行中，暂不可导入参考音频",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return
        character = self._character_manager.selected_character
        if not character:
            InfoBar.warning(
                title="请先选择角色",
                content="请先在左侧列表中选择或创建一个角色",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return
            
        self._update_character_audio(character.id, file_path)


    def _update_character_audio(self, character_id: str, file_path: str):
        """更新角色的参考音频"""
        self._character_manager.update_reference_audio(character_id, file_path)
        self._update_reference_audio_display()
        self._update_generate_btn_state()
        try:
            self.character_list_widget.update_reference_state(character_id, bool(file_path))
        except Exception:
            pass
        
        InfoBar.success(
            title="参考音频已更新",
            content=f"已加载: {os.path.basename(file_path)}",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000
        )


    def _ensure_ref_player(self):
        """确保参考音频播放器已创建"""
        if self._ref_player is None:
            self._ref_player = QMediaPlayer(self)
            self._ref_audio_output = QAudioOutput(self)
            self._ref_player.setAudioOutput(self._ref_audio_output)


    def _on_play_reference(self):
        """播放参考音频 (已由 AudioPlayerWidget 接管)"""
        pass


    def _ensure_player(self):
        """确保输出音频播放器已创建 (已废弃)"""
        pass


    def _on_play_output(self):
        """播放生成的音频 (已由 AudioPlayerWidget 接管)"""
        pass


    def _on_download_audio(self, wav_path: Optional[str] = None):
        """下载/保存生成的音频（支持指定某个样本路径）。"""
        if wav_path is None:
            wav_path = self._main_window.indextts_job.last_wav_path
        if not wav_path or not os.path.exists(wav_path):
            InfoBar.warning(
                title="无可保存文件",
                content="请先生成音频",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000,
            )
            return

        character = self._character_manager.selected_character
        if character:
            suggested_dir, suggested_name = self._character_manager.get_suggested_output_path(character.id)
        else:
            suggested_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MusicLocation)
            suggested_name = f"output_{int(time.time())}.wav"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存音频文件",
            os.path.join(suggested_dir, suggested_name),
            "WAV 音频 (*.wav);;所有文件 (*.*)",
        )

        if save_path:
            try:
                import shutil

                shutil.copy2(wav_path, save_path)
                if character:
                    self._character_manager.update_last_output(
                        character.id,
                        os.path.dirname(save_path),
                        os.path.basename(save_path),
                    )
                InfoBar.success(
                    title="保存成功",
                    content=os.path.basename(save_path),
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                )
            except Exception as e:
                InfoBar.error(
                    title="保存失败",
                    content=str(e),
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                )


    def _sync_output_results_after_rename(self, character_id: str, old_name: str, new_name: str) -> None:
        """角色改名成功后，同步生成结果区域中已展示的样本路径/标题。

        目标：输出区展示的 3 条若来自该角色目录，则将其映射到新目录/新文件名。
        """
        try:
            store = self._get_current_history_store()
            old_dir = str(store.get_character_dir(character_id, old_name) or "")
            new_dir = str(store.get_character_dir(character_id, new_name) or "")
        except Exception:
            return

        def _is_under_dir(path: str, base_dir: str) -> bool:
            try:
                if not path or not base_dir:
                    return False
                return os.path.commonpath([os.path.abspath(path), os.path.abspath(base_dir)]) == os.path.abspath(base_dir)
            except Exception:
                return False

        new_paths: list[str] = ["", "", ""]
        try:
            cur_paths = list(getattr(self, "_output_wav_paths", []) or [])
        except Exception:
            cur_paths = []

        # 保持长度为 3
        while len(cur_paths) < 3:
            cur_paths.append("")

        for i in range(3):
            p = str(cur_paths[i] or "")
            if not p:
                continue

            # 只处理位于旧角色目录下的输出
            if not _is_under_dir(p, old_dir):
                # 可能已经是新路径（或不属于该角色），原样保留
                if os.path.exists(p):
                    new_paths[i] = p
                continue

            base = os.path.basename(p)
            candidates: list[str] = []

            # 1) 优先：目录改为 new_dir，文件名前缀 old_name -> new_name
            try:
                if base.startswith(f"{old_name}_"):
                    candidates.append(os.path.join(new_dir, f"{new_name}_" + base[len(old_name) + 1 :]))
            except Exception:
                pass

            # 2) 兜底：仅替换目录（若文件名本身未改/已改）
            try:
                candidates.append(os.path.join(new_dir, base))
            except Exception:
                pass

            # 3) 最后兜底：按序号猜测（常见规则：<name>_1.wav.._3.wav）
            try:
                candidates.append(os.path.join(new_dir, f"{new_name}_{i + 1}.wav"))
            except Exception:
                pass

            chosen = ""
            for c in candidates:
                try:
                    if c and os.path.exists(c):
                        chosen = c
                        break
                except Exception:
                    continue

            new_paths[i] = chosen

        # 应用到状态与控件
        try:
            self._output_wav_paths = new_paths
        except Exception:
            pass

        try:
            widgets = list(getattr(self, "output_player_widgets", []) or [])
        except Exception:
            widgets = []

        for i in range(min(3, len(widgets))):
            try:
                widgets[i].set_audio_path(new_paths[i])
            except Exception:
                pass

        try:
            any_ok = any(p and os.path.exists(p) for p in new_paths)
        except Exception:
            any_ok = False
        try:
            self._set_output_empty_state(not bool(any_ok))
        except Exception:
            pass


    def _update_reference_audio_display(self):
        """更新参考音频显示"""
        character = self._character_manager.selected_character
        
        if not character:
            self.ref_player_widget.set_audio_path("")
            return
        
        if character.reference_audio_path and os.path.exists(character.reference_audio_path):
            self.ref_player_widget.set_audio_path(character.reference_audio_path)
        else:
            self.ref_player_widget.set_audio_path("")


