from PySide6.QtCore import QDir, Signal

from Source.Job.base_job import BaseJob
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.UI.Basic.progress_ring_window import ProgressRingWindow
from Source.Utility.config_utility import ProjectData, config_utility
from Source.Utility.soundbank_utility import SoundbankUtility


class SoundBankJob(BaseJob):
    _sync_soundbank_signal: Signal = Signal(str)
    _clean_generated_soundbanks_dir_signal: Signal = Signal(str)

    def __init__(self, main_window):
        super().__init__(main_window)
        self._soundbank_utility: SoundbankUtility | None = None
        self._last_report_dialog = None

    def sync_soundbank_action(self, project_id: str):
        unity_soundbank_dir_path: str | None = config_utility.get_config(ProjectData.UNITY_WWISE_BANK_PATH, project_id)
        if not unity_soundbank_dir_path:
            self.show_error_info_bar("无法同步声音库, Unity工程声音库目录为空, 请正确设置后再执行.")
            self.job_finish("结果", "任务中止", "error")
            return
        self._soundbank_utility = SoundbankUtility(self)
        unity_soundbank_dir: QDir = QDir(unity_soundbank_dir_path)
        if not unity_soundbank_dir.exists():
            if self._create_dialog("创建Unity工程声音库目录", f"Unity工程声音库目录\"{unity_soundbank_dir_path}\"不存在, 是否需要创建目录并继续同步任务?"):
                if not self._soundbank_utility.create_directory(unity_soundbank_dir_path):
                    self.job_finish("结果", "任务中止", "error")
                    return
            else:
                self.job_finish("结果", "任务中止", "warning")
                return

        self._create_utility()
        self.start_worker()
        self._create_progress_bar_window()
        self._sync_soundbank_signal.emit(project_id)

    def clean_generated_soundbanks_dir_action(self, project_id: str):
        self._create_utility()
        self.start_worker()
        self._create_progress_ring_window()
        self._clean_generated_soundbanks_dir_signal.emit(project_id)

    def job_finish(self, title: str, content: str, result: str):
        if self._soundbank_utility:
            self._soundbank_utility.deleteLater()
            self._soundbank_utility = None

        # 进度窗关闭 & 解除主窗禁用（复用 BaseJob 行为）
        self.delete_progress_window()
        self.main_window.setDisabled(False)

        # InfoBar 内容保持简短；同步声音库则额外弹出详细报告窗口
        summary = content
        if isinstance(content, str) and "\n" in content:
            summary = content.splitlines()[0]

        self.show_result_info_bar(result, title, summary)

        if result == "success" and isinstance(content, str) and content.startswith("同步声音库完成"):
            try:
                from Source.UI.Basic.text_report_dialog import TextReportDialog

                dlg = TextReportDialog(self.main_window, "同步声音库 - 变更明细", content)
                dlg.show()
                dlg.raise_()
                self._last_report_dialog = dlg
            except Exception:
                # 回退：至少保证有摘要提示
                pass

        self.main_window.raise_()

    def _create_utility(self):
        self._soundbank_utility: SoundbankUtility = SoundbankUtility(self)
        self._soundbank_utility.moveToThread(self.worker_thread)
        self._sync_soundbank_signal.connect(self._soundbank_utility.sync_soundbank_job)
        self._clean_generated_soundbanks_dir_signal.connect(self._soundbank_utility.clean_generated_soundbanks_dir_job)

    def _create_progress_bar_window(self):
        self._progress_bar_window: ProgressBarWindow = ProgressBarWindow(self.main_window)
        self._progress_bar_window.cancel_signal.connect(lambda: self._soundbank_utility.notice_cancel_job())

        self._soundbank_utility.update_progress_text_signal.connect(self._progress_bar_window.set_text)
        self._soundbank_utility.update_progress_total_count_signal.connect(self._progress_bar_window.set_total_count)
        self._soundbank_utility.update_progress_current_count_signal.connect(self._progress_bar_window.set_current_count)

    def _create_progress_ring_window(self):
        self._progress_ring_window: ProgressRingWindow = ProgressRingWindow(self.main_window)
        self._progress_ring_window.cancel_signal.connect(lambda: self._soundbank_utility.notice_cancel_job())

        self._soundbank_utility.update_progress_text_signal.connect(self._progress_ring_window.set_text)
