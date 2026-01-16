from typing import Optional

from PySide6.QtGui import QCloseEvent, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication

import changelog
import main
from packaging.version import Version
from PySide6.QtCore import QThread, QThreadPool, QTimer
from qfluentwidgets import FluentIcon, MSFluentWindow, NavigationItemPosition
from Source.Job.external_source_job import ExternalSourceJob
from Source.Job.game_project_job import GameProjectJob
from Source.Job.ovr_lip_sync_job import OVRLipSyncJob
from Source.Job.sample_job import SampleJob
from Source.Job.soundbank_job import SoundBankJob
from Source.Job.voice_job import VoiceJob
from Source.Job.work_environment_job import WorkEnvironmentJob
from Source.Job.wproj_job import WprojJob
from Source.title_bar import TitleBar
from Source.UI.Basic.changelog_window import ChangelogWindow
from Source.UI.Interface.ProjectInterface.project_interface import ProjectInterface
from Source.UI.Interface.setting_interface import SettingInterface
from Source.Job.indextts_job import IndexTTSJob
from Source.Job.indextts_download_job import IndexTTSDownloadJob
from Source.Job.indextts_env_job import IndexTTSEnvJob
from Source.UI.Interface.AIVoiceInterface.ai_voice_interface import AIVoiceInterface
from Source.Utility.config_utility import config_utility
from Source.Utility.dev_config_utility import dev_config_utility
from Source.Utility.wproj_utility import WprojUtility


