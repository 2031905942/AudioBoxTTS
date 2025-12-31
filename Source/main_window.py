from typing import Optional  # 导入 Optional 类型提示，用于表示变量可以是某种类型或 None

# 导入 PySide6 库的 GUI 组件，PySide6 是 Qt 框架的 Python 绑定
from PySide6.QtGui import QCloseEvent, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication

import changelog  # 导入变更日志模块
import main  # 导入主模块，通常包含全局配置或入口点信息
from packaging.version import Version  # 导入 Version 类，用于方便地进行版本号比较
from PySide6.QtCore import QThread, QThreadPool  # 导入核心线程功能
# 导入 qfluentwidgets 库，这是一个基于 PyQt/PySide 的 Fluent Design 风格组件库
from qfluentwidgets import FluentIcon, MSFluentWindow, NavigationItemPosition
# 导入各种业务逻辑处理类 (Job)，负责具体的后台任务
from Source.Job.external_source_job import ExternalSourceJob
from Source.Job.game_project_job import GameProjectJob
from Source.Job.ovr_lip_sync_job import OVRLipSyncJob
from Source.Job.sample_job import SampleJob
from Source.Job.soundbank_job import SoundBankJob
# from Source.Job.tts_job import TTSJob
from Source.Job.voice_job import VoiceJob
from Source.Job.work_environment_job import WorkEnvironmentJob
from Source.Job.wproj_job import WprojJob
from Source.title_bar import TitleBar  # 导入自定义标题栏
from Source.UI.Basic.changelog_window import ChangelogWindow  # 导入变更日志窗口 UI
from Source.UI.Interface.ProjectInterface.project_interface import ProjectInterface  # 导入项目界面
# from Source.UI.Interface.TTSInterface.tts_interface import TTSInterface
from Source.UI.Interface.setting_interface import SettingInterface  # 导入设置界面
# IndexTTS2
from Source.Job.indextts_job import IndexTTSJob
from Source.Job.indextts_download_job import IndexTTSDownloadJob
from Source.Job.indextts_env_job import IndexTTSEnvJob
from Source.UI.Interface.AIVoiceInterface.ai_voice_interface import AIVoiceInterface
# 配置工具
from Source.Utility.config_utility import config_utility  # 导入配置工具
from Source.Utility.wproj_utility import WprojUtility  # 导入 Wwise 项目工具


