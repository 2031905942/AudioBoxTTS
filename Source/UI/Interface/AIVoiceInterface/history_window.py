import os
import sys
from collections import defaultdict
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ScrollArea,
    StrongBodyLabel,
    FluentIcon,
    TransparentToolButton,
)

from Source.UI.Interface.AIVoiceInterface.audio_player_widget import ResultAudioPlayerWidget
from Source.Utility.tts_history_utility import TTSHistoryStore, tts_history_store, _format_dt


class AIVoiceHistoryWindow(QWidget):
    """Non-modal history window for recent generated samples of the selected character."""

    def __init__(
        self,
        parent: QWidget,
        download_callback: Callable[[str], None],
        history_store: TTSHistoryStore | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("历史记录")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(860, 720)

        self._download_callback = download_callback

        # 允许按项目注入；未提供时回退到全局 store（向后兼容）
        self._history_store: TTSHistoryStore = history_store or tts_history_store

        self._character_id: str = ""
        self._character_name: str = ""

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self._title = StrongBodyLabel("历史记录", header)
        header_layout.addWidget(self._title, 0)
        header_layout.addStretch(1)

        self._open_folder_btn = TransparentToolButton(FluentIcon.FOLDER, header)
        self._open_folder_btn.setToolTip("在文件资源管理器中打开当前角色语音文件夹")
        self._open_folder_btn.setFixedSize(32, 32)
        self._open_folder_btn.clicked.connect(self._open_current_character_folder)
        header_layout.addWidget(self._open_folder_btn, 0, Qt.AlignmentFlag.AlignRight)

        root_layout.addWidget(header)

        self._scroll = ScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # 隐藏将所有组包裹在一起的外框线
        try:
            self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        except Exception:
            pass
        try:
            self._scroll.setStyleSheet("QScrollArea{border: none; background: transparent;}")
        except Exception:
            pass

        host = QWidget(self._scroll)
        self._host = host
        self._list_layout = QVBoxLayout(host)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(10)
        self._list_layout.addStretch(1)

        self._scroll.setWidget(host)
        root_layout.addWidget(self._scroll, 1)

    def set_character(self, character_id: str, character_name: str):
        self._character_id = str(character_id or "")
        self._character_name = str(character_name or "")
        self._title.setText(f"历史记录 - {self._character_name}" if self._character_name else "历史记录")
        try:
            self._open_folder_btn.setEnabled(bool(self._character_id))
        except Exception:
            pass
        self.reload()

    def set_history_store(self, history_store: TTSHistoryStore | None):
        self._history_store = history_store or tts_history_store

    def _open_current_character_folder(self):
        if not self._character_id:
            return
        try:
            folder = self._history_store.get_character_dir(self._character_id, self._character_name)
        except Exception:
            folder = ""
        if not folder:
            return
        # 不要在这里创建空目录：避免“改名后出现空文件夹”的错觉
        if not os.path.isdir(folder):
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
                return
        except Exception:
            pass
        try:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl

            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        except Exception:
            pass

    def reload(self):
        """Reload UI from temp_output history index."""
        self._clear_list()

        if not self._character_id:
            self._add_empty("未选择角色")
            return

        # 打开历史时顺带裁剪缓存：每个角色最多保留 50 个 wav（按最早生成删除）
        try:
            self._history_store.prune_character_cache(self._character_id, self._character_name, max_files=50)
        except Exception:
            pass

        entries = self._history_store.load_entries(self._character_id, self._character_name, limit=50)
        if not entries:
            self._add_empty("暂无历史记录")
            return

        groups: Dict[str, List[dict]] = defaultdict(list)
        for e in entries:
            groups[str(e.get("group_id", ""))].append(e)

        group_rows = []
        for gid, rows in groups.items():
            rows.sort(key=lambda x: int(x.get("created_at_ms", 0) or 0))
            g_time = max((int(x.get("created_at_ms", 0) or 0) for x in rows), default=0)
            text = str(rows[-1].get("text", "") if rows else "")
            group_rows.append((g_time, gid, text, rows))

        group_rows.sort(key=lambda x: x[0], reverse=True)

        for g_time, gid, text, rows in group_rows:
            self._add_group(g_time, text, rows)

        self._list_layout.addStretch(1)

    def _clear_list(self):
        # 先释放所有播放器句柄，避免 Windows 下目录改名/删除失败
        try:
            self.release_all_media()
        except Exception:
            pass
        layout = self._list_layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                try:
                    w.deleteLater()
                except Exception:
                    pass

    def release_all_media(self):
        """释放历史窗口内所有播放器的媒体源（用于删除/改名文件夹前）。"""
        try:
            for w in self.findChildren(ResultAudioPlayerWidget):
                try:
                    if hasattr(w, "release_media"):
                        w.release_media()
                except Exception:
                    continue
        except Exception:
            pass

    def _add_empty(self, msg: str):
        card = CardWidget(self._host)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(6)
        lay.addWidget(BodyLabel(msg, card))
        self._list_layout.addWidget(card)

    def _add_group(self, group_time_ms: int, text: str, rows: List[dict]):
        card = CardWidget(self._host)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        header = QWidget(card)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        t = BodyLabel("合成文本：" + (text or ""), header)
        try:
            t.setWordWrap(True)
        except Exception:
            pass
        try:
            t.setStyleSheet("font-size: 12pt;")
        except Exception:
            pass
        header_layout.addWidget(t)

        ts = _format_dt(int(group_time_ms or 0))
        time_label = BodyLabel("生成时间：" + (ts or ""), header)
        try:
            time_label.setStyleSheet("font-size: 11pt;")
        except Exception:
            pass
        header_layout.addWidget(time_label)
        card_layout.addWidget(header)

        # samples
        for i, e in enumerate(sorted(rows, key=lambda x: int(x.get("created_at_ms", 0) or 0), reverse=False)):
            wav = str(e.get("wav_path", ""))
            if not wav or not os.path.exists(wav):
                continue
            # 标题会自动显示 wav 文件名
            w = ResultAudioPlayerWidget("音频", card)
            w.set_audio_path(wav)
            w.add_tool_button(
                # keep consistent with result area
                FluentIcon.DOWNLOAD,
                "保存音频",
                (lambda _=False, p=wav: self._download_callback(p)),
            )
            card_layout.addWidget(w)

        self._list_layout.addWidget(card)
