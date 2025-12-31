"""
IndexTTS2 模型下载 Job

负责线程管理、进度窗口、错误提示。
"""
import os
from typing import Optional

from PySide6.QtCore import Signal

from Source.Job.base_job import BaseJob
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.Utility.indextts_download_utility import IndexTTSDownloadUtility


class IndexTTSDownloadJob(BaseJob):
    """IndexTTS2 模型下载 Job"""

    # 信号
    download_signal = Signal(str, str, bool)  # local_dir, repo_id, use_mirror
    job_completed = Signal(bool)  # success

    def __init__(self, main_window):
        super().__init__(main_window)
        self._utility: Optional[IndexTTSDownloadUtility] = None
        self._downloaded_dir: Optional[str] = None

    @property
    def downloaded_dir(self) -> Optional[str]:
        """下载完成的目录"""
        return self._downloaded_dir

    def download_action(self, local_dir: str, repo_id: str = "IndexTeam/IndexTTS-2",
                        use_mirror: bool = False):
        """开始下载（UI 调用入口）

        Args:
            local_dir: 本地保存目录
            repo_id: HuggingFace 仓库 ID
            use_mirror: 是否使用 hf-mirror.com 镜像
        """
        if self.worker_thread.isRunning():
            self.show_error_info_bar("下载任务进行中，请稍候")
            return

        # 检查磁盘空间
        is_enough, msg = IndexTTSDownloadUtility.check_disk_space(
            os.path.dirname(local_dir) or local_dir, required_mb=5000
        )
        if not is_enough:
            self.show_error_info_bar(msg)
            return

        self._create_utility()
        self._utility.moveToThread(self.worker_thread)

        self.start_worker()
        self._create_progress_bar_window()

        self.download_signal.emit(local_dir, repo_id, use_mirror)

    def cancel_download(self):
        """取消下载"""
        if self._utility:
            self._utility.cancel()

    def _create_utility(self):
        """创建 Utility 实例并连接信号"""
        self._utility = IndexTTSDownloadUtility()

        self.download_signal.connect(self._utility.download)
        self._utility.progress_signal.connect(self._on_progress)
        self._utility.error_signal.connect(self._on_error)
        self._utility.finished_signal.connect(self._on_finished)
        self._utility.file_downloaded_signal.connect(self._on_file_downloaded)

    def _create_progress_bar_window(self):
        """创建进度条窗口"""
        self._progress_bar_window = ProgressBarWindow(self.main_window)
        self._progress_bar_window.set_enable_cancel(True)
        self._progress_bar_window.cancel_signal.connect(self.cancel_download)
        self._progress_bar_window.set_text("准备下载...")
        self._progress_bar_window.set_total_count(100)
        self._progress_bar_window.set_current_count(0)

    def _on_progress(self, progress: float, text: str):
        """进度更新"""
        if self._progress_bar_window:
            self._progress_bar_window.set_current_count(int(progress * 100))
            self._progress_bar_window.set_text(text)

    def _on_error(self, message: str):
        """错误回调"""
        self.worker_thread.quit()
        self.job_finish("模型下载", message, "error")
        self.job_completed.emit(False)

    def _on_finished(self, local_dir: str):
        """下载完成"""
        self._downloaded_dir = local_dir
        self.worker_thread.quit()
        self.job_finish("模型下载", f"下载完成！\n保存至: {local_dir}", "success")
        self.job_completed.emit(True)

    def _on_file_downloaded(self, filename: str):
        """单文件下载完成"""
        # 可以用于更新 UI 显示已下载文件列表
        pass
