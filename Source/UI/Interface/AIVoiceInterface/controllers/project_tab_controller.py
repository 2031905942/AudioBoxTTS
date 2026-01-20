"""
Project Tab Controller Mixin

Handles project tab management and synchronization.
"""


class ProjectTabControllerMixin:
    """Mixin for project tab management operations."""

    def _on_ai_voice_tab_changed(self, index: int):
        """AI语音页面Tab切换时调用"""
        if index < 0 or index >= len(self._ai_voice_tab_bar.items):
            return
        project_id = self._ai_voice_tab_bar.items[index].routeKey()
        self._switch_to_project(project_id)

        # 同步"项目"页选中（避免两边项目不一致）
        try:
            p = getattr(self._main_window, "project_interface", None)
            bar = getattr(p, "project_tab_bar", None)
            if bar is not None:
                target_index = -1
                try:
                    for i, item in enumerate(getattr(bar, "items", [])):
                        if item.routeKey() == project_id:
                            target_index = int(i)
                            break
                except Exception:
                    target_index = -1

                if target_index >= 0:
                    cur = int(bar.currentIndex())
                    if cur != int(target_index):
                        bar.setCurrentIndex(int(target_index))
        except Exception:
            pass

    def _switch_to_project(self, project_id: str):
        """切换到指定项目"""
        if self._current_project_id == project_id:
            # 防止"Tab 重建/字典重建"后仍持有旧 manager，导致 UI 显示串台
            try:
                mgr = self._character_managers.get(project_id)
                if mgr is not None and self._character_manager is mgr:
                    return
            except Exception:
                return

        self._current_project_id = project_id

        # 获取或创建该项目的 CharacterManager
        if project_id not in self._character_managers:
            from Source.UI.Interface.AIVoiceInterface.models.character_manager import CharacterManager
            self._character_managers[project_id] = CharacterManager.create_for_project(project_id)
        self._character_manager = self._character_managers[project_id]

        # 让角色列表控件切到当前项目的数据源（否则 UI 仍绑定旧 manager）
        try:
            w = getattr(self, "character_list_widget", None)
            if w is not None and hasattr(w, "set_character_manager"):
                w.set_character_manager(self._character_manager)
        except Exception:
            pass

        # 获取或创建该项目的 TTSHistoryStore
        if project_id not in self._history_stores:
            from Source.Utility.tts_history_utility import TTSHistoryStore
            project_title = "未命名"
            try:
                from Source.Utility.config_utility import config_utility, ProjectData
                project_data = (config_utility.get_project_data_dict() or {}).get(project_id, {})
                project_title = project_data.get(ProjectData.TITLE_CONFIG_NAME, project_title)
            except Exception:
                pass
            self._history_stores[project_id] = TTSHistoryStore.create_for_project(project_id, project_name=project_title)

        # 更新角色列表（仅当 UI 已创建）
        try:
            if hasattr(self, "character_list_widget"):
                self._refresh_character_list()
        except Exception:
            pass

        # 清空生成结果（仅当输出区已创建）
        try:
            if hasattr(self, "_output_stack"):
                self._clear_output_state()
        except Exception:
            pass

        # 若历史窗口已打开，同步刷新（按当前项目 store）
        try:
            self._refresh_history_window_if_open()
        except Exception:
            pass

    def _clear_output_state(self):
        """清空生成结果状态"""
        try:
            self._output_wav_paths = ["", "", ""]
            for w in getattr(self, "output_player_widgets", []):
                w.set_audio_path("")
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

    def on_project_tab_added(self, project_id: str, title: str):
        """项目Tab添加时调用"""
        from qfluentwidgets import FluentIcon
        from Source.UI.Interface.AIVoiceInterface.models.character_manager import CharacterManager
        from Source.Utility.tts_history_utility import TTSHistoryStore

        # 添加TabBar项
        tab_item = self._ai_voice_tab_bar.addTab(project_id, title, FluentIcon.MICROPHONE)
        tab_item.setAutoFillBackground(True)

        # 预创建该项目的管理器
        if project_id not in self._character_managers:
            self._character_managers[project_id] = CharacterManager.create_for_project(project_id)
        if project_id not in self._history_stores:
            self._history_stores[project_id] = TTSHistoryStore.create_for_project(project_id, project_name=title)

    def on_project_tab_removed(self, project_id: str):
        """项目Tab删除时调用"""
        from Source.UI.Interface.AIVoiceInterface.models.character_manager import CharacterManager

        # 查找并移除TabBar项
        index = self._find_tab_index(project_id)
        if index >= 0:
            self._ai_voice_tab_bar.removeTab(index)

        # 清理管理器
        self._character_managers.pop(project_id, None)
        self._history_stores.pop(project_id, None)

        # 如果删除的是当前项目，切换到第一个项目
        if self._current_project_id == project_id:
            self._current_project_id = None
            if len(self._ai_voice_tab_bar.items) > 0:
                first_project_id = self._ai_voice_tab_bar.items[0].routeKey()
                self._switch_to_project(first_project_id)
            else:
                try:
                    self._character_manager = CharacterManager()
                except Exception:
                    self._character_manager = None
                try:
                    w = getattr(self, "character_list_widget", None)
                    if w is not None and self._character_manager is not None and hasattr(w, "set_character_manager"):
                        w.set_character_manager(self._character_manager)
                    if hasattr(self, "character_list_widget"):
                        self._refresh_character_list()
                except Exception:
                    pass

    def on_project_tab_renamed(self, project_id: str, new_title: str):
        """项目Tab重命名时调用"""
        tab_item = self._ai_voice_tab_bar.tab(project_id)
        if tab_item:
            tab_item.setText(new_title)
        try:
            store = self._history_stores.get(project_id)
            if store is not None:
                store.set_project_name(new_title)
        except Exception:
            pass

    def on_project_tab_switched(self, project_id: str):
        """项目Tab切换时调用（来自项目页面的切换）"""
        index = self._find_tab_index(project_id)
        if index < 0:
            return

        # 关键修复：即便 index == currentIndex，也要确保内部 manager/UI 已绑定到该 project
        if index != self._ai_voice_tab_bar.currentIndex():
            self._ai_voice_tab_bar.setCurrentIndex(index)
            return

        # currentChanged 不会触发时（例如启动时默认 index 已是 0），这里手动切一次
        try:
            self._switch_to_project(project_id)
        except Exception:
            pass

    def on_project_tabs_swapped(self, index1: int, index2: int):
        """项目Tab顺序交换时调用"""
        # TabBar 不支持直接交换：这里选择重建一次，保证顺序与"项目"页一致。
        # 备注：即使不重建，上面的 _on_ai_voice_tab_changed 也已按 project_id 同步，避免 index 错配。
        try:
            current_project_id = str(getattr(self._main_window, "get_current_project_id")() or "")
        except Exception:
            current_project_id = ""

        try:
            self.init_tabs_from_projects()
        except Exception:
            return

        if current_project_id:
            try:
                self.on_project_tab_switched(current_project_id)
            except Exception:
                pass
        elif len(self._ai_voice_tab_bar.items) > 0:
            try:
                self._ai_voice_tab_bar.setCurrentIndex(0)
            except Exception:
                pass

    def _find_tab_index(self, project_id: str) -> int:
        """查找项目ID对应的Tab索引"""
        for i, item in enumerate(self._ai_voice_tab_bar.items):
            if item.routeKey() == project_id:
                return i
        return -1

    def init_tabs_from_projects(self):
        """从项目数据初始化所有Tab（启动时调用）"""
        from qfluentwidgets import FluentIcon
        from Source.Utility.config_utility import config_utility, ProjectData
        from Source.UI.Interface.AIVoiceInterface.models.character_manager import CharacterManager
        from Source.Utility.tts_history_utility import TTSHistoryStore

        # 清空旧 tab，避免重复初始化（阻止 currentChanged 回调触发切换逻辑）
        try:
            self._ai_voice_tab_bar.blockSignals(True)
        except Exception:
            pass

        try:
            while len(self._ai_voice_tab_bar.items) > 0:
                self._ai_voice_tab_bar.removeTab(0)
        except Exception:
            pass

        # 重建数据容器，避免保留已删除项目的数据
        try:
            self._character_managers = {}
            self._history_stores = {}
            self._character_manager = None
            self._current_project_id = None
        except Exception:
            pass

        project_data_dict = config_utility.get_project_data_dict()
        for project_id, project_data in project_data_dict.items():
            project_title = project_data.get(ProjectData.TITLE_CONFIG_NAME, "未命名")
            tab_item = self._ai_voice_tab_bar.addTab(project_id, project_title, FluentIcon.MICROPHONE)
            tab_item.setAutoFillBackground(True)

            # 预创建管理器
            self._character_managers[project_id] = CharacterManager.create_for_project(project_id)
            self._history_stores[project_id] = TTSHistoryStore.create_for_project(project_id, project_name=project_title)
        # 当前项目由 _create_tab_bar 或外部信号决定

        try:
            self._ai_voice_tab_bar.blockSignals(False)
        except Exception:
            pass