class MainWindow(MSFluentWindow):
    """
    主窗口类，继承自 MSFluentWindow (qfluentwidgets 提供的带有 Fluent Design 风格的窗口基类)。
    """
    def __init__(self):
        self.isMicaEnabled = False
        super().__init__()

        self.threadpool = QThreadPool.globalInstance()
        self.threadpool.setMaxThreadCount(QThread.idealThreadCount() * 4)

        self.external_source_job = ExternalSourceJob(self)
        self.voice_job = VoiceJob(self)
        self.sample_job = SampleJob(self)
        self.soundbank_job = SoundBankJob(self)
        self.wproj_job = WprojJob(self)
        self.work_environment_job = WorkEnvironmentJob(self)
        self.game_project_job = GameProjectJob(self)
        self.ovr_lip_sync_job = OVRLipSyncJob(self)

        self.indextts_job = IndexTTSJob(self)
        self.indextts_download_job = IndexTTSDownloadJob(self)
        self.indextts_env_job = IndexTTSEnvJob(self)

        self.project_interface = ProjectInterface(self)
        self.setting_interface = SettingInterface(self)

        self.ai_voice_interface = AIVoiceInterface(self)

        # 项目页 Tab 与 AI语音 页 Tab 同步
        try:
            self.project_interface.project_tab_added.connect(self.ai_voice_interface.on_project_tab_added)
            self.project_interface.project_tab_removed.connect(self.ai_voice_interface.on_project_tab_removed)
            self.project_interface.project_tab_renamed.connect(self.ai_voice_interface.on_project_tab_renamed)
            self.project_interface.project_tab_switched.connect(self.ai_voice_interface.on_project_tab_switched)
            self.project_interface.project_tabs_swapped.connect(self.ai_voice_interface.on_project_tabs_swapped)
        except Exception:
            pass

        self.title_bar: TitleBar = TitleBar(self)
        self.init_title_bar()

        self.init_navigation()

        self.init_main_window()

        self._close_shortcut: QShortcut = QShortcut(QKeySequence.StandardKey.Close, self)
        self._close_shortcut.activated.connect(self.close)

        self.setMicaEffectEnabled(True)

        self._changelog_window: Optional[ChangelogWindow] = None
        self._last_interface_index: int | None = None
        self._ai_voice_welcome_request_id: int = 0
        self._ai_voice_welcome_shown_runtime: bool = False
        self.show_changelog()

    def _show_ai_voice_welcome_if_still_current(self, request_id: int):
        """仅当计时结束时仍停留在 AI语音 页时才显示欢迎弹窗。"""
        try:
            if request_id != self._ai_voice_welcome_request_id:
                return
            if self.stackedWidget.currentWidget() != self.ai_voice_interface:
                return
            shown = bool(self.ai_voice_interface.show_first_time_welcome_from_project())
            if shown:
                self._ai_voice_welcome_shown_runtime = True
        except Exception:
            pass

    def init_title_bar(self):
        """设置窗口的自定义标题栏"""
        self.setTitleBar(self.title_bar)

    def init_navigation(self):
        """初始化侧边导航栏，添加各个子界面"""
        self.addSubInterface(self.project_interface, FluentIcon.HOME, "项目", FluentIcon.HOME_FILL)

        self.addSubInterface(self.ai_voice_interface, FluentIcon.MICROPHONE, "AI语音", FluentIcon.MICROPHONE)

        self.addSubInterface(self.setting_interface, FluentIcon.SETTING, "设置", FluentIcon.SETTING, NavigationItemPosition.BOTTOM)

        self.stackedWidget.currentChanged.connect(self._on_interface_changed)

        self.navigationInterface.setCurrentItem(self.project_interface.objectName())
        self.stackedWidget.setCurrentWidget(self.project_interface)

    def init_main_window(self):
        """初始化主窗口的外观和位置"""
        self.setWindowTitle('音频工具箱')
        self.resize(1000, 700)
        self.setMinimumSize(1000, 700)

        icon = QIcon()
        icon.addFile("Resource/Icon New.png")
        self.setWindowIcon(icon)

        desktop = QApplication.screens()[0].availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        重写关闭事件处理函数。
        当窗口尝试关闭时调用，用于清理资源。
        """
        if self._changelog_window:
            self._changelog_window.close()
        self.setting_interface.close()
        self.project_interface.close()

        self.voice_job.uninit()
        self.sample_job.uninit()
        self.wproj_job.uninit()
        
        self.indextts_job.uninit()

        event.accept()

    def _on_interface_changed(self, index: int):
        """
        当导航界面切换时调用的回调函数。
        index: 当前界面的索引
        """
        prev = self._last_interface_index

        # 任何切换都会作废此前挂起的欢迎弹窗计时器（避免切走后才弹出）
        self._ai_voice_welcome_request_id += 1

        if index == self.stackedWidget.indexOf(self.setting_interface):
            self.setting_interface.refresh_project_setting_frame()

        if index == self.stackedWidget.indexOf(self.ai_voice_interface):
            self.ai_voice_interface.refresh()

            # 进入 AI语音 页时，确保 Tab 对齐当前项目
            try:
                pid = self.get_current_project_id()
                if pid:
                    self.ai_voice_interface.on_project_tab_switched(pid)
            except Exception:
                pass

            # 开发欢迎弹窗：force=true 时，每次应用启动进入 AI语音 延迟 0.5s 弹一次
            try:
                force_enabled = False
                try:
                    force_enabled = bool(dev_config_utility.force_ai_voice_welcome_every_time())
                except Exception:
                    force_enabled = False

                # force=true 时，每次应用启动仅弹一次（不是每次切页都弹）
                if force_enabled and (not self._ai_voice_welcome_shown_runtime):
                    request_id = self._ai_voice_welcome_request_id
                    QTimer.singleShot(
                        500,
                        lambda rid=request_id: self._show_ai_voice_welcome_if_still_current(rid),
                    )
            except Exception:
                pass

        self._last_interface_index = index

    def get_current_project_id(self) -> str | None:
        """获取当前选中的项目 ID"""
        return self.project_interface.get_current_project_id()

    def is_current_wwise_project_valid(self) -> bool:
        """检查当前 Wwise 项目是否有效"""
        project_id: str | None = self.get_current_project_id()
        return WprojUtility.is_wwise_project_valid(project_id)

    def show_changelog(self):
        """
        显示变更日志逻辑。
        检查上次运行的版本与当前版本，如果有更新则显示日志。
        """
        last_app_version = config_utility.get_config("LastAppVersion")
        display_log = ""

        if last_app_version is None:
            last_app_version = "0.0"

        if Version(last_app_version) < Version(main.APP_VERSION):
            for version, log in changelog.CHANGELOG.items():
                if Version(main.APP_VERSION) >= Version(version) > Version(last_app_version):
                    display_log = f"{display_log}\n\n{version}\n{log}" if display_log != "" else f"{version}\n{log}"

        if display_log != "":
            self._changelog_window = ChangelogWindow(display_log)
            self._changelog_window.close_signal.connect(self.show)
        else:
            self.show()

        config_utility.set_config("LastAppVersion", main.APP_VERSION)
