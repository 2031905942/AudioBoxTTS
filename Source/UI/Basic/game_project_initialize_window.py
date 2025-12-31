import copy
import subprocess

from PySide6.QtCore import QStandardPaths, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLayout, QPushButton, QVBoxLayout, QWidget

from qfluentwidgets import BodyLabel, ComboBox, Dialog, FluentIcon, HorizontalSeparator, LineEdit, PasswordLineEdit, PushButton, PushSettingCard, TitleLabel
from Source.UI.Basic.error_info_bar import ErrorInfoBar
from Source.UI.Basic.result_info_bar import ResultInfoBar
from Source.Utility.svn_utility import SVNUtility
from typing_extensions import Optional


class GameProjectInitializeWindow(QWidget):

    confirm_signal = Signal(dict)
    window_closed_signal = Signal()

    def __init__(self, game_project_job):
        super().__init__()
        self.current_game_project_name = ""
        self.current_game_project_info_dict = {}
        self.game_project_root_path = ""

        self.setWindowTitle("游戏项目初始化窗口")
        # self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowMaximizeButtonHint)
        self.setStyleSheet("background-color: white")
        from Source.Utility.game_project_utility import GameProjectUtility
        self._game_project_utility: GameProjectUtility = game_project_job.game_project_utility
        self.game_project_info_dict = GameProjectUtility.game_project_info_dict

        self._layout: QVBoxLayout = QVBoxLayout(self)

        self._init_game_project_select_combo_box()

        self._separator1 = HorizontalSeparator(self)
        self._layout.addWidget(self._separator1)

        self._layout.addSpacing(10)

        self._init_svn_layout()

        self._separator2 = HorizontalSeparator(self)
        self._layout.addWidget(self._separator2)

        self._layout.addSpacing(10)

        self._init_final_check_layout()

        self._separator3 = HorizontalSeparator(self)
        self._layout.addWidget(self._separator3)

        self._layout.addSpacing(10)

        self._confirm_button = PushButton(self)
        self._confirm_button.setIcon(FluentIcon.SEND)
        self._confirm_button.setText("确认")
        self._confirm_button.clicked.connect(self.on_confirmed)
        self._layout.addWidget(self._confirm_button)

        self.show()

    def _init_game_project_select_combo_box(self):
        self._game_project_select_label_layout = QVBoxLayout()
        self._game_project_select_label_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._game_project_select_label = TitleLabel(self)
        self._game_project_select_label.setText("游戏项目")
        self._game_project_select_label_layout.addWidget(self._game_project_select_label)

        self._game_project_select_combo_box = ComboBox(self)
        self._game_project_select_combo_box.setPlaceholderText("请选择游戏项目")
        self._game_project_select_combo_box.addItems(self.game_project_info_dict.keys())
        self._game_project_select_combo_box.setCurrentIndex(-1)
        self._game_project_select_label_layout.addWidget(self._game_project_select_combo_box)

        self._game_project_select_combo_box.currentIndexChanged.connect(self._on_game_project_changed)

        self._game_project_info_label = BodyLabel(self)
        self._game_project_info_label.setText("")
        self._game_project_select_label_layout.addWidget(self._game_project_info_label)

        self._layout.addLayout(self._game_project_select_label_layout)

    def _init_svn_layout(self):
        self._svn_layout = QVBoxLayout()
        self._svn_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._svn_title_label = TitleLabel(self)
        self._svn_title_label.setText("SVN信息")
        self._svn_layout.addWidget(self._svn_title_label)
        self._svn_layout.addSpacing(10)

        self._svn_version_label = BodyLabel(self)
        svn_version = self._game_project_utility.get_svn_application_version()
        self._svn_version_label.setText(f"当前SVN版本: \"{svn_version}\"")
        self._svn_layout.addWidget(self._svn_version_label)
        self._svn_layout.addSpacing(10)

        self._svn_user_list_layout = QVBoxLayout()
        self._svn_user_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        '''
        self._svn_user_id_label = BodyLabel(self)
        self._svn_user_id_label.setText("用户名:")
        self._svn_user_id_label.setMaximumWidth(50)
        self._svn_user_layout.addWidget(self._svn_user_id_label)

        self._svn_user_id_line_edit = LineEdit(self)
        self._svn_user_id_line_edit.setPlaceholderText("选填")
        self._svn_user_id_line_edit.setClearButtonEnabled(True)
        self._svn_user_id_line_edit.setMinimumWidth(200)
        self._svn_user_id_line_edit.setMaximumWidth(300)
        self._svn_user_id_line_edit.textChanged.connect(lambda: self._svn_user_login_button.setIcon(FluentIcon.SEARCH))
        self._svn_user_layout.addWidget(self._svn_user_id_line_edit)

        self._svn_user_password_label = BodyLabel(self)
        self._svn_user_password_label.setText("密码:")
        self._svn_user_password_label.setMaximumWidth(50)
        self._svn_user_layout.addWidget(self._svn_user_password_label)

        self._svn_user_password_line_edit = PasswordLineEdit(self)
        self._svn_user_password_line_edit.setPlaceholderText("选填")
        self._svn_user_password_line_edit.setClearButtonEnabled(True)
        self._svn_user_password_line_edit.setMinimumWidth(200)
        self._svn_user_password_line_edit.setMaximumWidth(300)
        self._svn_user_password_line_edit.textChanged.connect(lambda: self._svn_user_login_button.setIcon(FluentIcon.SEARCH))
        self._svn_user_layout.addWidget(self._svn_user_password_line_edit)

        self._svn_user_login_button = PushButton(self)
        self._svn_user_login_button.setText("检查仓库访问权限")
        self._svn_user_login_button.setMaximumWidth(200)
        self._svn_user_login_button.setIcon(FluentIcon.SEARCH)
        self._svn_user_login_button.clicked.connect(self._on_svn_user_login_button_clicked)
        self._svn_user_layout.addWidget(self._svn_user_login_button)
        '''

        self._svn_layout.addLayout(self._svn_user_list_layout)
        self._svn_layout.addSpacing(10)

        self._game_project_root_path_label = BodyLabel(self)
        self._game_project_root_path_label.setText("请选择游戏项目根目录\n与项目相关的所有仓库将会检出至此目录下")
        self._svn_layout.addWidget(self._game_project_root_path_label)
        self._game_project_root_path_push_setting_card = PushSettingCard("选择游戏项目根目录", FluentIcon.FOLDER, "游戏项目根目录", "", self)
        self._game_project_root_path_push_setting_card.clicked.connect(self._on_game_project_root_path_push_setting_card_clicked)
        self._svn_layout.addWidget(self._game_project_root_path_push_setting_card)

        self._layout.addLayout(self._svn_layout)

    def _init_final_check_layout(self):
        self._final_check_layout = QVBoxLayout()
        self._final_check_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._final_check_title_label = TitleLabel(self)
        self._final_check_title_label.setText("最终确认")
        self._final_check_layout.addWidget(self._final_check_title_label)
        self._final_check_layout.addSpacing(10)

        self._final_check_info_label = BodyLabel(self)
        self._final_check_info_label.setText("")
        self._final_check_layout.addWidget(self._final_check_info_label)

        self._layout.addLayout(self._final_check_layout)

    def _on_game_project_changed(self):
        game_project_info_text: str = ""
        self._clear_layout(self._svn_user_list_layout)
        self.current_game_project_name = self._game_project_select_combo_box.currentText()
        self.current_game_project_info_dict = copy.deepcopy(self.game_project_info_dict[self.current_game_project_name])

        if "SVNTrunkPath" in self.current_game_project_info_dict.keys():
            game_project_info_text = f"* 将会检出游戏工程的\"Trunk\"分支的SVN仓库\n  \"{self.current_game_project_info_dict['SVNTrunkPath']['RemotePath']}\""
        if "SVNWwiseProjectPath" in self.current_game_project_info_dict.keys():
            game_project_info_text = f"{game_project_info_text}\n* 将会检出Wwise工程的SVN仓库\n  \"{self.current_game_project_info_dict['SVNWwiseProjectPath']['RemotePath']}\""
        if "SVNUnityPath" in self.current_game_project_info_dict.keys():
            game_project_info_text = f"{game_project_info_text}\n* 将会检出Unity编辑器的SVN仓库\n  \"{self.current_game_project_info_dict['SVNUnityPath']['RemotePath']}\""
        # if main.is_windows_os() and "WwiseVersion" in current_game_project_info_dict.keys():
        #     game_project_info_text = f"{game_project_info_text}\n* 将会从音频组SVN仓库中检出Wwise设计工具(版本: \"{current_game_project_info_dict['WwiseVersion']}\")"

        for repository_info_name, repository_info in self.current_game_project_info_dict.items():
            if "SVN" not in repository_info_name or "Path" not in repository_info_name:
                continue
            svn_authorization_layout = QVBoxLayout()
            svn_authorization_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            svn_repository_label = BodyLabel()
            svn_repository_label.setText(f"仓库: \"{repository_info['RemotePath']}\"")
            svn_authorization_layout.addWidget(svn_repository_label)

            svn_user_layout = QHBoxLayout()
            svn_user_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            svn_user_id_label = BodyLabel()
            svn_user_id_label.setText("用户名:")
            svn_user_id_label.setMaximumWidth(50)
            svn_user_layout.addWidget(svn_user_id_label)

            svn_user_id_line_edit = LineEdit()
            svn_user_id_line_edit.setPlaceholderText("选填")
            svn_user_id_line_edit.setClearButtonEnabled(True)
            svn_user_id_line_edit.setMinimumWidth(200)
            svn_user_id_line_edit.setMaximumWidth(300)

            svn_user_layout.addWidget(svn_user_id_line_edit)

            svn_user_password_label = BodyLabel()
            svn_user_password_label.setText("密码:")
            svn_user_password_label.setMaximumWidth(50)
            svn_user_layout.addWidget(svn_user_password_label)

            svn_user_password_line_edit = PasswordLineEdit()
            svn_user_password_line_edit.setPlaceholderText("选填")
            svn_user_password_line_edit.setClearButtonEnabled(True)
            svn_user_password_line_edit.setMinimumWidth(200)
            svn_user_password_line_edit.setMaximumWidth(300)

            svn_user_layout.addWidget(svn_user_password_line_edit)

            svn_user_login_button = PushButton()
            svn_user_login_button.setText("检查仓库访问权限")
            svn_user_login_button.setMaximumWidth(200)
            svn_user_login_button.setIcon(FluentIcon.SEARCH)
            repository_info_dict = copy.deepcopy(repository_info)
            svn_user_login_button.clicked.connect(
                    self._create_on_svn_user_login_button_clicked_callback(repository_info_dict, svn_user_id_line_edit, svn_user_password_line_edit, svn_user_login_button))
            svn_user_layout.addWidget(svn_user_login_button)

            svn_user_id_line_edit.textChanged.connect(self._create_on_svn_user_id_line_edit_text_changed_callback(repository_info_name, svn_user_id_line_edit, svn_user_login_button))
            svn_user_password_line_edit.textChanged.connect(self._create_on_svn_user_password_line_edit_text_changed_callback(repository_info_name, svn_user_password_line_edit, svn_user_login_button))

            svn_authorization_layout.addLayout(svn_user_layout)

            self._svn_user_list_layout.addLayout(svn_authorization_layout)
            self._svn_user_list_layout.addSpacing(10)

        self._game_project_info_label.setText(game_project_info_text)
        self._update_final_check_info()

    def _update_final_check_info(self):
        final_check_info_text: str = ""
        has_game_project_root_path: bool = self.game_project_root_path != ""

        if has_game_project_root_path and "SVNTrunkPath" in self.current_game_project_info_dict.keys():
            local_svn_trunk_path = f"{self.game_project_root_path}/{self.current_game_project_info_dict['SVNTrunkPath']['LocalRelativePath']}"
            final_check_info_text = f"* 游戏工程的\"Trunk\"分支的SVN仓库将会检出至: \"{local_svn_trunk_path}\""
        if has_game_project_root_path and "SVNWwiseProjectPath" in self.current_game_project_info_dict.keys():
            local_svn_wwise_project_path = f"{self.game_project_root_path}/{self.current_game_project_info_dict['SVNWwiseProjectPath']['LocalRelativePath']}"
            final_check_info_text = f"{final_check_info_text}\n* Wwise工程的SVN仓库将会检出至: \"{local_svn_wwise_project_path}\""
        if has_game_project_root_path and "SVNUnityPath" in self.current_game_project_info_dict.keys():
            local_unity_path = f"{self.game_project_root_path}/{self.current_game_project_info_dict['SVNUnityPath']['LocalRelativePath']}"
            final_check_info_text = f"{final_check_info_text}\n* Unity编辑器的SVN仓库将会检出至: \"{local_unity_path}\""

        self._final_check_info_label.setText(final_check_info_text)

    def _create_on_svn_user_login_button_clicked_callback(self, repository_info_dict: dict, user_id_line_edit: LineEdit, password_line_edit: LineEdit, button: QPushButton):
        return lambda: self._check_svn_repository_authorization(repository_info_dict, user_id_line_edit.text(), password_line_edit.text(), button)

    def _check_svn_repository_authorization(self, repository_info_dict: dict, user: Optional[str] = None, password: Optional[str] = None, button: PushButton = None) -> bool:
        result = True
        username = ""
        if user is not None and password is not None:
            username = user.strip()
            password = password.strip()
            if username != "" and password == "" or username == "" and password != "":
                dialog: Dialog = Dialog("提醒", "请提供正确的用户名和密码重试", self)
                dialog.cancelButton.setHidden(True)
                dialog.exec()
                return False
        remote_path: str = repository_info_dict["RemotePath"]
        user_from_info: Optional[str] = repository_info_dict.get("User")
        password_from_info: Optional[str] = repository_info_dict.get("Password")
        if user_from_info and password_from_info:
            if not self.get_repository_accessibility(remote_path, user_from_info, password_from_info):
                result = False
        else:
            if not self.get_repository_accessibility(remote_path, username, password):
                result = False
        if button:
            if not result:
                self.show_result_info_bar("error", "结果", "检查未通过")
                button.setIcon(FluentIcon.CLOSE)
            else:
                self.show_result_info_bar("success", "结果", "检查通过")
                button.setIcon(FluentIcon.ACCEPT)
        return result

    def _create_on_svn_user_id_line_edit_text_changed_callback(self, repository_info_name: str, line_edit: LineEdit, login_button: PushButton):
        return lambda: self._on_svn_user_id_line_edit_text_changed(repository_info_name, line_edit, login_button)

    def _on_svn_user_id_line_edit_text_changed(self, repository_info_name: str, line_edit: LineEdit, login_button: PushButton):
        self.current_game_project_info_dict[repository_info_name]["User"] = line_edit.text().strip()
        login_button.setIcon(FluentIcon.SEARCH)

    def _create_on_svn_user_password_line_edit_text_changed_callback(self, repository_info_name: str, line_edit: LineEdit, login_button: PushButton):
        return lambda: self._on_svn_user_password_line_edit_text_changed(repository_info_name, line_edit, login_button)

    def _on_svn_user_password_line_edit_text_changed(self, repository_info_name: str, line_edit: LineEdit, login_button: PushButton):
        self.current_game_project_info_dict[repository_info_name]["Password"] = line_edit.text().strip()
        login_button.setIcon(FluentIcon.SEARCH)

    def _on_game_project_root_path_push_setting_card_clicked(self):
        game_project_root_directory_file_dialog: QFileDialog = QFileDialog(self)
        game_project_root_directory_file_dialog.setWindowTitle("请选择游戏项目根目录")

        set_directory: str = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DownloadLocation)[0]
        game_project_root_directory_file_dialog.setDirectory(set_directory)
        game_project_root_directory_file_dialog.setFileMode(QFileDialog.FileMode.Directory)
        game_project_root_directory_file_dialog.setViewMode(QFileDialog.ViewMode.List)

        if game_project_root_directory_file_dialog.exec():
            self.game_project_root_path = game_project_root_directory_file_dialog.selectedFiles()[0]
        else:
            self.game_project_root_path = ""
        self._game_project_root_path_push_setting_card.setContent(self.game_project_root_path)
        self._update_final_check_info()

    def on_confirmed(self):
        if self.current_game_project_name not in self.game_project_info_dict.keys():
            dialog = Dialog("提醒", "未选择游戏项目\n请选择游戏项目后重试", self)
            dialog.cancelButton.setHidden(True)
            return dialog.exec()

        if self.game_project_root_path == "":
            dialog = Dialog("错误", "未指定游戏项目根目录\n请选择游戏项目根目录后重试", self)
            dialog.cancelButton.setHidden(True)
            return dialog.exec()

        all_repository_authorization_pass = True
        for repository_info_name, repository_info_dict in self.current_game_project_info_dict.items():
            if "SVN" in repository_info_name and "Path" in repository_info_name:
                user: Optional[str] = repository_info_dict.get("User", "")
                password: Optional[str] = repository_info_dict.get("Password", "")
                authorization_result = self._check_svn_repository_authorization(repository_info_dict, user, password)
                if not authorization_result:
                    all_repository_authorization_pass = False

        if not all_repository_authorization_pass:
            dialog = Dialog("错误", "无法访问SVN仓库\n请检查用户名和密码是否正确", self)
            dialog.cancelButton.setHidden(True)
            return dialog.exec()

        dialog = Dialog("确认执行游戏项目初始化", f"游戏项目: \"{self.current_game_project_name}\"", self)
        result = dialog.exec()
        if result:
            self.current_game_project_info_dict["game_project_name"] = self.current_game_project_name
            self.current_game_project_info_dict["game_project_root_path"] = self.game_project_root_path
            self.confirm_signal.emit(self.current_game_project_info_dict)
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.window_closed_signal.emit()
        event.accept()

    def get_repository_accessibility(self, repository_path: str, username: str = "", password: str = "") -> bool:
        if not self._game_project_utility.check_svn_validity():
            return False
        args = [SVNUtility.SVN_APPLICATION_PATH, "log", repository_path, "--non-interactive", "-l", "1", "-q"]
        if username != "" and password != "":
            args += ["--username", username, "--password", password]
        try:
            output = subprocess.check_output(args, stderr=subprocess.STDOUT, timeout=3)
        except Exception as error:
            ErrorInfoBar(f'访问仓库失败"{repository_path}":\n{error}', self)
            self.raise_()
            return False

        if not output:
            return False
        return True

    def show_result_info_bar(self, info_bar_type: str, title: str, content: str):
        ResultInfoBar(info_bar_type, title, content, self)
        self.raise_()

    def _clear_layout(self, layout: QLayout):
        while layout.count():
            item = layout.takeAt(0)  # 获取并移除第一个项

            # 处理widget项
            if item.widget():
                item.widget().deleteLater()  # 安全删除组件

            # 处理子布局
            elif item.layout():
                # 递归删除子布局中的组件
                while item.layout().count():
                    sub_item = item.layout().takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()
                    elif sub_item.layout():
                        self._clear_layout(sub_item.layout())

            # # 处理间距项
            # elif item.spacerItem():
            #     pass  # 可选：移除间距项