class MainWindow(MSFluentWindow):
    """
    主窗口类，继承自 MSFluentWindow (qfluentwidgets 提供的带有 Fluent Design 风格的窗口基类)。
    """
    def __init__(self):
        self.isMicaEnabled = False  # 初始化 Mica 特效标志位 (Windows 11 的一种半透明材质效果)
        super().__init__()  # 调用父类构造函数，初始化窗口

        # 获取全局线程池实例，用于管理后台线程
        self.threadpool = QThreadPool.globalInstance()
        # 设置最大线程数，这里设置为理想线程数 (通常是 CPU 核心数) 的 4 倍
        self.threadpool.setMaxThreadCount(QThread.idealThreadCount() * 4)

        # 初始化各种业务逻辑 Job 对象，传入 self (MainWindow 实例) 以便 Job 可以访问主窗口资源
        self.external_source_job = ExternalSourceJob(self)  # 处理外部源的任务
        self.voice_job = VoiceJob(self)  # 处理语音相关的任务
        self.sample_job = SampleJob(self)  # 处理样本相关的任务
        self.soundbank_job = SoundBankJob(self)  # 处理 SoundBank (音频库) 的任务
        # self.tts_job = TTSJob(self)
        self.wproj_job = WprojJob(self)  # 处理 Wwise 项目文件的任务
        self.work_environment_job = WorkEnvironmentJob(self)  # 处理工作环境配置的任务
        self.game_project_job = GameProjectJob(self)  # 处理游戏项目的任务
        self.ovr_lip_sync_job = OVRLipSyncJob(self)  # 处理 OVR 口型同步的任务

        # IndexTTS2: AI 语音合成 Job
        self.indextts_job = IndexTTSJob(self)
        self.indextts_download_job = IndexTTSDownloadJob(self)
        self.indextts_env_job = IndexTTSEnvJob(self)

        # 初始化 UI 界面对象
        self.project_interface = ProjectInterface(self)  # 项目主界面
        # self.tts_interface = TTSInterface(self)
        self.setting_interface = SettingInterface(self)  # 设置界面

        # IndexTTS2: AI 语音界面
        self.ai_voice_interface = AIVoiceInterface(self)

        # 初始化自定义标题栏
        self.title_bar: TitleBar = TitleBar(self)
        self.init_title_bar()

        # 初始化导航栏 (左侧菜单)
        self.init_navigation()

        # 初始化主窗口的基本属性 (大小、图标等)
        self.init_main_window()

        # 创建一个快捷键对象，绑定标准关闭键 (通常是 Ctrl+Q 或 Alt+F4 等)，触发 self.close
        self._close_shortcut: QShortcut = QShortcut(QKeySequence.StandardKey.Close, self)
        self._close_shortcut.activated.connect(self.close)

        # 启用 Mica 特效 (如果系统支持)
        self.setMicaEffectEnabled(True)

        # 初始化变更日志窗口变量，类型提示为 Optional[ChangelogWindow]
        self._changelog_window: Optional[ChangelogWindow] = None
        # 尝试显示变更日志 (如果是新版本)
        self.show_changelog()

    def init_title_bar(self):
        """设置窗口的自定义标题栏"""
        self.setTitleBar(self.title_bar)

    def init_navigation(self):
        """初始化侧边导航栏，添加各个子界面"""
        # 添加项目界面到导航栏
        # 参数: 界面部件, 图标, 显示文本, 选中时的图标
        self.addSubInterface(self.project_interface, FluentIcon.HOME, "项目", FluentIcon.HOME_FILL)

        # IndexTTS2: AI 语音入口
        self.addSubInterface(self.ai_voice_interface, FluentIcon.MICROPHONE, "AI语音", FluentIcon.MICROPHONE)

        # self.addSubInterface(self.tts_interface, FluentIcon.FEEDBACK, "TTS", FluentIcon.FEEDBACK)

        # 添加设置界面到导航栏底部
        self.addSubInterface(self.setting_interface, FluentIcon.SETTING, "设置", FluentIcon.SETTING, NavigationItemPosition.BOTTOM)

        # 连接 stackedWidget (堆叠窗口部件) 的 currentChanged 信号到 _on_interface_changed 槽函数
        # 当页面切换时触发
        self.stackedWidget.currentChanged.connect(self._on_interface_changed)

        # 设置默认选中的导航项为项目界面
        self.navigationInterface.setCurrentItem(self.project_interface.objectName())
        # 设置当前显示的窗口部件为项目界面
        self.stackedWidget.setCurrentWidget(self.project_interface)

    def init_main_window(self):
        """初始化主窗口的外观和位置"""
        self.setWindowTitle('音频工具箱')  # 设置窗口标题
        self.resize(1000, 700)  # 设置初始大小
        self.setMinimumSize(1000, 700)  # 设置最小大小

        # 设置窗口图标
        icon = QIcon()
        icon.addFile("Resource/Icon New.png")
        self.setWindowIcon(icon)

        # 将窗口移动到屏幕中央
        desktop = QApplication.screens()[0].availableGeometry()  # 获取主屏幕的可用几何区域
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)  # 计算居中坐标

    # noinspection PyPep8Naming
    def closeEvent(self, event: QCloseEvent) -> None:
        """
        重写关闭事件处理函数。
        当窗口尝试关闭时调用，用于清理资源。
        """
        if self._changelog_window:
            self._changelog_window.close()  # 如果变更日志窗口打开，则关闭它
        self.setting_interface.close()  # 关闭设置界面 (可能包含保存配置逻辑)
        self.project_interface.close()  # 关闭项目界面

        # 反初始化 (清理) 各个 Job 资源
        self.voice_job.uninit()
        self.sample_job.uninit()
        self.wproj_job.uninit()
        
        # IndexTTS2: 清理 AI 语音 Job 资源
        self.indextts_job.uninit()

        event.accept()  # 接受关闭事件，允许窗口关闭

    def _on_interface_changed(self, index: int):
        """
        当导航界面切换时调用的回调函数。
        index: 当前界面的索引
        """
        # 如果切换到了设置界面，刷新项目设置显示
        if index == self.stackedWidget.indexOf(self.setting_interface):
            self.setting_interface.refresh_project_setting_frame()  # if index == self.stackedWidget.indexOf(self.tts_interface):  #     self.tts_interface.refresh()

        # IndexTTS2: 切换到 AI 语音界面时刷新状态
        if index == self.stackedWidget.indexOf(self.ai_voice_interface):
            self.ai_voice_interface.refresh()

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
        # 从配置中获取上次运行的 App 版本
        last_app_version = config_utility.get_config("LastAppVersion")
        display_log = ""

        if last_app_version is None:
            last_app_version = "0.0"

        # 如果上次版本小于当前版本 (main.APP_VERSION)
        if Version(last_app_version) < Version(main.APP_VERSION):
            # 遍历变更日志字典
            for version, log in changelog.CHANGELOG.items():
                # 筛选出介于上次版本和当前版本之间的日志
                if Version(main.APP_VERSION) >= Version(version) > Version(last_app_version):
                    # 拼接日志内容
                    display_log = f"{display_log}\n\n{version}\n{log}" if display_log != "" else f"{version}\n{log}"

        # 如果有需要显示的日志
        if display_log != "":
            self._changelog_window = ChangelogWindow(display_log)
            # 当日志窗口关闭时，显示主窗口 (这里可能是为了让日志窗口先展示，或者作为模态/引导)
            self._changelog_window.close_signal.connect(self.show)
        else:
            # 如果没有日志要显示，直接显示主窗口
            self.show()

        # 更新配置文件中的版本号为当前版本
        config_utility.set_config("LastAppVersion", main.APP_VERSION)
