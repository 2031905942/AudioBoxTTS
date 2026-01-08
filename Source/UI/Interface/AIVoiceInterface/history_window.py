import os
from collections import defaultdict
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ScrollArea,
    StrongBodyLabel,
    FluentIcon,
)

from Source.UI.Interface.AIVoiceInterface.audio_player_widget import ResultAudioPlayerWidget
from Source.Utility.tts_history_utility import tts_history_store, _format_dt


class AIVoiceHistoryWindow(QWidget):
    """Non-modal history window for recent generated samples of the selected character."""

    def __init__(
        self,
        parent: QWidget,
        download_callback: Callable[[str], None],
    ):
        super().__init__(parent)
        self.setWindowTitle("历史记录")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(860, 720)

        self._download_callback = download_callback

        self._character_id: str = ""
        self._character_name: str = ""

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        self._title = StrongBodyLabel("历史记录", self)
        root_layout.addWidget(self._title)

        self._scroll = ScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

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
        self.reload()

    def reload(self):
        """Reload UI from temp_output history index."""
        self._clear_list()

        if not self._character_id:
            self._add_empty("未选择角色")
            return

        entries = tts_history_store.load_entries(self._character_id, self._character_name, limit=50)
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
        layout = self._list_layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                try:
                    w.deleteLater()
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
        header_layout.addWidget(t)

        ts = _format_dt(int(group_time_ms or 0))
        header_layout.addWidget(CaptionLabel("生成时间：" + (ts or ""), header))
        card_layout.addWidget(header)

        # samples
        for i, e in enumerate(sorted(rows, key=lambda x: int(x.get("created_at_ms", 0) or 0), reverse=False)):
            wav = str(e.get("wav_path", ""))
            if not wav or not os.path.exists(wav):
                continue
            w = ResultAudioPlayerWidget(f"样本 {i + 1}", card)
            w.set_audio_path(wav)
            w.add_tool_button(
                # keep consistent with result area
                FluentIcon.DOWNLOAD,
                "保存音频",
                (lambda _=False, p=wav: self._download_callback(p)),
            )
            card_layout.addWidget(w)

        self._list_layout.addWidget(card)
