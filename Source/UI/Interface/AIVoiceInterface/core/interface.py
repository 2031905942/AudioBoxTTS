"""
AI Voice Interface - Main Class

This module contains the main AIVoiceInterface class that inherits from all controller mixins.
"""
import os
import subprocess
from typing import Optional

from PySide6.QtCore import (
    Qt, QEvent, QTimer, QThreadPool, QObject, Signal, QRunnable,
    QUrl, QStandardPaths
)
from PySide6.QtGui import (
    QGuiApplication, QShortcut, QKeySequence, QAction
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QFileDialog, QGridLayout, QHBoxLayout,
    QWidget, QSizePolicy, QStackedLayout, QStackedWidget, QLabel, QDialog
)
from qfluentwidgets import (
    BodyLabel, CardWidget, FluentIcon, InfoBar, InfoBarPosition,
    MessageBox, MessageBoxBase, PlainTextEdit, PrimaryPushButton,
    ProgressBar, PushButton, RadioButton, Slider, StrongBodyLabel,
    TitleLabel, ToolTipFilter, ToolTipPosition, TransparentToolButton,
    TeachingTip, TeachingTipTailPosition, TextBrowser, TabCloseButtonDisplayMode,
)

from Source.Utility.config_utility import config_utility, ProjectData
from Source.Utility.dev_config_utility import dev_config_utility
from Source.Utility.indextts_preflight_utility import IndexTTSPreflightUtility
from Source.Utility.indextts_utility import IndexTTSUtility, IndexTTSUtilityFactory
from Source.Utility.tts_history_utility import tts_history_store, TTSHistoryStore
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.UI.Basic.project_tab_bar import ProjectTabBar, ProjectTabItem
from Source.UI.Interface.AIVoiceInterface.models.character_manager import CharacterManager, Character
from Source.UI.Interface.AIVoiceInterface.dialogs.character_dialog import CharacterDialog
from Source.UI.Interface.AIVoiceInterface.widgets.character_list_widget import CharacterListWidget
from Source.UI.Interface.AIVoiceInterface.dialogs.batch_delete_characters_dialog import BatchDeleteCharactersDialog
from Source.UI.Interface.AIVoiceInterface.widgets.audio_player_widget import (
    ReferenceAudioPlayerWidget,
    ResultAudioPlayerWidget,
)
from Source.UI.Interface.AIVoiceInterface.windows.history_window import AIVoiceHistoryWindow

# Import controller mixins
from Source.UI.Interface.AIVoiceInterface.controllers.ui_builder import UIBuilderMixin
from Source.UI.Interface.AIVoiceInterface.controllers.character_operations import CharacterOperationsMixin
from Source.UI.Interface.AIVoiceInterface.controllers.model_management import ModelManagementMixin
from Source.UI.Interface.AIVoiceInterface.controllers.download_manager import DownloadManagerMixin
from Source.UI.Interface.AIVoiceInterface.controllers.audio_operations import AudioOperationsMixin
from Source.UI.Interface.AIVoiceInterface.controllers.generation_controller import GenerationControllerMixin
from Source.UI.Interface.AIVoiceInterface.controllers.history_manager import HistoryManagerMixin
from Source.UI.Interface.AIVoiceInterface.controllers.project_tab_controller import ProjectTabControllerMixin
from Source.UI.Interface.AIVoiceInterface.controllers.onboarding_guide import OnboardingGuideMixin

# Import dialogs
from Source.UI.Interface.AIVoiceInterface.dialogs.model_actions import LocalModelActionsDialog

# Import overlays
from Source.UI.Interface.AIVoiceInterface.core.ui_overlays import DragDropOverlay


class EnvCheckSignals(QObject):
    """环境检测信号类"""
    finished = Signal(bool, str)  # is_ready, message


class EnvCheckWorker(QRunnable):
    """环境检测后台任务"""

    def __init__(self):
        super().__init__()
        self.signals = EnvCheckSignals()

    def run(self):
        """在后台线程执行环境检测"""
        try:
            from Source.Job.indextts_env_job import IndexTTSEnvJob
            is_ready, msg = IndexTTSEnvJob.check_env_ready()
            self.signals.finished.emit(is_ready, msg)
        except Exception as e:
            self.signals.finished.emit(False, f"检测失败: {str(e)}")


