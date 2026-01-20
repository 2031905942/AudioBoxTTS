"""
UI 遮罩层模块

包含拖拽遮罩层和模态输入拦截层。
"""
from typing import Optional

from PySide6.QtCore import Signal, Qt, QEvent, QRect
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon


class DragDropOverlay(QWidget):
    """全界面拖拽遮罩层。

    目的:
    - 拦截拖拽事件,避免输入框等子控件抢占 drop(把路径写进文本框)。
    - 在遮罩层上绘制橙色虚线框 + 图标 + 提示文本。
    """

    audio_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setVisible(False)
        # 透明背景,但仍然接收 drag/drop 事件
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    @staticmethod
    def _is_audio_url(event) -> Optional[str]:
        if not event.mimeData().hasUrls():
            return None
        urls = event.mimeData().urls()
        if not urls:
            return None
        file_path = urls[0].toLocalFile()
        if not file_path:
            return None
        if file_path.lower().endswith((".wav", ".mp3", ".flac", ".ogg")):
            return file_path
        return None

    def dragEnterEvent(self, event):
        file_path = self._is_audio_url(event)
        if file_path:
            event.acceptProposedAction()
            self.show()
            self.raise_()
            self.update()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        file_path = self._is_audio_url(event)
        if file_path:
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.hide()
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        file_path = self._is_audio_url(event)
        self.hide()
        self.update()
        if file_path:
            event.acceptProposedAction()
            self.audio_dropped.emit(file_path)
            return
        event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isVisible():
            return

        from PySide6.QtGui import QPainter, QPen, QColor, QFont

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 橙色虚线框
        pen = QPen(QColor("#ff6b00"), 3, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 107, 0, 20))
        rect = self.rect().adjusted(8, 8, -8, -8)
        painter.drawRoundedRect(rect, 12, 12)

        # 中心图标 + 文本
        icon_size = 44
        icon = None
        try:
            icon = FluentIcon.MUSIC.icon()
        except Exception:
            icon = None

        cx = self.rect().center().x()
        cy = self.rect().center().y()

        if icon is not None:
            pm = icon.pixmap(icon_size, icon_size)
            painter.drawPixmap(cx - icon_size // 2, cy - icon_size // 2 - 28, pm)

        painter.setPen(QColor("#ff6b00"))
        font = QFont()
        font.setPointSize(11)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(self.rect().adjusted(16, 0, -16, 0), Qt.AlignmentFlag.AlignCenter,
                         "拖拽音频文件到此处导入参考音频")

        painter.setPen(QColor(120, 120, 120))
        font2 = QFont()
        font2.setPointSize(9)
        font2.setBold(False)
        painter.setFont(font2)
        sub_rect = self.rect().adjusted(16, 28, -16, 0)
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, "支持 wav / mp3 / flac / ogg")


class _ModalInputBlockerOverlay(QWidget):
    """透明输入拦截层:用于让 TeachingTip 流程表现为"模态"。

    设计目标:
    - 不增加视觉元素(完全透明)
    - 阻断主窗口内除 TeachingTip 外的点击/键盘操作
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setVisible(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._spotlight_target: QWidget | None = None
        self._spotlight_rect = None
        self._spotlight_radius = 10
        self._spotlight_margin = 8

        try:
            parent.installEventFilter(self)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self.setGeometry(self.parentWidget().rect())
        except Exception:
            pass
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass
        try:
            self.setFocus()
        except Exception:
            pass

    def set_spotlight_target(self, target: QWidget | None, margin: int = 8, radius: int = 10):
        """设置需要高亮的目标区域(镂空显示)。"""
        self._spotlight_target = target
        self._spotlight_margin = int(margin)
        self._spotlight_radius = int(radius)
        self._recompute_spotlight_rect()
        self.update()

    def _recompute_spotlight_rect(self):
        if self._spotlight_target is None:
            self._spotlight_rect = None
            return
        try:
            # 目标控件的全局矩形映射到 overlay 坐标
            top_left = self._spotlight_target.mapToGlobal(self._spotlight_target.rect().topLeft())
            bottom_right = self._spotlight_target.mapToGlobal(self._spotlight_target.rect().bottomRight())
            local_tl = self.mapFromGlobal(top_left)
            local_br = self.mapFromGlobal(bottom_right)
            r = QRect(local_tl, local_br).normalized()
            r = r.adjusted(-self._spotlight_margin, -self._spotlight_margin, self._spotlight_margin, self._spotlight_margin)
            self._spotlight_rect = r
        except Exception:
            self._spotlight_rect = None

    def eventFilter(self, obj, event):
        if obj == self.parentWidget():
            try:
                if event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
                    self.setGeometry(self.parentWidget().rect())
                    self._recompute_spotlight_rect()
            except Exception:
                pass
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        super().paintEvent(event)

        from PySide6.QtGui import QPainter, QColor, QPainterPath

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 说明:之前用 CompositionMode_Clear 在部分 Windows/显卡组合下会表现为"白板遮挡",
        # 看不到高亮区域内容。这里改为只绘制"暗层路径减去高亮区域",避免依赖 Clear 合成模式。
        try:
            if self._spotlight_rect is None:
                painter.fillRect(self.rect(), QColor(0, 0, 0, 140))
                return

            dim_path = QPainterPath()
            dim_path.addRect(self.rect())

            hole = QPainterPath()
            hole.addRoundedRect(self._spotlight_rect, self._spotlight_radius, self._spotlight_radius)

            dim_path = dim_path.subtracted(hole)
            painter.fillPath(dim_path, QColor(0, 0, 0, 140))
        except Exception:
            # 最差情况下也保证是"整体压暗"
            painter.fillRect(self.rect(), QColor(0, 0, 0, 140))

    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        event.accept()

    def keyPressEvent(self, event):
        event.accept()

    def keyReleaseEvent(self, event):
        event.accept()
