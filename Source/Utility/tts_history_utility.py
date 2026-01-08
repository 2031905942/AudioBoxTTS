import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def _sanitize_component(name: str) -> str:
    """Make a filesystem-safe component (folder/file stem)."""
    if not name:
        return "role"
    name = str(name).strip()
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", "_", name)
    name = name.strip("._ ")
    return name or "role"


def _format_dt(epoch_ms: int) -> str:
    try:
        dt = datetime.fromtimestamp(max(0, int(epoch_ms)) / 1000.0)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


@dataclass
class HistoryEntry:
    v: int
    character_id: str
    character_name: str
    group_id: str
    text: str
    wav_path: str
    created_at_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "v": int(self.v),
            "character_id": str(self.character_id),
            "character_name": str(self.character_name),
            "group_id": str(self.group_id),
            "text": str(self.text),
            "wav_path": str(self.wav_path),
            "created_at_ms": int(self.created_at_ms),
        }


class TTSHistoryStore:
    """Persist and query per-character synthesis history under temp_output."""

    INDEX_FILENAME = "history.jsonl"

    def __init__(self, base_dir: Optional[str] = None):
        self._base_dir = base_dir or os.path.join(os.getcwd(), "temp_output")

    @property
    def base_dir(self) -> str:
        return self._base_dir

    def get_character_dir(self, character_id: str, character_name: str) -> str:
        safe_name = _sanitize_component(character_name)
        suffix = (character_id or "")[:8] or "unknown"
        folder = f"{safe_name}_{suffix}"
        return os.path.join(self.base_dir, folder)

    def get_index_path(self, character_id: str, character_name: str) -> str:
        return os.path.join(self.get_character_dir(character_id, character_name), self.INDEX_FILENAME)

    def ensure_character_dir(self, character_id: str, character_name: str) -> str:
        d = self.get_character_dir(character_id, character_name)
        os.makedirs(d, exist_ok=True)
        return d

    def _read_index_lines(self, index_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(index_path):
            return []
        entries: List[Dict[str, Any]] = []
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            return []
        return entries

    def load_entries(self, character_id: str, character_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        index_path = self.get_index_path(character_id, character_name)
        rows = self._read_index_lines(index_path)

        # filter and keep only existing files
        out: List[Dict[str, Any]] = []
        for r in rows:
            try:
                if str(r.get("character_id", "")) != str(character_id):
                    continue
                wav = str(r.get("wav_path", ""))
                if not wav or not os.path.exists(wav):
                    continue
                out.append(r)
            except Exception:
                continue

        out.sort(key=lambda x: int(x.get("created_at_ms", 0) or 0), reverse=True)
        if limit and len(out) > int(limit):
            out = out[: int(limit)]
        return out

    def get_or_create_group_id(self, character_id: str, character_name: str, text: str) -> str:
        """Return last group_id if last group's text equals current text; otherwise create a new group_id."""
        index_path = self.get_index_path(character_id, character_name)
        rows = self._read_index_lines(index_path)
        last_text = None
        last_gid = None
        last_ts = -1
        for r in rows:
            try:
                if str(r.get("character_id", "")) != str(character_id):
                    continue
                ts = int(r.get("created_at_ms", 0) or 0)
                if ts >= last_ts:
                    last_ts = ts
                    last_text = str(r.get("text", ""))
                    last_gid = str(r.get("group_id", ""))
            except Exception:
                continue

        if (last_gid and isinstance(last_text, str) and last_text.strip() == str(text).strip()):
            return str(last_gid)

        return str(int(time.time() * 1000))

    def next_sequence(self, character_id: str, character_name: str) -> int:
        """Find the next sequence number for naming files."""
        d = self.ensure_character_dir(character_id, character_name)
        max_seq = 0
        try:
            for fn in os.listdir(d):
                if not fn.lower().endswith(".wav"):
                    continue
                m = re.search(r"(\d+)(?=\.wav$)", fn)
                if not m:
                    continue
                try:
                    max_seq = max(max_seq, int(m.group(1)))
                except Exception:
                    pass
        except Exception:
            pass
        return max_seq + 1

    def build_output_paths(self, character_id: str, character_name: str, count: int = 3) -> List[str]:
        d = self.ensure_character_dir(character_id, character_name)
        safe_name = _sanitize_component(character_name)
        start = self.next_sequence(character_id, character_name)
        paths = []
        for i in range(int(count)):
            seq = start + i
            paths.append(os.path.join(d, f"{safe_name}_{seq}.wav"))
        return paths

    def append_samples(
        self,
        character_id: str,
        character_name: str,
        group_id: str,
        text: str,
        wav_paths: List[str],
    ) -> Tuple[int, int]:
        """Append generated samples to history index.

        Returns: (appended_count, group_time_ms)
        """
        self.ensure_character_dir(character_id, character_name)
        index_path = self.get_index_path(character_id, character_name)

        appended = 0
        group_time = 0
        lines: List[str] = []
        for p in wav_paths:
            try:
                if not p or not os.path.exists(p):
                    continue
                created_ms = int(os.path.getmtime(p) * 1000)
                group_time = max(group_time, created_ms)
                e = HistoryEntry(
                    v=1,
                    character_id=str(character_id),
                    character_name=str(character_name),
                    group_id=str(group_id),
                    text=str(text),
                    wav_path=os.path.abspath(p),
                    created_at_ms=created_ms,
                )
                lines.append(json.dumps(e.to_dict(), ensure_ascii=False))
                appended += 1
            except Exception:
                continue

        if not lines:
            return 0, 0

        try:
            with open(index_path, "a", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")
        except Exception:
            return 0, 0

        return appended, group_time


# Singleton

tts_history_store = TTSHistoryStore()

__all__ = [
    "tts_history_store",
    "TTSHistoryStore",
    "_format_dt",
]