class AIVoiceInterface(
    QFrame,
    UIBuilderMixin,
    CharacterOperationsMixin,
    ModelManagementMixin,
    DownloadManagerMixin,
    AudioOperationsMixin,
    GenerationControllerMixin,
    HistoryManagerMixin,
    ProjectTabControllerMixin,
    OnboardingGuideMixin
):
    """AI语音界面主类

    整合所有功能模块的主界面类。继承自QFrame和多个功能混入类。
    """

    def __init__(self, parent):
        super().__init__(parent)
        from Source.main_window import MainWindow
        # noinspection PyTypeChecker
        self._main_window: MainWindow = parent

        self.setObjectName("ai_voice_interface")

        # AI 语音页的底色（各大组件/卡片之外的背景）
        try:
            self.setAutoFillBackground(True)
        except Exception:
            pass
        try:
            self.setStyleSheet("#ai_voice_interface { background-color: #e5e5e5; }")
        except Exception:
            pass

        # 当前项目ID
        self._current_project_id: Optional[str] = None

        # 按项目隔离的管理器字典
        self._character_managers: dict[str, CharacterManager] = {}
        self._history_stores: dict[str, TTSHistoryStore] = {}

        # 角色管理器（当前项目的，会根据Tab切换而变化）
        self._character_manager: Optional[CharacterManager] = None

        # 记录主窗口"当前项目"快照，供 TabBar 初始化后对齐
        try:
            self._preferred_project_id: Optional[str] = self._main_window.get_current_project_id()
        except Exception:
            self._preferred_project_id = None

        # 播放器
        self._player: Optional[QMediaPlayer] = None
        self._audio_output: Optional[QAudioOutput] = None

        # 参考音频播放器（独立）
        self._ref_player: Optional[QMediaPlayer] = None
        self._ref_audio_output: Optional[QAudioOutput] = None

        # 环境检测状态
        self._env_check_pending = False
        self._env_check_request_id = 0
        self._env_check_worker = None

        # 环境/模型是否就绪
        self._env_ready = False
        self._model_ready = False

        # 生成状态：用于区分"模型加载完成"和"语音合成完成"都走 job_completed(True)
        self._synthesis_in_progress = False

        # 启用拖拽支持
        self.setAcceptDrops(True)
        self._drag_overlay = DragDropOverlay(self)
        self._drag_overlay.audio_dropped.connect(self._on_audio_dropped)
        self._drag_overlay.hide()

        self._init_ui()
        self._connect_signals()

        # 启动时根据配置同步“云服务模式”按钮状态
        try:
            self._sync_cloud_mode_ui_from_config()
        except Exception:
            pass

        # 首次使用引导（运行期缓存，避免多次弹出/被 GC）
        self._welcome_dialog = None
        self._quick_guide_dialog = None
        self._quick_guide_step_index = 0
        self._welcome_shown_runtime = False

        # 历史记录窗口（非模态）
        self._history_window = None
        self._history_pending = None

    def _sync_cloud_mode_ui_from_config(self) -> None:
        """根据 config/tts_config.json 同步按钮状态。

        若当前为 remote：禁用本地入口，并尝试做一次远程健康检查（load_model）。
        """
        mode = "local"
        try:
            mode = str(IndexTTSUtilityFactory.get_current_mode() or "local")
        except Exception:
            mode = "local"

        enabled = (mode == "remote")

        # 复用 OnboardingGuideMixin 里同名按钮
        btn_online = getattr(self, "use_online_model_btn", None)
        btn_local = getattr(self, "use_local_model_btn", None)

        if btn_online is not None:
            try:
                btn_online.setText("取消云服务" if enabled else "使用线上模型")
            except Exception:
                pass
            try:
                btn_online.setToolTip(
                    "点击取消云服务并恢复本地模型入口" if enabled else "点击启用 IndexTTS2 云服务（远程推理）"
                )
            except Exception:
                pass
            try:
                if enabled:
                    btn_online.setStyleSheet(getattr(self, "_load_btn_style_unload", ""))
                else:
                    btn_online.setStyleSheet(getattr(self, "_load_btn_style", ""))
            except Exception:
                pass

        if btn_local is not None:
            try:
                btn_local.setEnabled(not enabled)
            except Exception:
                pass
            try:
                btn_local.setToolTip(
                    "云服务模式已启用：本地模型入口已禁用" if enabled else "打开本地 IndexTTS2 模型管理（下载/加载）"
                )
            except Exception:
                pass

        # remote 模式下，尝试在启动时检查一次远程服务就绪状态
        if enabled:
            try:
                job = getattr(self._main_window, "indextts_job", None)
                if job is not None and (not bool(job.is_model_loaded)):
                    job.load_model_action("", use_fp16=False, use_cuda_kernel=False, use_deepspeed=False)
            except Exception:
                pass

        try:
            self._update_model_status()
            self._update_generate_btn_state()
        except Exception:
            pass

    def refresh(self):
        """进入页面或项目变更时刷新 UI。

        说明：重构前 `MainWindow` 会在切换到 AI 语音页时调用 `refresh()`。
        重构后仍需保留该公共方法以保持兼容。
        """
        # 重新从配置加载/对齐项目 Tab（容错：某些时机 TabBar 尚未完全初始化）
        try:
            if hasattr(self, "init_tabs_from_projects") and hasattr(self, "_ai_voice_tab_bar"):
                self.init_tabs_from_projects()
        except Exception:
            pass

        # 对齐到主窗口当前项目
        try:
            pid = None
            try:
                pid = self._main_window.get_current_project_id()
            except Exception:
                pid = None
            if pid and hasattr(self, "on_project_tab_switched"):
                self.on_project_tab_switched(pid)
        except Exception:
            pass

        # 刷新角色列表/按钮状态（尽量不抛异常影响主流程）
        try:
            if hasattr(self, "_refresh_character_list"):
                self._refresh_character_list()
        except Exception:
            pass
        try:
            if hasattr(self, "_update_generate_btn_state"):
                self._update_generate_btn_state()
        except Exception:
            pass

        # 欢迎弹窗由 MainWindow 在“进入 AI语音 页”时触发。


    def show_first_time_welcome_from_project(self) -> bool:
        """显示 AI语音 欢迎弹窗（用于 MainWindow 在进入 AI语音 页时触发）。

        返回：本次是否实际弹出了弹窗
        """
        # 运行期防抖：避免重复 show
        if bool(getattr(self, "_welcome_shown_runtime", False)):
            return False

        # 规则：仅依赖 dev.default.json/dev.json
        # - 默认仓库：config/dev.default.json 中 force=true，会弹出欢迎弹窗
        # - 用户点击“OK，不再显示”后，会写入本地 config/dev.json force=false 覆盖
        force_enabled = False
        try:
            force_enabled = bool(dev_config_utility.force_ai_voice_welcome_every_time())
        except Exception:
            force_enabled = False

        if not force_enabled:
            return False

        try:
            from Source.UI.Interface.AIVoiceInterface.dialogs.welcome import AIVoiceWelcomeDialog
        except Exception:
            return False

        def _start_guide():
            try:
                from PySide6.QtCore import QTimer
            except Exception:
                return

            # 让弹窗先关闭，再启动教学引导，避免 focus/overlay 抢占
            def _run():
                try:
                    self._run_quick_guide_step_teaching_tip(0)
                except Exception:
                    pass

            QTimer.singleShot(120, _run)

        try:
            if self._welcome_dialog is None:
                self._welcome_dialog = AIVoiceWelcomeDialog(self._main_window, on_start_guide=_start_guide)
            dlg = self._welcome_dialog
            try:
                dlg.show()
                dlg.raise_()
                dlg.activateWindow()
            except Exception:
                # 兜底：即便 show 失败也不崩
                pass

            self._welcome_shown_runtime = True
            return True
        except Exception:
            return False

    @staticmethod
    def _wrap_path_for_label(path: str) -> str:
        """给路径插入零宽断点，避免对话框因长路径被撑宽。"""
        if not path:
            return ""
        # Allow line breaks after separators without changing what user sees.
        return path.replace("\\", "\\\u200b").replace("/", "/\u200b")

    @staticmethod
    def _tune_message_box(msg: MessageBox) -> None:
        """统一 MessageBox 宽度与按钮尺寸，避免按钮文字显示不全。"""
        try:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                min_w = min(760, int(avail.width() * 0.78))
                max_w = int(avail.width() * 0.90)
            else:
                min_w, max_w = 720, 980

            msg.setMinimumWidth(max(560, min_w))
            msg.setMaximumWidth(max_w)
        except Exception:
            pass

        # 统一按钮尺寸
        for btn in (getattr(msg, "yesButton", None), getattr(msg, "cancelButton", None)):
            if btn is None:
                continue
            try:
                btn.setMinimumWidth(150)
                btn.setMinimumHeight(34)
            except Exception:
                pass

        # 处理插入到 buttonLayout 的额外按钮
        try:
            layout = getattr(msg, "buttonLayout", None)
            if layout is not None:
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    w = item.widget() if item is not None else None
                    if w is None:
                        continue
                    try:
                        w.setMinimumWidth(150)
                        w.setMinimumHeight(34)
                    except Exception:
                        pass
        except Exception:
            pass

    def dragEnterEvent(self, event):
        """处理拖拽进入事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.wav', '.mp3', '.flac', '.ogg')):
                event.acceptProposedAction()
                # 显示全界面遮罩层（拦截 drop，避免文本框等抢占）
                try:
                    self._drag_overlay.setGeometry(self.rect())
                    self._drag_overlay.show()
                    self._drag_overlay.raise_()
                except Exception:
                    pass
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        """处理拖拽离开事件"""
        try:
            self._drag_overlay.hide()
        except Exception:
            pass
        self.update()

    def dropEvent(self, event):
        """处理拖拽放下事件"""
        # 理论上 drop 会被 overlay 接走；这里兜底处理
        try:
            self._drag_overlay.hide()
        except Exception:
            pass
        self.update()
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.wav', '.mp3', '.flac', '.ogg')):
                self._on_audio_dropped(file_path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            self._drag_overlay.setGeometry(self.rect())
        except Exception:
            pass

    def _connect_signals(self):
        """连接信号槽"""
        # 模型控制（面板入口）
        try:
            self.use_local_model_btn.clicked.connect(self._on_use_local_model_clicked)
        except Exception:
            pass
        try:
            self.use_online_model_btn.clicked.connect(self._on_use_online_model_clicked)
        except Exception:
            pass

        # 本地模型弹窗内按钮：在弹窗创建时再绑定（避免此时按钮尚未创建）

        # 参考音频 (已在创建组件时连接)
        # self.import_audio_btn.clicked.connect(self._on_import_audio)
        # self.ref_play_btn.clicked.connect(self._on_play_reference)

        # 生成音频
        self.generate_btn.clicked.connect(self._on_generate_clicked)

        # 快捷键：Alt+Enter 生成（焦点在输入框时也可用）
        try:
            sc1 = QShortcut(QKeySequence(Qt.KeyboardModifier.AltModifier | Qt.Key.Key_Return), self)
            sc1.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc1.activated.connect(lambda: self._on_generate_clicked() if self.generate_btn.isEnabled() else None)

            sc2 = QShortcut(QKeySequence(Qt.KeyboardModifier.AltModifier | Qt.Key.Key_Enter), self)
            sc2.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc2.activated.connect(lambda: self._on_generate_clicked() if self.generate_btn.isEnabled() else None)
        except Exception:
            pass
        # self.output_play_btn.clicked.connect(self._on_play_output)
        # self.download_audio_btn.clicked.connect(self._on_download_audio)

        # 情感模式切换
        self.emo_mode_same.toggled.connect(self._on_emo_mode_changed)
        self.emo_mode_vector.toggled.connect(self._on_emo_mode_changed)

        # IndexTTSJob 信号
        self._main_window.indextts_job.progress_updated.connect(self._on_progress_updated)
        self._main_window.indextts_job.job_completed.connect(self._on_job_completed)
        try:
            self._main_window.indextts_job.variant_generated.connect(self._on_variant_generated)
        except Exception:
            pass
        try:
            self._main_window.indextts_job.variant_progress.connect(self._on_variant_progress)
        except Exception:
            pass

        # IndexTTSDownloadJob 信号
        self._main_window.indextts_download_job.job_completed.connect(self._on_download_job_completed)

    def _ensure_local_model_dialog(self) -> LocalModelActionsDialog | None:
        """确保本地模型弹窗已创建，并绑定按钮槽函数。"""
        dlg = getattr(self, "_local_model_dialog", None)
        if dlg is not None:
            return dlg
        try:
            dlg = LocalModelActionsDialog(self._main_window)
            self._local_model_dialog = dlg
            self.download_btn = dlg.download_btn
            self.load_model_btn = dlg.load_model_btn

            # FP16 开关引用（可能不存在，需判空）
            self.fp16_checkbox = getattr(dlg, "fp16_checkbox", None)
            self.fp16_hint_label = getattr(dlg, "fp16_hint_label", None)

            # 统一样式保持一致
            try:
                self.download_btn.setMinimumHeight(40)
                self.download_btn.setIconSize(self._model_btn_icon_size)
                self.download_btn.setToolTip("下载 IndexTTS2 所需的依赖和模型文件（约 5GB）")
                self.download_btn.setStyleSheet(self._download_btn_style_download)
            except Exception:
                pass
            try:
                self.load_model_btn.setMinimumHeight(40)
                self.load_model_btn.setIconSize(self._model_btn_icon_size)
                self.load_model_btn.setToolTip("加载模型到显存（首次约需 20-30 秒）")
                self.load_model_btn.setStyleSheet(self._load_btn_style)
            except Exception:
                pass

            # 绑定按钮槽（避免重复连接）
            try:
                from PySide6.QtCore import Qt

                self.download_btn.clicked.connect(self._on_download_clicked, Qt.ConnectionType.UniqueConnection)
                self.load_model_btn.clicked.connect(self._on_load_model_clicked, Qt.ConnectionType.UniqueConnection)
            except Exception:
                try:
                    self.download_btn.clicked.connect(self._on_download_clicked)
                except Exception:
                    pass
                try:
                    self.load_model_btn.clicked.connect(self._on_load_model_clicked)
                except Exception:
                    pass

            # 绑定 FP16 开关：仅当用户手动切换时才写入持久化配置
            try:
                if self.fp16_checkbox is not None:
                    def _on_fp16_toggled(checked: bool):
                        try:
                            config_utility.set_config("AIVoice.IndexTTS2.UseFP16", bool(checked))
                        except Exception:
                            pass
                        try:
                            self._refresh_fp16_hint_text()
                        except Exception:
                            pass

                    # SwitchButton 使用 checkedChanged；部分控件也可能是 toggled
                    try:
                        self.fp16_checkbox.checkedChanged.connect(_on_fp16_toggled)
                    except Exception:
                        self.fp16_checkbox.toggled.connect(_on_fp16_toggled)
            except Exception:
                pass

            # 初始化 FP16 默认值与提示文案
            try:
                self._apply_fp16_default(auto_only=True)
            except Exception:
                pass

            # 创建完成后，用当前快照刷新一次按钮显示（避免仍停留在默认样式/文案）
            try:
                self._update_download_btn_state(
                    bool(getattr(self, "_env_ok_fast", False)),
                    bool(getattr(self, "_model_files_ok", False)),
                )
            except Exception:
                pass
            try:
                self._update_model_status()
            except Exception:
                pass
            return dlg
        except Exception:
            return None

    # ==================== 角色管理 ====================
    def _is_character_name_unique(self, name: str, *, exclude_id: str | None = None) -> bool:
        """检查角色名称是否唯一

        Args:
            name: 要检查的角色名称
            exclude_id: 排除的角色ID（用于编辑时排除当前角色）

        Returns:
            bool: 名称是否唯一
        """
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

    def _recommend_fp16(self) -> tuple[bool, str]:
        """根据主机配置智能推荐 FP16 开关。

        Returns:
            tuple[bool, str]: (是否推荐开启, 推荐原因)
        """
        smi = {}
        try:
            smi = self._run_nvidia_smi() or {}
        except Exception:
            smi = {}

        def _to_int(x):
            try:
                return int(float(str(x).strip()))
            except Exception:
                return None

        total_mb = _to_int(smi.get("mem_total_mb"))
        free_mb = _to_int(smi.get("mem_free_mb"))
        gpu_name = str(smi.get("gpu_name") or "").strip()

        # 无法识别 GPU：保守默认关闭，但提示用户按需开启
        if not total_mb:
            return False, "未检测到 NVIDIA 显卡信息：默认关闭。若加载失败/显存不足，可开启 FP16。"

        total_gb = total_mb / 1024.0
        free_gb = (free_mb / 1024.0) if free_mb is not None else None

        # 经验阈值：
        # - 8GB 及以下：强烈建议 FP16
        # - 12GB：通常建议 FP16（尤其是空闲不足时）
        # - 16GB+：可默认关闭
        if total_mb <= 8192:
            reason = f"检测到 GPU {gpu_name or ''} 显存约 {total_gb:.1f}GB：建议开启 FP16 以降低显存占用。"
            if free_gb is not None:
                reason += f" 当前空闲约 {free_gb:.1f}GB。"
            return True, reason

        if total_mb <= 12288:
            if free_mb is not None and free_mb < 9000:
                return True, f"检测到显存约 {total_gb:.1f}GB（空闲偏紧约 {free_gb:.1f}GB）：建议开启 FP16。"
            return True, f"检测到显存约 {total_gb:.1f}GB：开启 FP16 通常更稳、更省显存。"

        # 16GB 及以上
        if free_mb is not None and free_mb < 12000:
            return True, f"虽然总显存约 {total_gb:.1f}GB，但当前空闲仅约 {free_gb:.1f}GB：建议开启 FP16。"
        return False, f"检测到显存约 {total_gb:.1f}GB：默认关闭 FP16（需要更省显存时可开启）。"

    def _refresh_fp16_hint_text(self) -> None:
        """刷新FP16提示文本"""
        lbl = getattr(self, "fp16_hint_label", None)
        if lbl is None:
            return

        saved = self._get_fp16_saved_preference()
        rec, reason = self._recommend_fp16()
        if saved is None:
            lbl.setText(f"自动推荐：{'开启' if rec else '关闭'}。{reason}")
        else:
            lbl.setText(f"已按你的设置：{'开启' if saved else '关闭'}。{reason}")

    def _apply_fp16_default(self, *, auto_only: bool = True) -> None:
        """将 FP16 默认值应用到弹窗开关。

        Args:
            auto_only: 仅当用户没有保存偏好时才自动设置
        """
        cb = getattr(self, "fp16_checkbox", None)
        if cb is None:
            return

        saved = self._get_fp16_saved_preference()
        if auto_only and (saved is not None):
            # 用户有明确偏好：不自动覆盖
            try:
                cb.setChecked(bool(saved))
            except Exception:
                pass
            self._refresh_fp16_hint_text()
            return

        rec, _ = self._recommend_fp16()
        try:
            cb.setChecked(bool(rec) if saved is None else bool(saved))
        except Exception:
            pass
        self._refresh_fp16_hint_text()

    def _run_nvidia_smi(self) -> dict:
        """尝试通过 nvidia-smi 获取 CUDA/显存信息。

        返回 dict，可能为空（例如没有 NVIDIA 驱动/命令）。
        """
        try:
            import subprocess

            # 1) 获取 CUDA 版本（nvidia-smi 顶部行包含 CUDA Version）
            p = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            out = (p.stdout or "").splitlines()
            cuda_ver = ""
            driver_ver = ""
            if out:
                # 示例：| NVIDIA-SMI 555.85 ... CUDA Version: 12.5 |
                first = out[0]
                if "CUDA Version" in first:
                    try:
                        cuda_ver = first.split("CUDA Version:", 1)[1].split("|")[0].strip()
                    except Exception:
                        cuda_ver = ""
                if "NVIDIA-SMI" in first:
                    try:
                        # NVIDIA-SMI 后面的版本号
                        driver_ver = first.split("NVIDIA-SMI", 1)[1].strip().split()[0]
                    except Exception:
                        driver_ver = ""

            # 2) GPU 名称 + 显存（首张卡）
            q = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,memory.used,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            row = (q.stdout or "").strip().splitlines()
            gpu_name = ""
            mem_total = ""
            mem_used = ""
            mem_free = ""
            if row:
                parts = [p.strip() for p in row[0].split(",")]
                if len(parts) >= 4:
                    gpu_name, mem_total, mem_used, mem_free = parts[:4]

            return {
                "cuda_version": cuda_ver,
                "driver_version": driver_ver,
                "gpu_name": gpu_name,
                "mem_total_mb": mem_total,
                "mem_used_mb": mem_used,
                "mem_free_mb": mem_free,
            }
        except Exception:
            return {}
