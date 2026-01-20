"""Wwise角色导入结果对话框

显示从Wwise项目导入角色的结果统计
"""

from PySide6.QtWidgets import QVBoxLayout
from qfluentwidgets import BodyLabel, MessageBoxBase, SubtitleLabel


class ImportResultDialog(MessageBoxBase):
    """导入结果对话框"""

    def __init__(self, parent=None, imported: int = 0, skipped: int = 0, failed: int = 0):
        """初始化对话框

        Args:
            parent: 父窗口
            imported: 成功导入的角色数
            skipped: 跳过的角色数（已存在）
            failed: 失败的角色数
        """

        super().__init__(parent)

        self._imported = imported
        self._skipped = skipped
        self._failed = failed

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 标题
        title_label = SubtitleLabel("导入完成", self)
        self.viewLayout.addWidget(title_label)

        # 结果统计
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(8)
        stats_layout.setContentsMargins(0, 16, 0, 16)

        if self._imported > 0:
            imported_label = BodyLabel(f"✓ 成功导入 {self._imported} 个角色", self)
            imported_label.setStyleSheet("color: #10b981;")  # 绿色
            stats_layout.addWidget(imported_label)

        if self._skipped > 0:
            skipped_label = BodyLabel(f"⊘ 跳过 {self._skipped} 个已存在的角色", self)
            skipped_label.setStyleSheet("color: #f59e0b;")  # 橙色
            stats_layout.addWidget(skipped_label)

        if self._failed > 0:
            failed_label = BodyLabel(f"✗ 导入失败 {self._failed} 个角色（超出上限或无效名称）", self)
            failed_label.setStyleSheet("color: #ef4444;")  # 红色
            stats_layout.addWidget(failed_label)

        # 如果全部失败或跳过，显示提示
        if self._imported == 0:
            if self._skipped > 0 and self._failed == 0:
                hint_label = BodyLabel("所有角色都已存在，无需导入。", self)
            elif self._failed > 0 and self._skipped == 0:
                hint_label = BodyLabel("导入失败，请检查Wwise项目配置或角色数量限制。", self)
            else:
                hint_label = BodyLabel("未导入任何角色。", self)
            hint_label.setStyleSheet("color: #6b7280; font-size: 12px;")
            stats_layout.addWidget(hint_label)

        self.viewLayout.addLayout(stats_layout)

        # 设置对话框尺寸
        self.widget.setMinimumWidth(360)

        # 设置按钮文本
        self.yesButton.setText("确定")
        self.cancelButton.hide()  # 隐藏取消按钮
