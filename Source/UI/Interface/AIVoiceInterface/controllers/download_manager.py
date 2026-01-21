"""
Download Manager Mixin

Handles model/environment downloading, deletion, and environment checking.
"""
import os
from PySide6.QtCore import QTimer, QThreadPool, QRunnable, QObject, Signal
from qfluentwidgets import FluentIcon, InfoBar, InfoBarPosition, MessageBox

# After refactor, controller mixins must import all symbols they reference.
from Source.UI.Basic.progress_bar_window import ProgressBarWindow
from Source.UI.Interface.AIVoiceInterface.core.environment_worker import EnvCheckWorker
from Source.UI.Interface.AIVoiceInterface.dialogs.delete_assets import DeleteAssetsChoiceDialog
from Source.UI.Interface.AIVoiceInterface.dialogs.download import DownloadModelChoiceDialog
from Source.UI.Interface.AIVoiceInterface.dialogs.environment import (
    EnvMissingInstallDialog,
    IndexTTSPreflightDialog,
)
from Source.Utility.indextts_preflight_utility import IndexTTSPreflightUtility
from Source.Utility.indextts_utility import IndexTTSUtility


class DownloadManagerMixin:
    """Mixin for download and environment management operations."""

    def _set_env_job_context(
        self,
        *,
        action: str,
        continue_download: bool = False,
        pending_save_dir: str | None = None,
    ):
        """记录最近一次环境安装/卸载操作的上下文。

        目的：避免“卸载环境/删除资源”后因为残留状态误触发下载流程。
        """
        try:
            self._env_job_action = str(action or "")
        except Exception:
            self._env_job_action = ""
        try:
            self._env_job_continue_download = bool(continue_download)
        except Exception:
            self._env_job_continue_download = False
        try:
            self._pending_save_dir = pending_save_dir
        except Exception:
            self._pending_save_dir = None

    def _on_download_clicked(self):
        """下载或删除依赖和模型"""
        if getattr(self, "_synthesis_in_progress", False):
            InfoBar.info(
                title="正在生成",
                content="生成进行中，暂不可执行该操作",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return
        # 统一模型目录来源：避免 refactor 后误指向 Source/checkpoints。
        save_dir = IndexTTSUtility.get_default_model_dir()
        try:
            save_dir = os.path.abspath(save_dir)
        except Exception:
            pass

        # 刷新一次快照，避免依赖缓存状态导致误判
        try:
            self._check_env_and_model()
        except Exception:
            pass

        # 仅在“安装环境后继续下载模型”的链路中才需要 pending_save_dir
        if not bool(getattr(self, "_is_delete_mode", False)):
            try:
                self._pending_save_dir = None
            except Exception:
                pass

        # 下载模式：首次点击前做一次设备预检（删除模式不拦截）
        if not getattr(self, "_is_delete_mode", False):
            if not self._run_indextts_preflight_before_download(save_dir):
                return

        # 若模型齐全但环境缺失：提供“下载环境依赖”入口（保持弹窗样式一致）
        if getattr(self, "_model_files_ok", False) and (not getattr(self, "_env_ok_fast", False)):
            self._show_fix_env_dialog(save_dir)
            return

        if self._is_delete_mode:
            # 删除模式：让用户选择删除模型 or 删除依赖
            self._show_delete_assets_dialog(save_dir)
            return

        # 下载模式：环境检测在“使用本地模型”打开时已触发；这里直接复用结果。
        if getattr(self, "_env_check_pending", False):
            InfoBar.info(
                title="正在检测环境",
                content="请稍候，环境检测完成后再继续",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2500,
            )
            return

        last_ready = getattr(self, "_env_check_last_ready", None)
        last_msg = str(getattr(self, "_env_check_last_msg", "") or "")

        # 若快速快照显示环境未就绪，则不要相信之前缓存的 "last_ready=True"。
        try:
            if (last_ready is True) and (not bool(getattr(self, "_env_ok_fast", False))):
                last_ready = None
        except Exception:
            pass

        if last_ready is True:
            self._download_model_files(save_dir)
            return

        if last_ready is False and last_msg:
            dialog = EnvMissingInstallDialog(self._main_window, last_msg)
            res = dialog.exec()
            if res and dialog.choice == "install":
                self._set_env_job_context(action="install", continue_download=True, pending_save_dir=save_dir)
                try:
                    from PySide6.QtCore import Qt

                    self._main_window.indextts_env_job.job_completed.connect(
                        self._on_env_job_finished, Qt.ConnectionType.UniqueConnection
                    )
                except Exception:
                    try:
                        self._main_window.indextts_env_job.job_completed.connect(self._on_env_job_finished)
                    except Exception:
                        pass
                self._main_window.indextts_env_job.install_action()
            return

        # 兜底：若还没有任何检测结果，则回退为交互式检测流程
        self._start_async_env_check(save_dir, show_install_dialog_on_missing=True, on_ready="download")


    def _run_indextts_preflight_before_download(self, save_dir: str) -> bool:
        """IndexTTS2 下载前设备预检。

        - 通过：不打扰，直接进入下载流程
        - 有建议项：弹窗提示，允许继续/取消
        - 有阻断项：弹窗提示并阻止继续（避免下载后无法运行或下载失败）
        """

        if getattr(self, "_indextts_preflight_checked", False):
            return True

        result = IndexTTSPreflightUtility.run_check(save_dir)

        # 结构化输出到运行时终端（便于排查用户环境问题）
        try:
            print(IndexTTSPreflightUtility.format_terminal_block(result), flush=True)
        except Exception:
            pass

        if result.has_blockers:
            report = IndexTTSPreflightUtility.format_report_text(result)
            dialog = IndexTTSPreflightDialog(self._main_window, report, can_continue=False)
            dialog.exec()
            return False

        if result.has_warnings:
            report = IndexTTSPreflightUtility.format_report_text(result)
            dialog = IndexTTSPreflightDialog(self._main_window, report, can_continue=True)
            res = dialog.exec()
            if res and dialog.choice == "continue":
                self._indextts_preflight_checked = True
                return True
            return False

        self._indextts_preflight_checked = True
        return True


    def _show_fix_env_dialog(self, save_dir: str):
        """环境缺失但模型齐全时的弹窗入口：提供“下载环境依赖”按钮。"""
        dialog = DeleteAssetsChoiceDialog(self._main_window, save_dir, env_action="download")
        res = dialog.exec()

        if dialog.choice == "download_env":
            QTimer.singleShot(100, self._download_env_only)
            return

        if res and dialog.choice == "delete_model":
            self._delete_model_files(save_dir)

    def _show_delete_assets_dialog(self, save_dir: str):
        """删除入口弹窗：将“删除模型”和“删除依赖”分离为两个按键。"""
        # 检查模型是否已加载
        if self._main_window.indextts_job.is_model_loaded:
            InfoBar.warning(
                title="请先卸载模型",
                content="模型正在使用中，请先卸载模型后再删除",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        dialog = DeleteAssetsChoiceDialog(self._main_window, save_dir)
        res = dialog.exec()

        if dialog.choice == "delete_env":
            # 新弹窗已经是确认，因此跳过二次确认
            QTimer.singleShot(100, lambda: self._delete_env_only(skip_confirm=True))
            return

        if res and dialog.choice == "delete_model":
            self._delete_model_files(save_dir)


    def _download_env_only(self):
        """仅安装 IndexTTS2 独立环境依赖（Runtime/IndexTTS2/.venv）。"""
        # 单独安装环境：仅更新状态，不自动触发模型下载
        self._set_env_job_context(action="install", continue_download=False, pending_save_dir=None)
        try:
            from PySide6.QtCore import Qt

            self._main_window.indextts_env_job.job_completed.connect(
                self._on_env_job_finished, Qt.ConnectionType.UniqueConnection
            )
        except Exception:
            try:
                self._main_window.indextts_env_job.job_completed.connect(self._on_env_job_finished)
            except Exception:
                pass

        self._main_window.indextts_env_job.install_action()

    def _start_async_env_check(
        self,
        save_dir: str,
        *,
        show_install_dialog_on_missing: bool = True,
        on_ready: str = "download",
    ):
        """异步检查环境。

        Args:
            save_dir: 模型目录
            show_install_dialog_on_missing: 环境缺失时是否弹出“下载依赖”对话框
            on_ready: 环境就绪后的动作："download" 触发下载流程；"none" 仅更新状态
        """
        if self._env_check_pending:
            return

        # 资源状态代号：当用户在检测期间执行“删除模型/删除环境”等破坏性操作时，
        # 我们需要丢弃过期的检测结果，避免误弹窗/误触发下载。
        try:
            assets_epoch = int(getattr(self, "_assets_epoch", 0) or 0)
        except Exception:
            assets_epoch = 0

        self._env_check_pending = True
        self._env_check_request_id += 1
        request_id = self._env_check_request_id

        try:
            if getattr(self, "download_btn", None) is not None:
                self.download_btn.setEnabled(False)
                self.download_btn.setText("正在检测环境...")
        except Exception:

            pass

        worker = EnvCheckWorker()
        # Keep a strong reference to avoid Python GC interrupting signal delivery.
        try:
            worker.setAutoDelete(False)
        except Exception:
            pass
        self._env_check_worker = worker

        worker.signals.finished.connect(
            lambda is_ready, msg: self._on_env_check_finished(
                request_id,
                is_ready,
                msg,
                save_dir,
                assets_epoch=assets_epoch,
                show_install_dialog_on_missing=bool(show_install_dialog_on_missing),
                on_ready=str(on_ready or "download"),
            )
        )
        QThreadPool.globalInstance().start(worker)

        # Watchdog: avoid being stuck forever if worker is blocked.
        QTimer.singleShot(20000, lambda: self._on_env_check_timeout(request_id))

    def _on_env_check_timeout(self, request_id: int):
        if not self._env_check_pending:
            return
        if request_id != self._env_check_request_id:

            return

        self._env_check_pending = False
        self._env_check_worker = None
        try:
            if getattr(self, "download_btn", None) is not None:
                self.download_btn.setEnabled(True)
        except Exception:
            pass
        self._check_env_and_model()

        InfoBar.warning(
            title="环境检测超时",
            content="环境检测耗时过长，请稍后重试或直接点击“安装并下载”。",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=4500
        )

    def _on_env_check_finished(
        self,
        request_id: int,
        is_ready: bool,
        msg: str,
        save_dir: str,
        *,
        assets_epoch: int | None = None,
        show_install_dialog_on_missing: bool = True,
        on_ready: str = "download",
    ):
        """环境检测完成回调"""
        if request_id != self._env_check_request_id:
            return

        # 若期间发生过删除等破坏性操作，丢弃该次检测的“后续动作”（弹窗/自动下载）。
        try:
            current_epoch = int(getattr(self, "_assets_epoch", 0) or 0)
        except Exception:
            current_epoch = 0
        is_stale = (assets_epoch is not None) and (int(assets_epoch) != int(current_epoch))

        self._env_check_pending = False
        self._env_check_worker = None
        try:
            if getattr(self, "download_btn", None) is not None:
                self.download_btn.setEnabled(True)
        except Exception:
            pass
        # 检查当前状态（如果文件已存在，则更新为删除模式；否则保持下载模式）
        self._check_env_and_model()

        # 缓存最近一次检测结果，供“下载依赖和模型”点击时复用
        try:
            if is_stale:
                self._env_check_last_ready = None
                self._env_check_last_msg = ""
            else:
                self._env_check_last_ready = bool(is_ready)
                self._env_check_last_msg = str(msg or "")
        except Exception:
            if is_stale:
                self._env_check_last_ready = None
                self._env_check_last_msg = ""
            else:
                self._env_check_last_ready = bool(is_ready)
                self._env_check_last_msg = ""

        if is_stale:
            return
        
        if not is_ready:

            if not bool(show_install_dialog_on_missing):
                return

            # 提示安装环境（自定义布局，保证按钮不重叠；样式与“下载模型”窗口一致）
            dialog = EnvMissingInstallDialog(self._main_window, msg)
            res = dialog.exec()
            if res and dialog.choice == "install":
                self._set_env_job_context(action="install", continue_download=True, pending_save_dir=save_dir)

                # 连接信号，等待环境安装完成
                try:
                    from PySide6.QtCore import Qt

                    self._main_window.indextts_env_job.job_completed.connect(
                        self._on_env_job_finished, Qt.ConnectionType.UniqueConnection
                    )
                except Exception:
                    try:
                        self._main_window.indextts_env_job.job_completed.connect(self._on_env_job_finished)
                    except Exception:
                        pass

                # 启动环境安装
                self._main_window.indextts_env_job.install_action()

            return

        # 环境已就绪
        if str(on_ready).lower() == "download":
            # 进入模型下载流程
            self._download_model_files(save_dir)
            return

        # on_ready == none: 仅更新状态，不触发下载
        return

    def _on_env_job_finished(self, success: bool):
        """环境安装完成回调"""
        # 安装/卸载完成后，刷新按钮与生成状态
        self._check_env_and_model()
        self._update_generate_btn_state()

        action = str(getattr(self, "_env_job_action", "") or "")
        should_continue = bool(getattr(self, "_env_job_continue_download", False))

        # 只在“安装环境 + 继续下载模型”的明确链路中自动进入下载。
        if success and action == "install" and should_continue:
            pending_dir = getattr(self, "_pending_save_dir", None)
            if pending_dir:
                QTimer.singleShot(500, lambda: self._download_model_files(pending_dir))

        # 无论成功与否都清理上下文，避免下一次卸载/删除误触发。
        self._set_env_job_context(action="", continue_download=False, pending_save_dir=None)

    def _download_model_files(self, save_dir: str):
        """下载模型文件"""
        # 安全检查：如果路径为空，使用默认路径
        if not save_dir:
            save_dir = IndexTTSUtility.get_default_model_dir()
        try:
            save_dir = os.path.abspath(save_dir)
        except Exception:
            pass

        # 检测是否已完整
        is_complete, missing = IndexTTSUtility.check_model_files(save_dir)
        if is_complete:
            InfoBar.success(
                title="模型已就绪",
                content="依赖和模型文件已完整",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            # 刷新按钮状态：模型齐全后还需结合环境是否存在
            self._check_env_and_model()
            return

        dialog = DownloadModelChoiceDialog(self._main_window, save_dir)
        res = dialog.exec()

        if dialog.choice == "delete_env":
            QTimer.singleShot(100, self._delete_env_only)
            return

        if res:
            use_mirror = (dialog.choice != "direct")
            self._main_window.indextts_download_job.download_action(save_dir, use_mirror=use_mirror)

    def _delete_env_only(self, skip_confirm: bool = False):
        """仅删除 IndexTTS2 独立环境（Runtime/IndexTTS2/.venv），不删除模型文件。"""
        # 检查模型是否已加载
        if self._main_window.indextts_job.is_model_loaded:
            InfoBar.warning(
                title="请先卸载模型",
                content="模型正在使用中，请先卸载模型后再删除环境依赖",
                parent=self,

                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        if not skip_confirm:
            msg = MessageBox(
                "删除环境依赖",
                "确定要删除 IndexTTS2 独立环境吗？\n\n"
                "将删除: Runtime/IndexTTS2/.venv\n\n"
                "模型文件（checkpoints）不会被删除。",
                self._main_window
            )
            msg.yesButton.setText("确认删除")
            msg.cancelButton.setText("取消")
            self._tune_message_box(msg)

            if not msg.exec():
                return

        # 卸载环境不应触发任何下载流程（清理缓存与 pending 状态）
        self._set_env_job_context(action="uninstall", continue_download=False, pending_save_dir=None)
        try:
            self._assets_epoch = int(getattr(self, "_assets_epoch", 0) or 0) + 1
        except Exception:
            self._assets_epoch = 1
        try:
            self._env_check_last_ready = None
            self._env_check_last_msg = ""
        except Exception:
            pass

        self._main_window.indextts_env_job.uninstall_action()
        self._env_ready = False
        self._update_generate_btn_state()

        # 卸载结束后刷新界面状态（避免按钮文案不更新）
        try:
            from PySide6.QtCore import Qt

            self._main_window.indextts_env_job.job_completed.connect(
                self._on_env_job_finished, Qt.ConnectionType.UniqueConnection
            )
        except Exception:
            try:
                self._main_window.indextts_env_job.job_completed.connect(self._on_env_job_finished)
            except Exception:
                pass

    def _delete_model_files(self, save_dir: str):
        """删除模型文件（不删除独立环境依赖）。"""
        # 检查模型是否已加载
        if self._main_window.indextts_job.is_model_loaded:
            InfoBar.warning(
                title="请先卸载模型",
                content="模型正在使用中，请先卸载模型后再删除",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        # 注意：确认弹窗在 _show_delete_assets_dialog 中已经执行，这里不再二次确认。

        # 删除模型文件属于破坏性操作：清理环境检测缓存与 pending 状态，避免误用旧结果。
        try:
            self._assets_epoch = int(getattr(self, "_assets_epoch", 0) or 0) + 1
        except Exception:
            self._assets_epoch = 1
        try:
            self._env_check_last_ready = None
            self._env_check_last_msg = ""
        except Exception:
            pass
        try:
            self._pending_save_dir = None
        except Exception:
            pass

        # 收集要删除的文件
        files_to_delete = []
        for filename in IndexTTSUtility.get_required_files():
            file_path = os.path.join(save_dir, filename)
            if os.path.exists(file_path):
                files_to_delete.append(file_path)
        
        # 添加可选的 feat 文件
        for feat_file in ["feat1.pt", "feat2.pt"]:
            file_path = os.path.join(save_dir, feat_file)
            if os.path.exists(file_path):
                files_to_delete.append(file_path)
        
        # 添加要删除的文件夹（模型下载产生的目录）
        dirs_to_delete = []
        for dir_name in ["qwen0.6bemo4-merge", "hf_cache", "amphion", "facebook"]:
            dir_path = os.path.join(save_dir, dir_name)
            if os.path.exists(dir_path):
                dirs_to_delete.append(dir_path)
        
        # 显示进度弹窗 (用于文件删除阶段)
        progress_window = ProgressBarWindow(self._main_window)
        progress_window.set_text("正在删除模型文件...")
        progress_window.set_total_count(len(files_to_delete) + len(dirs_to_delete))
        progress_window.set_enable_cancel(False)  # 删除操作不可取消
        
        # 执行文件删除
        try:
            import shutil
            from PySide6.QtWidgets import QApplication
            deleted_count = 0
            failed: list[str] = []
            
            # 1. 删除文件
            for i, file_path in enumerate(files_to_delete):
                try:
                    filename = os.path.basename(file_path)
                    progress_window.set_text(f"正在删除文件: {filename}")
                    progress_window.set_current_count(deleted_count)
                    QApplication.processEvents()  # 刷新 UI
                    
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"删除文件失败: {file_path}, 错误: {e}")
                    try:
                        failed.append(str(file_path))
                    except Exception:
                        pass
            
            # 2. 删除文件夹
            for dir_path in dirs_to_delete:
                try:
                    dirname = os.path.basename(dir_path)
                    progress_window.set_text(f"正在删除目录: {dirname}")
                    progress_window.set_current_count(deleted_count)
                    QApplication.processEvents()
                    
                    shutil.rmtree(dir_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"删除目录失败: {dir_path}, 错误: {e}")
                    try:
                        failed.append(str(dir_path))
                    except Exception:
                        pass
            
            progress_window.set_current_count(len(files_to_delete) + len(dirs_to_delete))
            progress_window.set_text("文件删除完成，准备卸载依赖...")
            QApplication.processEvents()

            # 检查目录是否为空，如果为空则删除目录
            if os.path.exists(save_dir) and not os.listdir(save_dir):
                os.rmdir(save_dir)

            progress_window.close()

            if failed:
                try:
                    InfoBar.warning(
                        title="部分文件未能删除",
                        content="有文件/目录可能被占用或权限不足，建议关闭占用程序后重试。",
                        parent=self,
                        position=InfoBarPosition.TOP,
                        duration=5000,
                    )
                except Exception:
                    pass

            # 仅删除模型文件：保留独立环境，以便后续重新下载模型更快。
            self._check_env_and_model()
            self._update_generate_btn_state()

        except Exception as e:
            progress_window.close()
            InfoBar.error(
                title="删除失败",
                content=str(e),
                parent=self,
                position=InfoBarPosition.TOP,
                duration=5000
            )
            
            # 更新按钮状态
            self._check_env_and_model()
            self._env_ready = False
            self._update_generate_btn_state()


    def _update_download_btn_state(self, env_ok: bool, model_ok: bool):
        """更新下载/删除按钮状态

        - env_ok & model_ok: 配置完成 -> 删除入口
        - !env_ok & model_ok: 缺乏依赖（仅环境缺失）-> 保持黄色样式，提供下载环境依赖入口
        - otherwise: 下载依赖和模型
        """
        btn = getattr(self, "download_btn", None)

        # 先更新内部状态（即使按钮尚未创建）
        self._is_delete_mode = bool(env_ok and model_ok)

        # 弹窗懒创建：界面 refresh() 可能先于弹窗按钮创建
        if btn is None:
            return

        # 1) 配置完成：允许删除
        if env_ok and model_ok:
            btn.setText("配置完成，点击可删除")
            # 视觉保持与“加载完成，点击可卸载”一致：浅蓝 + 对勾
            btn.setIcon(FluentIcon.ACCEPT)
            btn.setToolTip("删除 IndexTTS2 的依赖和模型文件以释放磁盘空间")
            if hasattr(self, "_model_btn_icon_size"):
                btn.setIconSize(self._model_btn_icon_size)
            btn.setStyleSheet(getattr(self, "_load_btn_style_unload", ""))
            return

        # 2) 仅环境缺失：保持黄色样式，但引导下载环境依赖
        if (not env_ok) and model_ok:
            btn.setText("缺乏依赖，点击可下载")
            btn.setIcon(FluentIcon.DOWNLOAD)
            btn.setToolTip("检测到环境依赖缺失，点击可下载/安装环境依赖")
            if hasattr(self, "_model_btn_icon_size"):
                btn.setIconSize(self._model_btn_icon_size)
            # 复用当前“配置完成”黄色样式
            btn.setStyleSheet(getattr(self, "_download_btn_style_delete", ""))
            return

        # 3) 其余情况：下载依赖和模型
        btn.setText("下载依赖和模型")
        btn.setIcon(FluentIcon.DOWNLOAD)
        btn.setToolTip("下载 IndexTTS2 所需的依赖和模型文件（约 5GB）")
        if hasattr(self, "_model_btn_icon_size"):
            btn.setIconSize(self._model_btn_icon_size)
        btn.setStyleSheet(getattr(self, "_download_btn_style_download", ""))


