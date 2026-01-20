"""
History Manager Mixin

Handles history management operations.
"""
import os
from qfluentwidgets import InfoBar, InfoBarPosition


class HistoryManagerMixin:
    """Mixin for history management operations."""

    def _get_current_history_store(self):
        """获取当前项目的历史记录存储"""
        from Source.Utility.tts_history_utility import tts_history_store

        if self._current_project_id and self._current_project_id in self._history_stores:
            return self._history_stores[self._current_project_id]
        return tts_history_store  # 回退到全局的（向后兼容）

    def _on_open_history(self):
        """打开非模态历史记录窗口（按当前所选角色过滤）。"""
        from Source.UI.Interface.AIVoiceInterface.windows.history_window import AIVoiceHistoryWindow

        character = self._character_manager.selected_character
        if character is None:
            InfoBar.info(
                title="未选择角色",
                content="请先选择一个角色再查看历史记录",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return

        win = getattr(self, "_history_window", None)
        if win is None:
            win = AIVoiceHistoryWindow(
                self._main_window,
                download_callback=self._on_download_audio,
                history_store=self._get_current_history_store(),
            )
            self._history_window = win
        try:
            if hasattr(win, "set_history_store"):
                win.set_history_store(self._get_current_history_store())
            win.set_character(character.id, character.name)
        except Exception:
            pass
        try:
            win.show()
            win.raise_()
            win.activateWindow()
        except Exception:
            pass

    def _refresh_history_window_if_open(self):
        """若历史窗口已打开，刷新其内容。"""
        win = getattr(self, "_history_window", None)
        if win is None:
            return
        try:
            if not win.isVisible():
                return
        except Exception:
            pass
        character = self._character_manager.selected_character
        if character is None:
            try:
                win.set_character("", "")
            except Exception:
                pass
            return
        try:
            if hasattr(win, "set_history_store"):
                win.set_history_store(self._get_current_history_store())
            win.set_character(character.id, character.name)
        except Exception:
            pass

    def _clear_output_results(self) -> None:
        """清空生成结果区域（3 个样本卡片 + 内部路径数组），并回到空态音符。"""
        try:
            self._output_wav_paths = ["", "", ""]
        except Exception:
            pass

        # 先释放媒体句柄，避免 Windows 下删除/改名卡住
        try:
            for w in getattr(self, "output_player_widgets", []) or []:
                try:
                    if hasattr(w, "release_media"):
                        w.release_media()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            for w in getattr(self, "output_player_widgets", []) or []:
                try:
                    w.set_audio_path("")
                except Exception:
                    pass
                try:
                    w.set_loading(False)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            self._set_output_empty_state(True)
        except Exception:
            pass

    def _set_output_empty_state(self, empty: bool):
        """切换生成结果区域空状态（未生成时仅显示音符图标）。"""
        try:
            cur = -1
            try:
                cur = int(self._output_stack.currentIndex())
            except Exception:
                cur = -1

            if empty:
                try:
                    self._output_stack.setCurrentIndex(0)
                except Exception:
                    pass
                return
            self._output_stack.setCurrentIndex(1)
            # 非空态会显著增加内容高度：主动让主窗口增高，避免控件被挤压造成"视觉重叠"
            self._grow_window_to_fit_contents()
        except Exception:
            pass
