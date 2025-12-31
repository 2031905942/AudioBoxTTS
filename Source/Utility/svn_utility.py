import subprocess
import urllib.parse
from os import path
from typing import Optional

from PySide6.QtCore import Signal

import chardet
import main
from Source.Utility.base_utility import BaseUtility


class SVNUtility(BaseUtility):
    SVN_APPLICATION_PATH = f"{main.ROOT_PATH}/Subversion/Windows/svn.exe" if main.is_windows_os() else "svn"
    SVN_FILE_ACTION_CHARACTER_LIST = ["A", "D", "U", "C", "G", "E", "R"]

    JAZMAYBE_SVN_USER = "MoontonAudio"
    JAZMAYBE_SVN_PASSWORD = "MoontonAudio123"

    LIGHT_HOUSE_SVN_USER = "maybetan"
    LIGHT_HOUSE_SVN_PASSWORD = "maybetan123"

    update_wwise_authoring_succeed_signal = Signal(dict)
    check_workcopy_update_complete_signal = Signal(dict)

    def update_wwise_authoring_job(self, wwise_authoring_info_dict: dict):
        wwise_authoring_root_dir_path = wwise_authoring_info_dict["dir_path"]
        self.update_progress_text_signal.emit(f"更新Wwise设计工具...\n目录\"{wwise_authoring_root_dir_path}\"")
        self.cleanup_repository(wwise_authoring_root_dir_path, SVNUtility.JAZMAYBE_SVN_USER, SVNUtility.JAZMAYBE_SVN_PASSWORD, True)
        for stdout in self.update_repository(wwise_authoring_root_dir_path, SVNUtility.JAZMAYBE_SVN_USER, SVNUtility.JAZMAYBE_SVN_PASSWORD):
            if stdout == "":
                self.finish_signal.emit("任务中止", "", "error")
                return

        self.update_wwise_authoring_succeed_signal.emit(wwise_authoring_info_dict)
        self.finish_signal.emit("结果", "更新Wwise设计工具完成.", "success")

    def check_workcopy_has_update_job(self, info_dict: dict):
        dir_path = info_dict["dir_path"]
        info_dict["has_update"] = False
        try:
            self.update_progress_text_signal.emit(f"检查工作副本更新...\n目录\"{dir_path}\"")
            output = subprocess.check_output([SVNUtility.SVN_APPLICATION_PATH, "status", "-u", dir_path], stderr=subprocess.STDOUT, timeout=7)
        except Exception as error:
            if type(error) is subprocess.TimeoutExpired:
                self.check_workcopy_update_complete_signal.emit(info_dict)
                self.finish_signal.emit("结果", f'检查SVN工作副本"{dir_path}"是否有更新超时', "warning")
            else:
                self.error_signal.emit(f'检查SVN工作副本是否有更新失败"{dir_path}":\n{error}')
                self.check_workcopy_update_complete_signal.emit(info_dict)
                self.finish_signal.emit("任务中止", "", "error")
            return
        stdout = SVNUtility.handle_stdout(output)
        if "*" in stdout:
            info_dict["has_update"] = True
        self.check_workcopy_update_complete_signal.emit(info_dict)
        self.finish_signal.emit("结果", "检查工作副本更新完成.", "success")

    def check_svn_validity(self) -> bool:
        if main.is_windows_os():
            return path.isfile(SVNUtility.SVN_APPLICATION_PATH)
        else:
            try:
                subprocess.run(SVNUtility.SVN_APPLICATION_PATH, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return True
            except FileNotFoundError:
                self.error_signal.emit("未安装SVN, 请先安装Subversion(可通过Brew安装)")
                return False

    def check_dir_is_workcopy(self, dir_path) -> bool:
        if not self.check_svn_validity():
            return False

        try:
            output = subprocess.check_output([SVNUtility.SVN_APPLICATION_PATH, "status", "--depth=empty", dir_path], stderr=subprocess.STDOUT, timeout=5)
        except Exception as error:
            if type(error) is subprocess.TimeoutExpired:
                self.show_result_info_bar_signal.emit("warning", "", f'检查目录"{dir_path}"是否是SVN工作副本超时')
            else:
                self.error_signal.emit(f'检查目录是否是SVN工作副本失败"{dir_path}":\n{error}')
            return False
        stdout = SVNUtility.handle_stdout(output)
        if "is not a working copy" in stdout:
            return False
        return True

    def get_repository_url(self, dir_path) -> Optional[str]:
        if not self.check_svn_validity():
            return None

        if not self.check_dir_is_workcopy(dir_path):
            return None

        try:
            output = subprocess.check_output([SVNUtility.SVN_APPLICATION_PATH, "info", "--show-item", "url", dir_path], stderr=subprocess.STDOUT, timeout=3)
        except Exception as error:
            if type(error) is subprocess.TimeoutExpired:
                self.show_result_info_bar_signal.emit("warning", "", f'获取仓库地址"{dir_path}"超时')
                return "Timeout"
            else:
                self.error_signal.emit(f'获取仓库地址失败"{dir_path}":\n{error}')
            return None
        stdout = SVNUtility.handle_stdout(output)
        if "is not a working copy" in stdout:
            return None
        return stdout

    def get_revision(self, path, remote=False) -> Optional[int]:
        if not self.check_svn_validity():
            return None
        try:
            cmd = [SVNUtility.SVN_APPLICATION_PATH, 'info']
            if remote:
                cmd += ['-r', 'HEAD']
            cmd.append(path)
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            for line in result.stdout.splitlines():
                if line.startswith('Revision:'):
                    return int(line.split(':')[1].strip())
            return None
        except subprocess.CalledProcessError as e:
            self.error_signal.emit(f'获取SVN工作副本版本失败"{path}":\n{e}')
            return None

    def get_svn_application_version(self) -> str:
        if not self.check_svn_validity():
            return ""
        process = subprocess.run([SVNUtility.SVN_APPLICATION_PATH, "--version", "--quiet"], capture_output=True)
        version: str = SVNUtility.handle_stdout(process.stdout)
        return version

    def get_repository_accessibility(self, repository_path: str, username: str = "", password: str = "") -> bool:
        if not self.check_svn_validity():
            return False
        args = [SVNUtility.SVN_APPLICATION_PATH, "log", repository_path, "--non-interactive", "-l", "1", "-q"]
        if username != "" and password != "":
            args += ["--username", username, "--password", password]

        try:
            output = subprocess.check_output(args, stderr=subprocess.STDOUT, timeout=3)
        except Exception as error:
            if type(error) is subprocess.TimeoutExpired:
                self.show_result_info_bar_signal.emit("warning", "", f'访问仓库"{repository_path}"超时')
            else:
                self.error_signal.emit(f'访问仓库失败"{repository_path}":\n{error}')
            return False

        if not output:
            return False
        return True

    def list_file(self, repository_path: str, username: str = "", password: str = "", recursively: bool = True) -> Optional[list[str]]:
        if not self.check_svn_validity():
            return None
        args = [SVNUtility.SVN_APPLICATION_PATH, "list", repository_path, "--include-externals"]
        if username != "" and password != "":
            args += ["--username", username, "--password", password]

        if recursively:
            args += ["-R"]

        try:
            output = subprocess.check_output(args, stderr=subprocess.STDOUT, timeout=5)

        except Exception as error:
            if type(error) is subprocess.TimeoutExpired:
                self.show_result_info_bar_signal.emit("warning", "", f'列出仓库"{repository_path}"文件超时')
            else:
                self.error_signal.emit(f'列出仓库"{repository_path}"文件失败:\n{error}')
            return None

        return self.handle_stdout(output).splitlines()

    def get_repository_file_count(self, repository_path: str, username: str = "", password: str = "", timeout: float = 5) -> int:
        if not self.check_svn_validity():
            return -1
        args = [SVNUtility.SVN_APPLICATION_PATH, "list", repository_path, "-R", "--include-externals"]
        if username != "" and password != "":
            args += ["--username", username, "--password", password]

        try:
            output = subprocess.check_output(args, stderr=subprocess.STDOUT, timeout=timeout)
        except Exception as error:
            if type(error) is subprocess.TimeoutExpired:
                self.show_result_info_bar_signal.emit("warning", "", f'获取仓库"{repository_path}"文件数量超时')
                return -2
            else:
                self.error_signal.emit(f'获取仓库"{repository_path}"文件数量失败:\n{error}')
            return -1

        # process = subprocess.run(args, capture_output=True)
        #
        # if process.returncode != 0:
        #     self.error_signal.emit(f'访问仓库失败"{repository_path}":\n{SVNUtility.handle_stdout(process.stderr)}')
        #     return -1

        file_count = len(output.splitlines())
        return file_count

    def checkout_repository(self, repository_path: str, local_path: str, username: str = "", password: str = "", depth: str = "infinity") -> Optional[str]:
        if not self.check_svn_validity():
            yield None
        args = [SVNUtility.SVN_APPLICATION_PATH, "co", repository_path, local_path]
        if username != "" and password != "":
            args += ["--username", username, "--password", password]

        args += ["--depth", depth]

        popen = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        for stdout_line in iter(popen.stdout.readline, ""):
            yield stdout_line
        popen.stdout.close()
        return_code = popen.wait()
        if return_code:
            self.error_signal.emit(f'检出仓库失败"{repository_path}":\n{popen.stderr.readline().strip()}')
            yield None

    def update_repository(self, local_path: str, username: str = "", password: str = "", depth: str = "infinity") -> Optional[str]:
        if not self.check_svn_validity():
            yield None

        args = [SVNUtility.SVN_APPLICATION_PATH, "up", local_path]

        if username != "" and password != "":
            args += ["--username", username, "--password", password]

        args += ["--depth", depth]

        popen = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        for stdout_line in iter(popen.stdout.readline, ""):
            yield stdout_line
        popen.stdout.close()
        return_code = popen.wait()
        if return_code:
            self.error_signal.emit(f'更新仓库失败"{local_path}":\n{popen.stderr.readline().strip()}')
            yield None

    def cleanup_repository(self, local_path: str, username: str = "", password: str = "", ignore_error: bool = False) -> bool:
        args = [SVNUtility.SVN_APPLICATION_PATH, "cleanup", local_path]
        if username != "" and password != "":
            args += ["--username", username, "--password", password]

        process = subprocess.run(args, capture_output=True)
        if process.returncode != 0:
            if not ignore_error:
                self.error_signal.emit(f'仓库整理失败"{local_path}":\n{SVNUtility.handle_stdout(process.stderr)}')
            return False

        return True

    @staticmethod
    def handle_stdout(stdout: bytes) -> Optional[str]:
        if not stdout:
            return ""
        result = chardet.detect(stdout)
        stdout = stdout.decode(result['encoding']).strip()

        stdout = urllib.parse.unquote(stdout)
        return stdout
