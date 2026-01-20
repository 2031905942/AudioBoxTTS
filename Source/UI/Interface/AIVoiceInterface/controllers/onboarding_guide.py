"""
Onboarding Guide Mixin

Handles first-time user guidance and teaching tips.
"""
import os

from PySide6.QtCore import QTimer, Qt, QPoint, QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from qfluentwidgets import PrimaryPushButton, PushButton, TeachingTip, TeachingTipTailPosition

from Source.UI.Interface.AIVoiceInterface.core.ui_overlays import _ModalInputBlockerOverlay
from Source.UI.Interface.AIVoiceInterface.dialogs.online_model import OnlineModelDialog


class OnboardingGuideMixin:
    """Mixin for onboarding and teaching tip operations."""

    def _get_quick_guide_fallback_target(self) -> QWidget | None:
        """当某一步目标控件不可见/不可用时，选择一个稳定可见的锚点控件。

        目标：确保 TeachingTip 一定能显示，而不是回退到旧式 MessageBox。
        """
        for name in (
            "_ai_voice_tab_bar",
            "model_control_panel_card",
            "use_local_model_btn",
            "text_edit",
        ):
            try:
                w = getattr(self, name, None)
                if w is not None and hasattr(w, "isVisible") and w.isVisible():
                    return w
            except Exception:
                continue
        try:
            win = getattr(self, "_main_window", None)
            if win is not None and hasattr(win, "isVisible") and win.isVisible():
                return win
        except Exception:
            pass
        return None

    def _ensure_teaching_tip_modal_blocker(self):
        """开启透明输入拦截层，让 TeachingTip 流程表现为“模态”。"""
        try:
            if getattr(self, "_quick_guide_modal_overlay", None) is None and self._main_window is not None:
                self._quick_guide_modal_overlay = _ModalInputBlockerOverlay(self._main_window)
            overlay = getattr(self, "_quick_guide_modal_overlay", None)
            if overlay is not None:
                overlay.show()
                overlay.raise_()
        except Exception:
            pass


    def _update_teaching_tip_spotlight(self, target: QWidget | None):
        """更新 spotlight 高亮区域。"""
        overlay = getattr(self, "_quick_guide_modal_overlay", None)
        if overlay is None:
            return
        try:
            overlay.set_spotlight_target(target)
        except Exception:
            pass


    def _teardown_teaching_tip_modal_blocker(self):
        """关闭并释放透明输入拦截层。"""
        overlay = getattr(self, "_quick_guide_modal_overlay", None)
        if overlay is None:
            return
        try:
            try:
                overlay.set_spotlight_target(None)
            except Exception:
                pass
            overlay.hide()
        except Exception:
            pass
        try:
            overlay.deleteLater()
        except Exception:
            pass
        self._quick_guide_modal_overlay = None


    def _configure_teaching_tip_view_for_wrapping(self, tip: QWidget, view: QWidget):
        """尽量避免 TeachingTip 由于不换行导致的越界/超宽。"""
        try:
            from PySide6.QtWidgets import QLabel
        except Exception:
            QLabel = None  # type: ignore

        max_content_w = 520
        try:
            win = getattr(self, "_main_window", None)
            if win is not None and hasattr(win, "width"):
                w = int(win.width())
                # 适配：宽窗口用更舒适的宽度，小窗口跟随缩小
                max_content_w = int(min(560, max(340, w * 0.45)))
        except Exception:
            pass

        try:
            if QLabel is not None:
                title_label = view.findChild(QLabel, "titleLabel")
                content_label = view.findChild(QLabel, "contentLabel")

                if title_label is not None:
                    try:
                        title_label.setWordWrap(True)
                        title_label.setMaximumWidth(max_content_w)
                    except Exception:
                        pass

                if content_label is not None:
                    try:
                        content_label.setWordWrap(True)
                        content_label.setMaximumWidth(max_content_w)
                    except Exception:
                        pass
        except Exception:
            pass

        # 给 view 也加一个上限，避免布局把窗口拉到非常宽
        try:
            view.setMaximumWidth(int(max_content_w + 72))
        except Exception:
            pass

        try:
            view.adjustSize()
        except Exception:
            pass
        try:
            tip.adjustSize()
        except Exception:
            pass


    def _choose_teaching_tip_tail_position(self, target: QWidget, preferred):
        """根据目标控件在屏幕中的位置，尽量选择更不容易被遮挡的 tailPosition。

        约定：
        - tip 在目标下方  -> tailPosition.TOP
        - tip 在目标上方  -> tailPosition.BOTTOM
        - tip 在目标右侧  -> tailPosition.LEFT
        - tip 在目标左侧  -> tailPosition.RIGHT
        """
        try:
            from PySide6.QtCore import QPoint, QRect
            from PySide6.QtGui import QGuiApplication
        except Exception:
            return preferred

        def _to_global_rect(w: QWidget):
            try:
                p = w.mapToGlobal(QPoint(0, 0))
                return QRect(p, w.size())
            except Exception:
                return None

        try:
            rect = _to_global_rect(target)
            if rect is None:
                return preferred
            screen = QGuiApplication.screenAt(rect.center())
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            if screen is None:
                return preferred
            avail = screen.availableGeometry()

            above = rect.top() - avail.top()
            below = avail.bottom() - rect.bottom()
            left = rect.left() - avail.left()
            right = avail.right() - rect.right()

            # 粗略估计 TeachingTip 高度（含按钮），用于决定上下翻转
            min_space = 190

            # 先尊重 preferred
            try:
                if preferred == TeachingTipTailPosition.TOP and below >= min_space:
                    return TeachingTipTailPosition.TOP
                if preferred == TeachingTipTailPosition.BOTTOM and above >= min_space:
                    return TeachingTipTailPosition.BOTTOM
                if preferred == TeachingTipTailPosition.LEFT and right >= 260:
                    return TeachingTipTailPosition.LEFT
                if preferred == TeachingTipTailPosition.RIGHT and left >= 260:
                    return TeachingTipTailPosition.RIGHT
            except Exception:
                pass

            # 再做自适应选择
            best = max(
                [
                    (below, TeachingTipTailPosition.TOP),
                    (above, TeachingTipTailPosition.BOTTOM),
                    (right, TeachingTipTailPosition.LEFT),
                    (left, TeachingTipTailPosition.RIGHT),
                ],
                key=lambda x: x[0],
            )[1]
            return best
        except Exception:
            return preferred


    def _close_current_teaching_tip(self):
        tip = getattr(self, "_quick_guide_teaching_tip", None)
        if tip is None:
            return
        try:
            tip.close()
        except Exception:
            pass
        try:
            tip.deleteLater()
        except Exception:
            pass
        self._quick_guide_teaching_tip = None


    def _add_teaching_tip_footer_buttons(self, view: QWidget, step_index: int, total: int):
        """为 TeachingTip 追加底部按钮（上一步/结束指引/下一步/完成）。

        备注：不同版本 qfluentwidgets 的 TeachingTip.view 结构略有差异，这里尽量用最稳妥的方式：
        - view.layout() 存在则直接 addWidget
        - 不存在则创建一个 QVBoxLayout
        """
        # 目标：尽量复刻你之前的布局结构（host + QHBoxLayout + addStretch + view.addWidget(host)）。
        # 同时通过 layout 的 ContentsMargins 提供“留白”，避免按钮贴边。
        try:
            from PySide6.QtWidgets import QHBoxLayout
        except Exception:
            return

        # 清理旧 footer（防止重复添加）
        try:
            old = view.findChild(QWidget, "quickGuideFooterHost")
            if old is not None:
                old.setParent(None)
                old.deleteLater()
        except Exception:
            pass

        try:
            host = QWidget(view)
            host.setObjectName("quickGuideFooterHost")

            layout = QHBoxLayout(host)
            # 关键：通过 margins 让按钮不要贴着 TeachingTip 边缘
            layout.setContentsMargins(12, 10, 12, 12)
            layout.setSpacing(12)

            prev_btn = PushButton("上一步", host)
            prev_btn.setMinimumHeight(32)
            try:
                prev_btn.setEnabled(int(step_index) > 0)
            except Exception:
                pass
            try:
                prev_btn.clicked.connect(lambda: self._on_teaching_tip_prev(int(step_index)))
            except Exception:
                pass

            is_last = int(step_index) >= (int(total) - 1)

            if not is_last:
                next_btn = PrimaryPushButton("下一步", host)
                end_btn = PushButton("结束指引", host)

                next_btn.setMinimumHeight(32)
                end_btn.setMinimumHeight(32)

                try:
                    next_btn.clicked.connect(lambda: self._on_teaching_tip_next(int(step_index)))
                except Exception:
                    pass
                try:
                    end_btn.clicked.connect(self._on_teaching_tip_skip)
                except Exception:
                    pass

                layout.addWidget(prev_btn)
                layout.addStretch(1)
                layout.addWidget(next_btn)
                layout.addWidget(end_btn)
            else:
                finish_btn = PrimaryPushButton("恭喜完成指引！快去上手实操吧~", host)
                finish_btn.setMinimumHeight(32)
                try:
                    finish_btn.clicked.connect(self._on_teaching_tip_finish)
                except Exception:
                    pass

                layout.addWidget(prev_btn)
                layout.addStretch(1)
                layout.addWidget(finish_btn)

            # TeachingTipView.addWidget 存在于 qfluentwidgets 1.10.5
            try:
                view.addWidget(host)  # type: ignore[attr-defined]
            except Exception:
                # 兜底：如果没有 addWidget，就挂到 view.layout() 里
                try:
                    lay = view.layout()
                    if lay is not None:
                        lay.addWidget(host)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            view.adjustSize()
        except Exception:
            pass


    def _on_teaching_tip_prev(self, current_index: int):
        prev_idx = int(current_index) - 1
        if prev_idx < 0:
            return
        self._close_current_teaching_tip()
        QTimer.singleShot(80, lambda: self._run_quick_guide_step_teaching_tip(prev_idx))


    def _get_quick_guide_steps(self):
        return [
            (
                "项目切换\n",
                "📁 AI语音支持多项目：通过顶部 Tab 在不同项目之间切换。\n"
                "每个项目的角色、历史记录与输出目录都是相互隔离的。",
                lambda: getattr(self, "_ai_voice_tab_bar", None),
                TeachingTipTailPosition.TOP,
            ),
            (
                "模型准备与选择\n",
                "🧠 点击“使用本地模型”进入弹窗：先下载依赖/模型文件，再点击“加载模型”加载到显存。\n"
                "模型加载完成后，“模型选择”区域会显示“正在使用本地模型...”，并可点击查看诊断。",
                lambda: getattr(self, "model_control_panel_card", None)
                or getattr(self, "use_local_model_btn", None)
                or getattr(self, "download_btn", None),
                TeachingTipTailPosition.TOP,
            ),
            (
                "角色列表\n",
                "👤 在这里选择/新增角色。也可以从 Wwise 导入角色；必要时可批量删除清理。\n"
                "每个角色通常对应一套参考音频与风格配置。",
                lambda: getattr(self, "character_list_widget", None),
                TeachingTipTailPosition.LEFT,
            ),
            (
                "参考音频\n",
                "🎧 在此导入/拖拽参考音频，用于复刻音色与风格。\n"
                "导入后可直接试听，必要时可清空并重新导入。",
                lambda: getattr(self, "ref_player_widget", None),
                TeachingTipTailPosition.TOP,
            ),
            (
                "合成文本\n",
                "✍️ 输入要合成的内容，然后点击“生成音频”。支持 Alt+Enter 快捷键生成。",
                lambda: getattr(self, "text_edit", None),
                TeachingTipTailPosition.TOP,
            ),
            (
                "情感与风格\n",
                "🎛️ 可选择“与参考相同”或“使用情感向量控制”。使用向量控制时可通过滑块调节情绪与风格。",
                lambda: getattr(self, "emotion_control_panel_card", None) or getattr(self, "emo_mode_same", None),
                TeachingTipTailPosition.TOP,
            ),
            (
                "生成结果与历史\n",
                "🔊 生成完成后右侧展示 3 个候选样本，可播放/保存。\n"
                "你也可以打开历史记录窗口，批量回放与导出过往结果。",
                lambda: getattr(self, "_output_stack_host", None),
                TeachingTipTailPosition.RIGHT,
            ),
        ]


    def _run_quick_guide_step_teaching_tip(self, step_index: int):
        """TeachingTip 版本的引导。无法锚定/异常时回退到模态弹窗版本。"""
        steps = self._get_quick_guide_steps()
        total = len(steps)
        if step_index < 0 or step_index >= total:
            self._close_current_teaching_tip()
            self._teardown_teaching_tip_modal_blocker()
            return

        step_title, step_desc, focus_getter, tail_pos = steps[step_index]

        try:
            target = focus_getter() if callable(focus_getter) else None
        except Exception:
            target = None

        if target is None:
            target = self._get_quick_guide_fallback_target()
        if target is None:
            # 没有任何可用锚点时，直接结束（不回退旧式弹窗）
            self._close_current_teaching_tip()
            self._teardown_teaching_tip_modal_blocker()
            return

        try:
            if hasattr(target, "isVisible") and (not target.isVisible()):
                # 不可见时很难锚定：改用稳定锚点，保证 TeachingTip 显示
                fallback = self._get_quick_guide_fallback_target()
                if fallback is not None:
                    target = fallback
                else:
                    self._close_current_teaching_tip()
                    self._teardown_teaching_tip_modal_blocker()
                    return
        except Exception:
            pass

        # 尽量把焦点给到对应区域（非强制）
        try:
            target.setFocus()
        except Exception:
            pass

        try:
            # 让 TeachingTip 流程表现为“模态”：阻断背景操作
            self._ensure_teaching_tip_modal_blocker()
            self._update_teaching_tip_spotlight(target)
            self._close_current_teaching_tip()
            tip_title = f"快速指引（{step_index + 1}/{total}）·{step_title}"
            # 根据屏幕可用空间做 tailPosition 自适应，尽量避免被遮挡
            try:
                tail_pos = self._choose_teaching_tip_tail_position(target, tail_pos)
            except Exception:
                pass

            tip = TeachingTip.create(
                target=target,
                title=tip_title,
                content=step_desc,
                icon=None,
                image=None,
                isClosable=False,
                duration=-1,
                tailPosition=tail_pos,
                parent=self._main_window,
                isDeleteOnClose=True,
            )
            self._quick_guide_teaching_tip = tip

            # 某些版本的 qfluentwidgets 下 create() 不一定立即 show
            try:
                tip.show()
            except Exception:
                pass

            # 尝试设置窗口模态（有些平台/窗口旗标下可能不生效，但 overlay 会生效）
            try:
                tip.setWindowModality(Qt.WindowModality.ApplicationModal)
            except Exception:
                pass

            # 确保 TeachingTip 在拦截层之上
            try:
                tip.raise_()
                tip.activateWindow()
            except Exception:
                pass

            # 由于 tip.raise_() 会改变 Z 序，这里再把 overlay raise 到下方一次，并刷新 spotlight
            try:
                overlay = getattr(self, "_quick_guide_modal_overlay", None)
                if overlay is not None:
                    overlay.raise_()
                    tip.raise_()
                self._update_teaching_tip_spotlight(target)
            except Exception:
                pass

            view = getattr(tip, "view", None)
            if view is None:
                raise RuntimeError("TeachingTip.view 不可用")

            # 提升可读性：标题更大加粗；标题/正文间隔一行
            try:
                view.setStyleSheet(
                    "QLabel#titleLabel{font-size: 13pt; font-weight: 600;}"
                    "QLabel#contentLabel{font-size: 12pt; margin-top: 8px;}"
                )
            except Exception:
                pass

            # 解决越界：启用换行 + 限制最大宽度
            try:
                self._configure_teaching_tip_view_for_wrapping(tip, view)
            except Exception:
                pass

            # 底部按钮（可见）
            self._add_teaching_tip_footer_buttons(view, step_index, total)

        except Exception:
            self._close_current_teaching_tip()
            self._teardown_teaching_tip_modal_blocker()
            return


    def _on_teaching_tip_next(self, current_index: int):
        steps = self._get_quick_guide_steps()
        total = len(steps)
        next_idx = current_index + 1
        self._close_current_teaching_tip()
        if next_idx >= total:
            self._teardown_teaching_tip_modal_blocker()
            return
        QTimer.singleShot(80, lambda: self._run_quick_guide_step_teaching_tip(next_idx))


    def _on_teaching_tip_skip(self):
        self._close_current_teaching_tip()
        self._teardown_teaching_tip_modal_blocker()


    def _on_teaching_tip_finish(self):
        self._close_current_teaching_tip()
        self._teardown_teaching_tip_modal_blocker()


    def _on_use_local_model_clicked(self):
        """打开“使用本地模型”弹窗，并在打开时触发一次环境检测（仅更新状态）。"""
        try:
            audiobox_root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
            save_dir = os.path.join(audiobox_root, "checkpoints")
            self._pending_save_dir = save_dir

            dlg = self._ensure_local_model_dialog()
            if dlg is None:
                return

            # 每次打开都刷新智能推荐文案/默认值（仅在用户未保存偏好时自动应用）
            try:
                self._apply_fp16_default(auto_only=True)
            except Exception:
                pass

            # 先做一次快速检查，确保弹窗一打开按钮状态就正确
            try:
                self._check_env_and_model()
            except Exception:
                pass

            # 触发一次完整依赖检查（不弹安装对话框、不自动下载）
            try:
                self._start_async_env_check(
                    save_dir,
                    show_install_dialog_on_missing=False,
                    on_ready="none",
                )
            except Exception:
                pass

            dlg.exec()
        except Exception:
            pass


    def _on_use_online_model_clicked(self):
        """打开“使用线上模型”弹窗（占位，后续实现 API 管理/模型选择）。"""
        try:
            dlg = OnlineModelDialog(self._main_window)
            dlg.exec()
        except Exception:
            pass


