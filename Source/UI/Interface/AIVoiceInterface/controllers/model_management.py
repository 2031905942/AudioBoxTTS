"""
Model Management Mixin

Handles model loading, FP16 configuration, and model status management.
"""
import os
import subprocess
from qfluentwidgets import FluentIcon, InfoBar, InfoBarPosition, MessageBox
from PySide6.QtCore import QTimer

from Source.Utility.indextts_utility import IndexTTSUtility
from Source.Utility.indextts_utility import IndexTTSUtilityFactory
from Source.UI.Interface.AIVoiceInterface.dialogs.diagnostics import ModelDiagnosticsDialog


class ModelManagementMixin:
    """Mixin for model management operations."""

    def _check_env_ready_with_warning(self) -> bool:
        """检查 IndexTTS2 环境/模型文件是否就绪；未就绪则弹提示并返回 False。"""
        # 云服务模式：不检查本地 venv/模型文件
        try:
            if str(IndexTTSUtilityFactory.get_current_mode() or "local") == "remote":
                return True
        except Exception:
            pass

        # 先刷新一次快照（快速判断，不阻塞）
        try:
            if hasattr(self, "_check_env_and_model"):
                self._check_env_and_model()
        except Exception:
            pass

        env_ok = bool(getattr(self, "_env_ok_fast", False))
        model_ok = bool(getattr(self, "_model_files_ok", False))

        if not env_ok:
            InfoBar.warning(
                title="环境未就绪",
                content="请先在“使用本地模型”里下载/安装环境依赖。",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3500,
            )
            return False

        if not model_ok:
            InfoBar.warning(
                title="模型文件不完整",
                content="请先在“使用本地模型”里下载依赖和模型文件。",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3500,
            )
            return False

        return True

    def _update_model_status(self):
        """刷新“模型选择/本地模型弹窗”的按钮状态。

        重构拆分后该方法曾遗漏，但多个流程会调用它：
        - 环境检测完成
        - 模型加载/卸载
        - job_completed 回调
        """
        job = getattr(self._main_window, "indextts_job", None)
        is_loaded = False
        try:
            is_loaded = bool(getattr(job, "is_model_loaded", False))
        except Exception:
            is_loaded = False

        # 1) 标题按钮：仅在模型已加载时可点击查看诊断
        title_btn = getattr(self, "model_control_title_btn", None)
        if title_btn is not None:
            try:
                title_btn.setEnabled(bool(is_loaded))
                title_btn.setToolTip("点击查看模型诊断信息" if is_loaded else "")
                # 需求：本地模型加载后，"模型选择" 文案改为提示正在使用本地模型
                try:
                    mode = "local"
                    try:
                        mode = str(IndexTTSUtilityFactory.get_current_mode() or "local")
                    except Exception:
                        mode = "local"
                    if is_loaded and mode == "remote":
                        title_btn.setText("正在使用云服务...")
                    else:
                        title_btn.setText("正在使用本地模型..." if is_loaded else "模型选择")
                except Exception:
                    pass
            except Exception:
                pass

        # 2) 本地模型弹窗：加载/卸载按钮
        btn = getattr(self, "load_model_btn", None)
        if btn is not None:
            try:
                if is_loaded:
                    btn.setEnabled(True)
                    btn.setText("卸载模型")
                    try:
                        btn.setIcon(getattr(FluentIcon, "CLOSE", FluentIcon.CLOSE))
                    except Exception:
                        pass
                    try:
                        btn.setStyleSheet(getattr(self, "_load_btn_style_unload", ""))
                    except Exception:
                        pass
                else:
                    # 加载进行中：保持禁用/文案
                    if bool(getattr(self, "_model_load_in_progress", False)):
                        btn.setEnabled(False)
                        btn.setText("加载中...")
                    else:
                        btn.setEnabled(True)
                        btn.setText("加载模型")
                    try:
                        btn.setIcon(getattr(FluentIcon, "PLAY", FluentIcon.PLAY))
                    except Exception:
                        pass
                    try:
                        btn.setStyleSheet(getattr(self, "_load_btn_style", ""))
                    except Exception:
                        pass
            except Exception:
                pass

        # 3) FP16 开关：模型已加载/加载中时禁用（避免用户误解为即时生效）
        cb = getattr(self, "fp16_checkbox", None)
        if cb is not None:
            try:
                cb.setEnabled((not is_loaded) and (not bool(getattr(self, "_model_load_in_progress", False))) and (not bool(getattr(self, "_synthesis_in_progress", False))))
            except Exception:
                pass

        try:
            self._model_ready = bool(is_loaded)
        except Exception:
            pass

    def _get_fp16_saved_preference(self):
        """获取用户保存的 FP16 偏好设置。
        
        Returns:
            bool | None: True/False 表示用户明确设置；None 表示未设置（首次使用）
        """
        try:
            from Source.Utility.config_utility import config_utility
            val = config_utility.get_config("AIVoice.IndexTTS2.UseFP16", None)
            if val is None:
                return None
            return bool(val)
        except Exception:
            return None

    def _recommend_fp16(self) -> tuple[bool, str]:
        """根据主机配置智能推荐 FP16 开关。"""
        smi = {}
        try:
            smi = self._run_nvidia_smi() or {}
        except Exception:
            smi = {}
        
        def _to_int(x):
            try:
                return int(float(str(x).strip()))
            except Exception:
                return None
        
        total_mb = _to_int(smi.get("mem_total_mb"))
        free_mb = _to_int(smi.get("mem_free_mb"))
        gpu_name = str(smi.get("gpu_name") or "").strip()
        
        # 无法识别 GPU：保守默认关闭，但提示用户按需开启
        if not total_mb:
            return False, "未检测到 NVIDIA 显卡信息：默认关闭。若加载失败/显存不足，可开启 FP16。"
        
        total_gb = total_mb / 1024.0
        free_gb = (free_mb / 1024.0) if free_mb is not None else None
        
        # 经验阈值：
        # - 8GB 及以下：强烈建议 FP16
        # - 12GB：通常建议 FP16（尤其是空闲不足时）
        # - 16GB+：可默认关闭
        if total_mb <= 8192:
            reason = f"检测到 GPU {gpu_name or ''} 显存约 {total_gb:.1f}GB：建议开启 FP16 以降低显存占用。"
            if free_gb is not None:
                reason += f" 当前空闲约 {free_gb:.1f}GB。"
            return True, reason
        
        if total_mb <= 12288:
            if free_mb is not None and free_mb < 9000:
                return True, f"检测到显存约 {total_gb:.1f}GB（空闲偏紧约 {free_gb:.1f}GB）：建议开启 FP16。"
            return True, f"检测到显存约 {total_gb:.1f}GB：开启 FP16 通常更稳、更省显存。"
        
        # 16GB 及以上
        if free_mb is not None and free_mb < 12000:
            return True, f"虽然总显存约 {total_gb:.1f}GB，但当前空闲仅约 {free_gb:.1f}GB：建议开启 FP16。"
        return False, f"检测到显存约 {total_gb:.1f}GB：默认关闭 FP16（需要更省显存时可开启）。"
    

    def _refresh_fp16_hint_text(self) -> None:
        lbl = getattr(self, "fp16_hint_label", None)
        if lbl is None:
            return
        
        saved = self._get_fp16_saved_preference()
        rec, reason = self._recommend_fp16()
        if saved is None:
            lbl.setText(f"自动推荐：{'开启' if rec else '关闭'}。{reason}")
        else:
            lbl.setText(f"已按你的设置：{'开启' if saved else '关闭'}。{reason}")
    

    def _apply_fp16_default(self, *, auto_only: bool = True) -> None:
        """将 FP16 默认值应用到弹窗开关。
        
        auto_only=True：仅当用户没有保存偏好时才自动设置。
        """
        cb = getattr(self, "fp16_checkbox", None)
        if cb is None:
            return
        
        saved = self._get_fp16_saved_preference()
        if auto_only and (saved is not None):
            # 用户有明确偏好：不自动覆盖
            try:
                cb.setChecked(bool(saved))
            except Exception:
                pass
            self._refresh_fp16_hint_text()
            return
        
        rec, _ = self._recommend_fp16()
        try:
            cb.setChecked(bool(rec) if saved is None else bool(saved))
        except Exception:
            pass
        self._refresh_fp16_hint_text()

    def _on_load_model_clicked(self):
        """加载/卸载模型"""
        if getattr(self, "_synthesis_in_progress", False):
            InfoBar.info(
                title="正在生成",
                content="生成进行中，暂不可加载/卸载模型",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return

        # 云服务模式下不允许在此处加载/卸载本地模型
        try:
            if str(IndexTTSUtilityFactory.get_current_mode() or "local") == "remote":
                InfoBar.info(
                    title="云服务模式",
                    content="已启用云服务：本地模型入口已禁用。若要退出云服务，请再次点击“使用线上模型”。",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3500,
                )
                return
        except Exception:
            pass
        job = self._main_window.indextts_job
        
        if job.is_model_loaded:
            # 卸载模型
            job.unload_model()
            self._update_model_status()
            InfoBar.success(
                title="模型已卸载",
                content="显存已释放",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000
            )
        else:
            # 检查环境是否就绪
            if not self._check_env_ready_with_warning():
                return
            
            # 加载模型
            model_dir = IndexTTSUtility.get_default_model_dir()
            
            is_complete, missing = IndexTTSUtility.check_model_files(model_dir)
            if not is_complete:
                InfoBar.error(
                    title="模型文件不完整",
                    content="请先下载依赖和模型",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3000
                )
                return

            # 读取 FP16 开关（若弹窗未创建则按智能推荐/持久化偏好）
            use_fp16 = None
            try:
                cb = getattr(self, "fp16_checkbox", None)
                if cb is not None:
                    use_fp16 = bool(cb.isChecked())
            except Exception:
                use_fp16 = None
            if use_fp16 is None:
                saved = self._get_fp16_saved_preference()
                if saved is None:
                    use_fp16, _ = self._recommend_fp16()
                else:
                    use_fp16 = bool(saved)
            
            # 标记：本次为“模型加载”，用于失败提示/自动重试
            try:
                self._model_load_in_progress = True
                self._model_load_last_fp16 = bool(use_fp16)
            except Exception:
                pass
            
            # 加载耗时提示：若过久仍未完成，给出优化建议（不打断）
            try:
                if not hasattr(self, "_model_load_watchdog") or self._model_load_watchdog is None:
                    self._model_load_watchdog = QTimer(self)
                    self._model_load_watchdog.setSingleShot(True)
                    self._model_load_watchdog.timeout.connect(self._on_model_load_watchdog_timeout)
                self._model_load_watchdog.start(90_000)
            except Exception:
                pass
            
            job.load_model_action(
                model_dir,
                use_fp16=bool(use_fp16),
                use_cuda_kernel=False,
                use_deepspeed=False,
            )
            
            self.load_model_btn.setEnabled(False)
            self.load_model_btn.setText("加载中...")

            # 加载期间禁用 FP16 开关（避免用户误以为实时生效）
            try:
                if getattr(self, "fp16_checkbox", None) is not None:
                    self.fp16_checkbox.setEnabled(False)
            except Exception:
                pass


    def _on_model_load_watchdog_timeout(self):
        """模型加载超过一定时间：提示可能需要 FP16/释放显存。"""
        try:
            if not bool(getattr(self, "_model_load_in_progress", False)):
                return
        except Exception:
            return

        try:
            rec, reason = self._recommend_fp16()
        except Exception:
            rec, reason = (True, "")

        msg = "模型加载时间较长。"
        if bool(getattr(self, "_model_load_last_fp16", False)):
            msg += "已启用 FP16，仍较慢时建议关闭占用显存的软件后重试。"
        else:
            msg += "可能是显存不足导致卡住，建议开启 FP16（半精度）后重试。"
        if reason:
            msg += f"\n{reason}"

        try:
            InfoBar.warning(
                title="模型加载较慢",
                content=msg,
                parent=self,
                position=InfoBarPosition.TOP,
                duration=7000,
            )
        except Exception:
            pass
    

    def _on_model_title_clicked(self):
        """点击标题：展示模型诊断信息。"""
        job = self._main_window.indextts_job
        if not job.is_model_loaded:
            return

        # Job/engine 信息
        try:
            device = job.device
        except Exception:
            device = ""
        device_text = str(device).strip() if device else "未知"

        model_dir = ""
        engine_pid = ""
        engine_alive = ""
        stderr_tail = ""
        try:
            util = getattr(job, "_utility", None)
            if util is not None:
                model_dir = getattr(util, "model_dir", "") or ""
                proc = getattr(util, "_engine_proc", None)
                if proc is not None:
                    try:
                        engine_pid = str(proc.pid)
                    except Exception:
                        engine_pid = ""
                    try:
                        engine_alive = "是" if (proc.poll() is None) else "否"
                    except Exception:
                        engine_alive = ""

                tail = getattr(util, "_engine_stderr_tail", None)
                if isinstance(tail, list) and tail:
                    stderr_tail = "\n".join([str(x) for x in tail[-60:]])
        except Exception:
            pass

        # GPU/CUDA 信息
        smi = self._run_nvidia_smi()

        lines = []
        lines.append("基础")
        lines.append(f"- 设备: {device_text}")
        if model_dir:
            lines.append(f"- 模型目录: {model_dir}")
        if engine_pid:
            lines.append(f"- 引擎进程 PID: {engine_pid}")
        if engine_alive:
            lines.append(f"- 引擎存活: {engine_alive}")

        lines.append("")
        lines.append("CUDA / 显存（来自 nvidia-smi，若可用）")
        if smi:
            if smi.get("gpu_name"):
                lines.append(f"- GPU: {smi.get('gpu_name')}")
            if smi.get("driver_version"):
                lines.append(f"- NVIDIA-SMI: {smi.get('driver_version')}")
            if smi.get("cuda_version"):
                lines.append(f"- CUDA Version: {smi.get('cuda_version')}")
            if smi.get("mem_total_mb"):
                lines.append(
                    f"- 显存(MB): 已用 {smi.get('mem_used_mb')}/{smi.get('mem_total_mb')}，剩余 {smi.get('mem_free_mb')}"
                )
        else:
            lines.append("- 未检测到 nvidia-smi 或读取失败")

        if stderr_tail:
            lines.append("")
            lines.append("引擎日志尾部（stderr tail）")
            lines.append(stderr_tail)

        details = "\n".join(lines)
        dlg = ModelDiagnosticsDialog(self, "模型详细信息", details)
        dlg.exec()


