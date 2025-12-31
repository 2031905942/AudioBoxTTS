"""
IndexTTS2 环境安装 Job

负责线程管理、进度窗口。
"""
from typing import Optional

from PySide6.QtCore import Signal

from Source.Job.base_job import BaseJob
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.Utility.indextts_env_utility import IndexTTSEnvUtility


class IndexTTSEnvJob(BaseJob):
    """IndexTTS2 环境安装/卸载 Job"""

    # 信号
    install_signal = Signal(bool, str)  # use_cuda, mirror
    uninstall_signal = Signal()
    job_completed = Signal(bool)  # success

    def __init__(self, main_window):
        super().__init__(main_window)
        self._utility: Optional[IndexTTSEnvUtility] = None
        self._log_lines: list = []
        self._current_operation = "install"  # install or uninstall

    @property
    def install_log(self) -> str:
        """获取安装日志"""
        return "\n".join(self._log_lines[-100:])  # 最近 100 行

    def install_action(self, use_cuda: bool = True, mirror: str = "default"):
        """开始安装（UI 调用入口）

        Args:
            use_cuda: 是否安装 CUDA 版本
            mirror: PyPI 镜像 (aliyun/tsinghua/default)
        """
        if self.worker_thread.isRunning():
            self.show_error_info_bar("任务进行中，请稍候")
            return

        self._current_operation = "install"
        self._log_lines.clear()
        self._create_utility()
        self._utility.moveToThread(self.worker_thread)

        self.start_worker()
        self._create_progress_bar_window("准备安装环境...")

        self.install_signal.emit(use_cuda, mirror)

    def uninstall_action(self):
        """开始卸载（UI 调用入口）"""
        if self.worker_thread.isRunning():
            self.show_error_info_bar("任务进行中，请稍候")
            return

        self._current_operation = "uninstall"
        self._log_lines.clear()
        self._create_utility()
        self._utility.moveToThread(self.worker_thread)

        self.start_worker()
        self._create_progress_bar_window("准备卸载依赖...")

        self.uninstall_signal.emit()

    def cancel_install(self):
        """取消任务"""
        if self._utility:
            self._utility.cancel()

    def _create_utility(self):
        """创建 Utility 实例"""
        self._utility = IndexTTSEnvUtility()

        self.install_signal.connect(self._utility.install_dependencies)
        self.uninstall_signal.connect(self._utility.uninstall_dependencies)
        self._utility.progress_signal.connect(self._on_progress)
        self._utility.error_signal.connect(self._on_error)
        self._utility.finished_signal.connect(self._on_finished)
        self._utility.log_signal.connect(self._on_log)

    def _create_progress_bar_window(self, title="准备中..."):
        """创建进度条窗口"""
        self._progress_bar_window = ProgressBarWindow(self.main_window)
        self._progress_bar_window.set_enable_cancel(True)
        self._progress_bar_window.cancel_signal.connect(self.cancel_install)
        self._progress_bar_window.set_text(title)
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
        op_name = "环境安装" if self._current_operation == "install" else "环境卸载"
        self.job_finish(op_name, message, "error")
        self.job_completed.emit(False)

    def _on_finished(self, success: bool):
        """任务完成"""
        self.worker_thread.quit()
        
        op_name = "环境安装" if self._current_operation == "install" else "环境卸载"
        
        if success:
            msg = "IndexTTS2 环境安装成功！" if self._current_operation == "install" else "依赖卸载成功！"
            self.job_finish(op_name, msg, "success")
        else:
            msg = "部分依赖安装失败，请查看日志" if self._current_operation == "install" else "部分依赖卸载失败"
            self.job_finish(op_name, msg, "warning")
            
        self.job_completed.emit(success)

    def _on_log(self, line: str):
        """日志输出"""
        self._log_lines.append(line)
        # 可以在这里更新 UI 显示日志

    @staticmethod
    def check_env_ready() -> tuple[bool, str]:
        """检查环境是否就绪

        Returns:
            (是否就绪, 描述)
        """
        # 使用新的子进程安全检测方法
        is_ready, msg, _ = IndexTTSEnvUtility.check_full_env_status()
        return is_ready, msg
