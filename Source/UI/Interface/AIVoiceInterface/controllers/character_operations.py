"""
Character Operations Mixin

Handles character management operations (add, edit, delete, import).
"""
import os
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox

# After refactor, mixins must import the symbols they reference.
from Source.UI.Interface.AIVoiceInterface.dialogs.batch_delete_characters_dialog import BatchDeleteCharactersDialog
from Source.UI.Interface.AIVoiceInterface.dialogs.character_dialog import CharacterDialog
from Source.UI.Interface.AIVoiceInterface.models.character_manager import CharacterManager


class CharacterOperationsMixin:
    """Mixin for character management operations."""

    def _is_character_name_unique(self, name: str, *, exclude_id: str | None = None) -> bool:
        try:
            candidate = str(name or "").strip()
        except Exception:
            candidate = ""
        if not candidate:
            return False

        # Prevent clobbering temp_output/logs
        try:
            store = self._get_current_history_store()
            safe_dir = os.path.basename(store.get_character_dir("", candidate))
            if str(safe_dir).strip().lower() == "logs":
                return False
        except Exception:
            pass

        try:
            candidate_key = candidate.lower()
        except Exception:
            candidate_key = candidate

        for c in self._character_manager.characters:
            try:
                if exclude_id and str(getattr(c, "id", "")) == str(exclude_id):
                    continue
                n = str(getattr(c, "name", "") or "").strip()
                if not n:
                    continue
                if n.lower() == candidate_key:
                    return False
            except Exception:
                continue
        return True
        

    def _on_add_character(self):
        """添加新角色"""
        if not self._character_manager.can_add:
            InfoBar.warning(
                title="角色数量已达上限",
                content=f"最多只能创建 {CharacterManager.MAX_CHARACTERS} 个角色",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        dialog = CharacterDialog(self._main_window)
        if dialog.exec():
            name, avatar_path = dialog.get_data()
            if name:
                if not self._is_character_name_unique(str(name)):
                    InfoBar.error(
                        title="昵称不可用",
                        content="角色昵称必须唯一，且不能使用 logs 作为昵称",
                        parent=self,
                        position=InfoBarPosition.TOP,
                        duration=3500,
                    )
                    return
                character = self._character_manager.add(name, avatar_path)
                if character:
                    self._refresh_character_list()
                    self._select_character(character.id)
                    InfoBar.success(
                        title="角色创建成功",
                        content=f"已创建角色: {name}",
                        parent=self,
                        position=InfoBarPosition.TOP,
                        duration=2000
                    )


    def _on_character_selected(self, character_id: str):
        """角色被选中 - 选中并置顶"""
        # 选中并置顶
        self._character_manager.select_and_move_to_top(character_id)
        # 刷新列表
        self._refresh_character_list()
        # 更新参考音频显示
        self._update_reference_audio_display()
        # 更新生成按钮状态
        self._update_generate_btn_state()
        # 刷新历史窗口（若已打开）
        try:
            self._refresh_history_window_if_open()
        except Exception:
            pass


    def _on_character_edit(self, character_id: str):
        """编辑角色"""
        character = self._character_manager.get_by_id(character_id)
        if not character:
            return

        old_name = str(getattr(character, "name", "") or "")

        dialog = CharacterDialog(
            self._main_window,
            character_name=character.name,
            avatar_path=character.avatar_path
        )
        if dialog.exec():
            name, avatar_path = dialog.get_data()
            if name:
                if (str(name).strip() != old_name.strip()) and (not self._is_character_name_unique(str(name), exclude_id=character_id)):
                    InfoBar.error(
                        title="昵称不可用",
                        content="角色昵称必须唯一，且不能使用 logs 作为昵称",
                        parent=self,
                        position=InfoBarPosition.TOP,
                        duration=3500,
                    )
                    return
                self._character_manager.update(
                    character_id,
                    name=name,
                    avatar_path=avatar_path
                )

                # 同步更新 temp_output 下的角色目录与样本文件名
                try:
                    if str(name) and str(name) != old_name:
                        # Windows 下若 wav 正在被播放器占用，目录改名会失败（表现为只新建空目录）
                        try:
                            win = getattr(self, "_history_window", None)
                            if win is not None and hasattr(win, "release_all_media"):
                                win.release_all_media()
                        except Exception:
                            pass
                        try:
                            for w in getattr(self, "output_player_widgets", []) or []:
                                if hasattr(w, "release_media"):
                                    w.release_media()
                        except Exception:
                            pass
                        # 没有任何历史缓存时不应提示“改名失败”
                        has_old_cache = False
                        try:
                            from Source.Utility.tts_history_utility import _sanitize_component

                            safe_old = _sanitize_component(old_name)
                            desired_old = os.path.join(self._get_current_history_store().base_dir, safe_old)
                            has_old_cache = bool(safe_old and os.path.isdir(desired_old))
                        except Exception:
                            has_old_cache = False

                        ok = bool(self._get_current_history_store().rename_character_cache(character_id, old_name, str(name)))
                        if has_old_cache and (not ok):
                            InfoBar.warning(
                                title="历史缓存改名失败",
                                content="可能有音频仍在播放/占用文件，建议停止播放或关闭历史窗口后重试",
                                parent=self,
                                position=InfoBarPosition.TOP,
                                duration=4500,
                            )
                        else:
                            # 同步刷新生成结果区域显示的文件名/路径
                            try:
                                self._sync_output_results_after_rename(character_id, old_name, str(name))
                            except Exception:
                                pass
                except Exception:
                    pass

                self._refresh_character_list()
                try:
                    self._refresh_history_window_if_open()
                except Exception:
                    pass
                InfoBar.success(
                    title="角色更新成功",
                    content=f"已更新角色: {name}",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=2000
                )


    def _on_character_delete(self, character_id: str):
        """删除角色"""
        character = self._character_manager.get_by_id(character_id)
        if not character:
            return

        msg = MessageBox(
            "确认删除",
            f"确定要删除角色「{character.name}」吗？\n删除后将从列表中移除。",
            self._main_window
        )
        if msg.exec():
            # 删除角色时，一并清理 temp_output 下该角色的音频文件夹
            try:
                # Windows 下若 wav 正在被播放器占用，删除会失败（表现为只删掉 history.jsonl 或无变化）
                try:
                    win = getattr(self, "_history_window", None)
                    if win is not None and hasattr(win, "release_all_media"):
                        win.release_all_media()
                except Exception:
                    pass
                try:
                    for w in getattr(self, "output_player_widgets", []) or []:
                        if hasattr(w, "release_media"):
                            w.release_media()
                except Exception:
                    pass
                # 参考音频播放器也可能占用文件
                try:
                    if hasattr(self, "ref_player_widget") and hasattr(self.ref_player_widget, "release_media"):
                        self.ref_player_widget.release_media()
                except Exception:
                    pass

                removed = int(self._get_current_history_store().delete_character_cache(character_id, str(getattr(character, "name", "") or "")))
                if removed < 0:
                    InfoBar.warning(
                        title="缓存删除可能失败",
                        content="可能有音频仍在播放/占用文件，建议停止播放或关闭历史窗口后再删除",
                        parent=self,
                        position=InfoBarPosition.TOP,
                        duration=4500,
                    )
            except Exception:
                pass
            self._character_manager.delete(character_id)
            self._refresh_character_list()

            # 删除角色后：切换到新的选中角色并清空生成结果区域（避免残留已被删除的 wav）
            try:
                next_id = self._character_manager.selected_id
                if next_id:
                    self._select_character(next_id)
                else:
                    self._update_reference_audio_display()
                    self._update_generate_btn_state()
            except Exception:
                pass
            try:
                self._clear_output_results()
            except Exception:
                pass

            try:
                self._refresh_history_window_if_open()
            except Exception:
                pass
            InfoBar.success(
                title="角色已删除",
                content=f"已删除角色: {character.name}",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000
            )


    def _on_batch_delete_characters(self):
        """批量删除角色（带选择对话框）。"""
        try:
            characters = list(self._character_manager.characters or [])
        except Exception:
            characters = []

        if not characters:
            InfoBar.info(
                title="没有可删除的角色",
                content="当前项目没有角色",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=1800,
            )
            return

        dlg = BatchDeleteCharactersDialog(self._main_window, characters)
        if not dlg.exec():
            return

        selected_ids = dlg.get_selected_ids()
        if not selected_ids:
            InfoBar.info(
                title="未选择角色",
                content="请先勾选要删除的角色",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=1800,
            )
            return

        msg = MessageBox(
            "确认批量删除",
            f"确定要删除选中的 {len(selected_ids)} 个角色吗？\n删除后将从列表中移除。",
            self._main_window,
        )
        if not msg.exec():
            return

        # 删除前尽量释放媒体句柄（Windows 删除/改名需要）
        try:
            win = getattr(self, "_history_window", None)
            if win is not None and hasattr(win, "release_all_media"):
                win.release_all_media()
        except Exception:
            pass
        try:
            for w in getattr(self, "output_player_widgets", []) or []:
                if hasattr(w, "release_media"):
                    w.release_media()
        except Exception:
            pass
        try:
            if hasattr(self, "ref_player_widget") and hasattr(self.ref_player_widget, "release_media"):
                self.ref_player_widget.release_media()
        except Exception:
            pass

        failed_cache = 0
        deleted = 0
        for cid in selected_ids:
            ch = None
            try:
                ch = self._character_manager.get_by_id(cid)
            except Exception:
                ch = None
            if ch is None:
                continue

            try:
                removed = int(self._get_current_history_store().delete_character_cache(cid, str(getattr(ch, "name", "") or "")))
                if removed < 0:
                    failed_cache += 1
            except Exception:
                pass

            try:
                if self._character_manager.delete(cid):
                    deleted += 1
            except Exception:
                pass

        self._refresh_character_list()
        try:
            next_id = self._character_manager.selected_id
            if next_id:
                self._select_character(next_id)
            else:
                self._update_reference_audio_display()
                self._update_generate_btn_state()
        except Exception:
            pass
        try:
            self._clear_output_results()
        except Exception:
            pass

        try:
            self._refresh_history_window_if_open()
        except Exception:
            pass

        if failed_cache > 0:
            InfoBar.warning(
                title="部分缓存删除失败",
                content=f"有 {failed_cache} 个角色的缓存目录可能仍被占用，可停止播放/关闭历史窗口后再重试删除缓存。",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4500,
            )

        InfoBar.success(
            title="批量删除完成",
            content=f"已删除 {deleted} 个角色",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2200,
        )


    def _on_import_from_wwise(self):
        """从Wwise项目导入角色"""
        # 检查是否有当前项目
        if not self._current_project_id:
            InfoBar.warning(
                title="未选择项目",
                content="请先在项目页面创建或选择一个项目",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        # 显示处理中提示
        InfoBar.info(
            title="正在扫描",
            content="正在从Wwise项目中发现角色...",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000
        )

        try:
            from Source.Utility.wwise_character_discovery import discover_leaf_work_units_from_project
            from Source.UI.Interface.AIVoiceInterface.dialogs.wwise_workunit_import_dialog import WwiseWorkUnitImportDialog

            # 发现叶子 WorkUnit
            candidates = discover_leaf_work_units_from_project(self._current_project_id)
            if not candidates:
                InfoBar.warning(
                    title="未发现 WorkUnit",
                    content="未在 Actor-Mixer Hierarchy 下找到可导入的最低层 WorkUnit",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3200,
                )
                return

            # 弹窗让用户选择要导入的 WorkUnit
            dlg = WwiseWorkUnitImportDialog(self._main_window, candidates=candidates)
            if not dlg.exec():
                return
            selected_units = dlg.get_selected_candidates()
            if not selected_units:
                InfoBar.info(
                    title="未选择",
                    content="未选择任何 WorkUnit，已取消导入",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=2200,
                )
                return

            # 记录导入前已有名称，用于导入后自动定位一个新角色
            try:
                existed = {str(c.name or "").strip() for c in self._character_manager.characters}
            except Exception:
                existed = set()

            characters_data = []
            for u in selected_units:
                characters_data.append(
                    {
                        "name": str(u.name or "").strip(),
                        "reference_audio_path": str(u.reference_voice_path or "").strip(),
                        "avatar_path": "",
                    }
                )

            result = self._character_manager.batch_import(characters_data, skip_existing=True)
            if result.get("imported", 0) > 0:
                self._refresh_character_list()

                # 自动选中一个新导入的角色，方便直接看到 reference_audio 是否带入
                try:
                    for u in selected_units:
                        n = str(u.name or "").strip()
                        if n and n not in existed:
                            c = self._character_manager.get_by_name(n)
                            if c is not None:
                                self._select_character(c.id)
                                break
                except Exception:
                    pass

            from Source.UI.Interface.AIVoiceInterface.dialogs.import_result_dialog import ImportResultDialog
            ImportResultDialog(
                self._main_window,
                imported=int(result.get("imported", 0)),
                skipped=int(result.get("skipped", 0)),
                failed=int(result.get("failed", 0)),
            ).exec()

        except ValueError as e:
            # 项目配置错误（如未配置Wwise项目路径）
            InfoBar.error(
                title="配置错误",
                content=str(e),
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000
            )
        except FileNotFoundError as e:
            # Wwise项目文件不存在
            InfoBar.error(
                title="文件不存在",
                content=str(e),
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000
            )
        except Exception as e:
            # 其他错误
            InfoBar.error(
                title="导入失败",
                content=f"从Wwise导入角色时出错: {str(e)}",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000
            )
            import traceback
            traceback.print_exc()


    def _select_character(self, character_id: str):
        """选中角色（不置顶）"""
        self._character_manager.select(character_id)
        
        # 更新角色列表选中状态
        self.character_list_widget.update_selection(character_id)
        
        # 更新参考音频显示
        self._update_reference_audio_display()
        
        # 更新生成按钮状态
        self._update_generate_btn_state()

        # 刷新历史窗口（若已打开）
        try:
            self._refresh_history_window_if_open()
        except Exception:
            pass


    def _refresh_character_list(self):
        """刷新角色列表"""
        try:
            if hasattr(self.character_list_widget, "set_character_manager") and (self._character_manager is not None):
                self.character_list_widget.set_character_manager(self._character_manager)
            else:
                self.character_list_widget.refresh()
        except Exception:
            try:
                self.character_list_widget.refresh()
            except Exception:
                pass
        # 更新参考音频显示
        self._update_reference_audio_display()


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


