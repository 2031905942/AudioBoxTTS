import os.path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout

import main
import psutil
from main import APP_VERSION
from qfluentwidgets import Action, FluentIcon, MSFluentTitleBar, PrimaryPushButton, RoundMenu, TransparentDropDownPushButton
from Source.Job.work_environment_job import WorkEnvironmentJob
from Source.Utility.config_utility import config_utility


class TitleBar(MSFluentTitleBar):
    def __init__(self, parent):
        super().__init__(parent)

        from Source.main_window import MainWindow
        # noinspection PyTypeChecker
        self._main_window: MainWindow = parent
        from Source.Job.version_job import VersionJob
        self.version_job: VersionJob = VersionJob(self._main_window, self)
        self.version_job.check_app_latest_version_action()
        self.toolButtonLayout: QHBoxLayout = QHBoxLayout()
        # self._add_help_menu()
        self._add_voice_job_menu()
        self._add_sample_job_menu()
        self._add_wwise_project_job_menu()
        self._add_work_environment_job_menu()
        self._add_game_project_job_menu()
        # self._add_tts_job_menu()
        self.hBoxLayout.insertLayout(4, self.toolButtonLayout)

        self.hBoxLayout.setStretch(5, 0)

        self._update_button: PrimaryPushButton | None = None

        self.hBoxLayout.insertSpacing(7, 20)

        self.refresh()

    def display_version_update_notice(self, latest_version: str | None):
        if not latest_version:
            return

        self.version_job.latest_version = latest_version

        if latest_version > APP_VERSION:
            self._update_button = PrimaryPushButton(f"检测到最新版本\"{latest_version}\", 请尽快升级", self, FluentIcon.UPDATE)
            # self._update_button.clicked.connect(self.version_job.update_app_action)
            self.hBoxLayout.insertWidget(5, self._update_button)

    def _add_help_menu(self):
        help_menu_button: TransparentDropDownPushButton = TransparentDropDownPushButton("帮助", self, FluentIcon.HELP)

        about_action = Action(FluentIcon.QUESTION, "关于")
        about_action.triggered.connect(self._about)

        version_action = Action(FluentIcon.SEARCH, f"版本: {APP_VERSION}")

        version_action.setDisabled(True)
        help_menu: RoundMenu = RoundMenu(parent=self)

        help_menu.addAction(about_action)
        help_menu.addSeparator()
        help_menu.addAction(version_action)

        help_menu_button.setMenu(help_menu)
        self.toolButtonLayout.addWidget(help_menu_button)

    def _add_voice_job_menu(self):
        voice_job_menu_button: TransparentDropDownPushButton = TransparentDropDownPushButton("语音", self, FluentIcon.CHAT)

        sync_export_excel_and_voice_excel_action = Action(FluentIcon.SYNC, "文案平台工作簿同步录音工作簿")
        sync_export_excel_and_voice_excel_action.setToolTip(
                "将文案平台导出的工作簿的台本数据同步到录音工作簿.\n注意:\n1. 只能同步相同语言的工作簿.\n2. 读取文案平台工作簿后, 若有台本存在问题(文案缺失等), 则会弹出工作簿问题窗口供检查.\n3. 写入录音工作簿前会在相同目录下创建录音工作簿的备份.\n4. 同步完成后将会创建台本数据差异工作簿, 方便比较同步前后的台本差异.")
        sync_export_excel_and_voice_excel_action.triggered.connect(self._main_window.voice_job.sync_export_excel_and_voice_excel_action)

        sync_localized_voice_excel_action = Action(FluentIcon.SYNC, "多语言录音工作簿同步")
        sync_localized_voice_excel_action.triggered.connect(self._main_window.voice_job.sync_localized_voice_excel_action)

        generate_voice_id_for_voice_excel_action = Action(FluentIcon.ADD_TO, "为录音工作簿生成语音ID")
        generate_voice_id_for_voice_excel_action.triggered.connect(self._main_window.voice_job.generate_voice_id_for_voice_excel_action)

        generate_voice_event_for_voice_excel_action = Action(FluentIcon.ADD_TO, "为录音工作簿生成语音事件")
        generate_voice_event_for_voice_excel_action.triggered.connect(self._main_window.voice_job.generate_voice_event_for_voice_excel_action)

        format_voice_excel_action = Action(FluentIcon.BRUSH, "格式化录音工作簿")
        format_voice_excel_action.triggered.connect(self._main_window.voice_job.format_voice_excel_action)

        rename_voice_sample_by_voice_excel_action = Action(FluentIcon.PASTE, "用录音工作簿重命名语音素材")
        rename_voice_sample_by_voice_excel_action.triggered.connect(self._main_window.voice_job.rename_voice_sample_by_voice_excel_action)

        voice_job_menu = RoundMenu(parent=self)

        voice_job_menu.addAction(sync_export_excel_and_voice_excel_action)
        voice_job_menu.addAction(sync_localized_voice_excel_action)
        voice_job_menu.addSeparator()
        voice_job_menu.addAction(generate_voice_id_for_voice_excel_action)
        voice_job_menu.addAction(generate_voice_event_for_voice_excel_action)
        voice_job_menu.addSeparator()
        voice_job_menu.addAction(format_voice_excel_action)
        voice_job_menu.addSeparator()
        voice_job_menu.addAction(rename_voice_sample_by_voice_excel_action)

        voice_job_menu_button.setMenu(voice_job_menu)
        self.toolButtonLayout.addWidget(voice_job_menu_button)

    def _add_sample_job_menu(self):
        sample_job_menu_button: TransparentDropDownPushButton = TransparentDropDownPushButton("素材", self, FluentIcon.MUSIC)
        self.toolButtonLayout.addWidget(sample_job_menu_button)

        sample_job_menu = RoundMenu(parent=self)
        sample_job_menu_button.setMenu(sample_job_menu)

        normalize_sample_action = Action(FluentIcon.MIX_VOLUMES, "素材标准化")
        normalize_sample_action.triggered.connect(self._main_window.sample_job.normalize_sample_action)
        sample_job_menu.addAction(normalize_sample_action)

        update_wwise_project_sample_action = Action(FluentIcon.SAVE_COPY, "更新Wwise工程素材")
        update_wwise_project_sample_action.triggered.connect(self._main_window.sample_job.update_wwise_project_sample_action)
        sample_job_menu.addAction(update_wwise_project_sample_action)

        # if main.is_windows_os():
        #     sample_job_menu.addSeparator()
        #
        #     export_voice_sample_viseme_action = Action(FluentIcon.MEGAPHONE, "使用OVRLipSync导出语音素材视素")
        #     export_voice_sample_viseme_action.triggered.connect(self._main_window.ovr_lip_sync_job.export_voice_sample_viseme_action)
        #     sample_job_menu.addAction(export_voice_sample_viseme_action)

    def _add_wwise_project_job_menu(self):
        self.wwise_project_job_menu_button: TransparentDropDownPushButton = TransparentDropDownPushButton("Wwise工程", self, FluentIcon.TILES)
        self.toolButtonLayout.addWidget(self.wwise_project_job_menu_button)
        wwise_project_job_menu = RoundMenu(parent=self)
        self.wwise_project_job_menu_button.setMenu(wwise_project_job_menu)

        sample_import_action = Action(FluentIcon.FOLDER_ADD, "素材入库")
        sample_import_action.triggered.connect(self._main_window.wproj_job.sample_import_action)
        wwise_project_job_menu.addAction(sample_import_action)

        split_work_unit_action = Action(FluentIcon.DICTIONARY_ADD, "拆分工作单元")
        split_work_unit_action.triggered.connect(self._main_window.wproj_job.split_work_unit_action)
        wwise_project_job_menu.addAction(split_work_unit_action)

        find_sound_object_contain_inactive_source_action = Action(FluentIcon.SEARCH, "查找含有未激活素材的声音对象")
        find_sound_object_contain_inactive_source_action.triggered.connect(self._main_window.wproj_job.find_sound_object_contain_inactive_source_action)
        wwise_project_job_menu.addAction(find_sound_object_contain_inactive_source_action)

        find_missing_language_voice_object_action = Action(FluentIcon.SEARCH, "查找缺失了语言素材的语音对象")
        find_missing_language_voice_object_action.triggered.connect(self._main_window.wproj_job.find_missing_language_voice_object_action)
        wwise_project_job_menu.addAction(find_missing_language_voice_object_action)

        find_wrong_referenced_voice_event_action = Action(FluentIcon.SEARCH, "查找错误引用语音对象的语音事件对象")
        find_wrong_referenced_voice_event_action.triggered.connect(self._main_window.wproj_job.find_wrong_referenced_voice_event_action)
        wwise_project_job_menu.addAction(find_wrong_referenced_voice_event_action)

        select_sound_object_within_txt_action = Action(FluentIcon.SEARCH, "查找并选中文本文件中包含的事件的声音对象")
        select_sound_object_within_txt_action.triggered.connect(self._main_window.wproj_job.select_sound_object_within_text_action)
        wwise_project_job_menu.addAction(select_sound_object_within_txt_action)

        test_action = Action(FluentIcon.SEARCH, "测试")
        test_action.triggered.connect(self._main_window.wproj_job.test_action)
        wwise_project_job_menu.addAction(test_action)

    def _add_work_environment_job_menu(self):
        self.work_environment_job_menu_button: TransparentDropDownPushButton = TransparentDropDownPushButton("工作环境", self, FluentIcon.CONNECT)
        self.toolButtonLayout.addWidget(self.work_environment_job_menu_button)
        work_environment_job_menu = RoundMenu(parent=self)
        self.work_environment_job_menu_button.setMenu(work_environment_job_menu)

        if main.is_windows_os():
            prepare_work_environment_action = Action(FluentIcon.APPLICATION, "准备工作环境")
            prepare_work_environment_action.triggered.connect(self._main_window.work_environment_job.prepare_work_environment_action)
            work_environment_job_menu.addAction(prepare_work_environment_action)

            unity_hub_icon_path = f"{main.ROOT_PATH}/Resource/Icon/UnityHub.png"

            open_official_unity_hub_action = Action(QIcon(unity_hub_icon_path), "打开官方版Unity Hub")
            open_official_unity_hub_action.triggered.connect(lambda: _open_unity_hub(True))
            work_environment_job_menu.addAction(open_official_unity_hub_action)

            open_moonton_unity_hub_action = Action(QIcon(unity_hub_icon_path), "打开沐瞳版Unity Hub")
            open_moonton_unity_hub_action.triggered.connect(lambda: _open_unity_hub(False))
            work_environment_job_menu.addAction(open_moonton_unity_hub_action)

            def _open_unity_hub(is_official: bool):
                for process in psutil.process_iter(['pid', 'name']):
                    try:
                        if process.info['name'] == "Unity Hub.exe":
                            psutil.Process(process.info['pid']).terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                if is_official:
                    os.system(r'Powershell -Command "& { Start-Process \"C:\Program Files\Unity Hub\Unity Hub.exe\" } "')
                else:
                    os.system(r'Powershell -Command "& { Start-Process \"' + WorkEnvironmentJob.MOONTON_UNITY_HUB_APPLICATION_PATH + r'\" -Verb RunAs } "')

            unity_icon_path = f"{main.ROOT_PATH}/Resource/Icon/Unity.png"
            install_unity_action = Action(QIcon(unity_icon_path), "安装Unity引擎")
            install_unity_action.triggered.connect(self._main_window.work_environment_job.install_unity_action)
            work_environment_job_menu.addAction(install_unity_action)

            wwise_icon_path = f"{main.ROOT_PATH}/Resource/Icon/Wwise.png"
            install_wwise_authoring_action = Action(QIcon(wwise_icon_path), "安装Wwise设计工具")
            install_wwise_authoring_action.triggered.connect(self._main_window.work_environment_job.install_wwise_authoring_action)
            work_environment_job_menu.addAction(install_wwise_authoring_action)

    def _add_game_project_job_menu(self):
        self.game_project_job_menu_button: TransparentDropDownPushButton = TransparentDropDownPushButton("游戏项目", self, FluentIcon.TILES)
        self.toolButtonLayout.addWidget(self.game_project_job_menu_button)
        game_project_job_menu = RoundMenu(parent=self)
        self.game_project_job_menu_button.setMenu(game_project_job_menu)

        initialize_game_project_action = Action(FluentIcon.CLOUD_DOWNLOAD, "初始化游戏项目")
        initialize_game_project_action.triggered.connect(self._main_window.game_project_job.initialize_game_project_action)
        game_project_job_menu.addAction(initialize_game_project_action)

    # def _add_tts_job_menu(self):
    #     self.tts_job_menu_button: TransparentDropDownPushButton = TransparentDropDownPushButton("语音合成", self, FluentIcon.FEEDBACK)
    #     self.toolButtonLayout.addWidget(self.tts_job_menu_button)
    #     tts_job_menu = RoundMenu(parent=self)
    #     self.tts_job_menu_button.setMenu(tts_job_menu)
    #
    #     generate_lyric_audio_action = Action(FluentIcon.FEEDBACK, "歌词语音合成")
    #     generate_lyric_audio_action.triggered.connect(self._main_window.tts_job.generate_lyric_audio_action)
    #     tts_job_menu.addAction(generate_lyric_audio_action)

    def refresh(self):
        if self._main_window.is_current_wwise_project_valid():
            self.wwise_project_job_menu_button.setDisabled(False)
        else:
            self.wwise_project_job_menu_button.setDisabled(True)

        if main.is_windows_os():
            from windows_tools import installed_software
            installed_software_list = installed_software.get_installed_software()
            if any("Unity Hub" in installed_software['name'] for installed_software in installed_software_list):
                self.work_environment_job_menu_button.menu().actions()[1].setVisible(True)
            else:
                self.work_environment_job_menu_button.menu().actions()[1].setVisible(False)

            if os.path.isfile(WorkEnvironmentJob.MOONTON_UNITY_HUB_APPLICATION_PATH) and config_utility.get_config("UnityHubInstalled") is True:
                self.work_environment_job_menu_button.menu().actions()[2].setVisible(True)
            else:
                config_utility.set_config("UnityHubInstalled", False)
                self.work_environment_job_menu_button.menu().actions()[2].setVisible(False)

    @staticmethod
    def _about():
        QApplication.aboutQt()
