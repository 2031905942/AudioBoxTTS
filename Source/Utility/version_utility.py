import traceback

from PySide6.QtCore import Signal

import pymysql
from Source.Utility.base_utility import BaseUtility


class VersionUtility(BaseUtility):
    latest_version_get_signal: Signal = Signal(str)

    # update_finish_signal: Signal = Signal()

    def __init__(self, version_job):
        from Source.Job.version_job import VersionJob
        version_job: VersionJob
        super().__init__(version_job)
        #     import pysvn
        #     self._svn_client = pysvn.Client()
        #     self._svn_client.callback_notify = self._app_update_completed
        #     self._svn_client.callback_get_login = self._svn_client_get_login

    def check_app_latest_version(self):
        # Connect to the database
        try:
            # noinspection PyUnresolvedReferences
            connection = pymysql.connect(host="jazmaybe.com", port=3307, user="PrismAudioBox", database="AudioBox", cursorclass=pymysql.cursors.DictCursor)
            with connection:
                with connection.cursor() as cursor:
                    sql = "SELECT `Version` FROM `AppVersion`"
                    cursor.execute(sql)
                    result = cursor.fetchone()
                    result: {
                        str: str
                    }

                    if isinstance(result, dict) and "Version" in result.keys():
                        version: str = result["Version"]
                        print(f"应用最新版本: \"{version}\"")
                        self.latest_version_get_signal.emit(version)
                        self.finish_signal.emit("", "", "")
                        return
        except Exception as error:
            self._print_log_error(f"获取应用最新版本发生异常: {traceback.format_exc()}.")
            # self.error_signal.emit(f"获取应用最新版本发生异常: {error}.")
        self.finish_signal.emit("", "", "")

    # def update_app(self):
    #     self.update_progress_text_signal.emit("升级中...")
    #     try:
    #         self._svn_client.update('.')
    #     except Exception as error:
    #         self._print_log_error(f"升级应用发生异常: {traceback.format_exc()}.")
    #         self.error_signal.emit(f"升级应用发生异常: {error}.")

    # def _app_update_completed(self, event_dict: dict):
    #     if not event_dict or "action" not in event_dict.keys():
    #         return
    #     # noinspection PyPackageRequirements,PyUnresolvedReferences
    #     import pysvn
    #
    #     if event_dict["error"]:
    #         self.error_signal.emit(f"升级应用发生异常: {event_dict['error']}")
    #         self.finish_signal.emit("结果", "任务中止", "error")
    #         return
    #
    #     # noinspection PyUnresolvedReferences
    #     if event_dict["action"] == pysvn.wc_notify_action.update_completed:
    #         self.update_finish_signal.emit()
    #         self.finish_signal.emit("", "", "")
    #
    # # noinspection PyUnusedLocal,PyMethodMayBeStatic
    # def _svn_client_get_login(self, realm, username, may_save):
    #     return True, "maybe", "3Z%2*Hv+", False
