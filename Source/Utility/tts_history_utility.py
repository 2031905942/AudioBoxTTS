import json
import hashlib
import os
import re
import shutil
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


def _sanitize_project_dir_name(name: str) -> str:
    """Make a filesystem-safe project folder name.

    Project folder should be more readable than role folder:
    - keep '-' and '_' and Chinese characters
    - replace whitespace with '-'
    """
    if not name:
        return "project"
    name = str(name).strip()
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", "-", name)
    name = name.strip("._ -")
    return name or "project"


def _short_hash(text: str, length: int = 8) -> str:
    """Stable short hash for uniqueness suffix."""
    try:
        h = hashlib.sha1(str(text).encode("utf-8"), usedforsecurity=False).hexdigest()
    except TypeError:
        # Python <3.9 compatibility for usedforsecurity
        h = hashlib.sha1(str(text).encode("utf-8")).hexdigest()
    return h[: max(4, int(length))]


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

    PROJECT_ID_MARKER = ".project_id"

    def __init__(
        self,
        base_dir: Optional[str] = None,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ):
        """
        初始化历史记录存储

        Args:
            base_dir: 基础目录，默认为 temp_output
            project_id: 项目ID，有值时按项目隔离存储到 temp_output/<项目名>/
            project_name: 项目名称（用于生成更易读的项目目录名）
        """
        default_base = base_dir or os.path.join(os.getcwd(), "temp_output")
        self._project_id = project_id
        self._project_name = project_name

        if project_id:
            self._base_dir = self._resolve_project_base_dir(default_base, project_id, project_name)
        else:
            self._base_dir = default_base

    def _marker_path(self, project_dir: str) -> str:
        return os.path.join(project_dir, self.PROJECT_ID_MARKER)

    def _read_marker(self, project_dir: str) -> str:
        p = self._marker_path(project_dir)
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return str(f.read() or "").strip()
        except Exception:
            return ""
        return ""

    def _ensure_marker(self):
        if not self._project_id:
            return
        try:
            os.makedirs(self._base_dir, exist_ok=True)
        except Exception:
            return

        p = self._marker_path(self._base_dir)
        try:
            if os.path.exists(p):
                return
            with open(p, "w", encoding="utf-8") as f:
                f.write(str(self._project_id))
        except Exception:
            pass

    def _find_existing_project_dir(self, default_base: str, project_id: str) -> str:
        """Find an existing project directory by marker (to preserve history on renames)."""
        try:
            if not os.path.isdir(default_base):
                return ""
            for name in os.listdir(default_base):
                if self._is_reserved_dir_name(name):
                    continue
                candidate = os.path.join(default_base, name)
                if not os.path.isdir(candidate):
                    continue
                if str(self._read_marker(candidate)) == str(project_id):
                    return candidate
        except Exception:
            return ""
        return ""

    def _resolve_project_base_dir(self, default_base: str, project_id: str, project_name: Optional[str]) -> str:
        """Resolve per-project root dir under temp_output using human-readable name.

        Strategy:
        1) If an existing folder contains marker for this project_id, reuse it.
        2) Otherwise, use sanitized project_name.
        3) If name conflicts, append a stable short hash suffix.
        """

        existing = self._find_existing_project_dir(default_base, project_id)
        desired = _sanitize_project_dir_name(project_name or "")
        if self._is_reserved_dir_name(desired):
            desired = "project"

        if existing:
            # If name changed, try to rename to desired (best-effort, no hard failure).
            try:
                current_name = os.path.basename(existing)
                if desired and current_name != desired:
                    target = os.path.join(default_base, desired)
                    if os.path.abspath(target) != os.path.abspath(existing):
                        if not os.path.exists(target):
                            os.rename(existing, target)
                            return target
                        # Conflict: append hash
                        target = os.path.join(default_base, f"{desired}-{_short_hash(project_id)}")
                        if not os.path.exists(target):
                            os.rename(existing, target)
                            return target
            except Exception:
                pass
            return existing

        base_name = desired or "project"
        candidate = os.path.join(default_base, base_name)
        marker = self._marker_path(candidate)
        if not os.path.exists(candidate):
            return candidate

        # If folder exists but belongs to same project, reuse it.
        try:
            if os.path.exists(marker) and str(self._read_marker(candidate)) == str(project_id):
                return candidate
        except Exception:
            pass

        # Conflict: deterministic suffix
        suffix = _short_hash(project_id)
        candidate2 = os.path.join(default_base, f"{base_name}-{suffix}")
        if not os.path.exists(candidate2):
            return candidate2

        # Extremely unlikely: keep adding numeric suffix.
        for i in range(2, 1000):
            cand = os.path.join(default_base, f"{base_name}-{suffix}-{i}")
            if not os.path.exists(cand):
                return cand
            try:
                if os.path.exists(self._marker_path(cand)) and str(self._read_marker(cand)) == str(project_id):
                    return cand
            except Exception:
                continue
        return candidate2

    @staticmethod
    def create_for_project(
        project_id: str,
        project_name: Optional[str] = None,
        base_dir: Optional[str] = None,
    ) -> "TTSHistoryStore":
        """为指定项目创建历史记录存储"""
        return TTSHistoryStore(base_dir=base_dir, project_id=project_id, project_name=project_name)

    @property
    def base_dir(self) -> str:
        return self._base_dir

    @property
    def project_id(self) -> Optional[str]:
        return self._project_id

    @property
    def project_name(self) -> Optional[str]:
        return self._project_name

    def set_project_name(self, project_name: Optional[str]):
        """更新项目名（用于项目重命名后写入到新的更易读目录）。"""
        if not self._project_id:
            self._project_name = project_name
            return
        default_base = os.path.dirname(self._base_dir)
        self._project_name = project_name
        self._base_dir = self._resolve_project_base_dir(default_base, str(self._project_id), project_name)

    def get_character_dir(self, character_id: str, character_name: str) -> str:
        # New rule: folder name is only the (sanitized) nickname.
        safe_name = _sanitize_component(character_name)
        return os.path.join(self.base_dir, safe_name)

    def resolve_existing_character_dir(self, character_id: str, character_name: str) -> str:
        """返回该角色目录（当前命名规则下）。"""
        return self.get_character_dir(character_id, character_name)

    @staticmethod
    def _is_reserved_dir_name(name: str) -> bool:
        # temp_output/logs is used by the app; never treat it as a character folder.
        return str(name or "").strip().lower() in {"logs"}

    @staticmethod
    def _pick_most_recent_dir(dirs: List[str]) -> str:
        if not dirs:
            return ""
        try:
            return max(dirs, key=lambda p: os.path.getmtime(p))
        except Exception:
            return dirs[0]

    @staticmethod
    def _iter_wavs(folder: str) -> List[str]:
        if not folder or not os.path.isdir(folder):
            return []
        out: List[str] = []
        try:
            for fn in os.listdir(folder):
                if fn.lower().endswith(".wav"):
                    out.append(os.path.join(folder, fn))
        except Exception:
            return []
        return out

    @staticmethod
    def _extract_seq_from_filename(filename: str) -> Optional[int]:
        if not filename:
            return None
        m = re.search(r"(\d+)(?=\.wav$)", filename, flags=re.IGNORECASE)
        if not m:
            return None
        try:
            return int(m.group(1))
        except Exception:
            return None

    def _rewrite_index_keep_existing(
        self,
        index_path: str,
        *,
        character_id: str,
        character_name: str,
        path_map: Optional[Dict[str, str]] = None,
        keep_limit: int = 50,
    ) -> int:
        """压缩/修正 index：

        - 只保留 wav 文件仍存在的行
        - 可选应用 path_map（旧绝对路径 -> 新绝对路径）
        - 更新 character_name
        - 最多保留 keep_limit 条（按 created_at_ms 降序）

        返回：最终写回的条数
        """
        if not index_path or not os.path.exists(index_path):
            return 0

        rows = self._read_index_lines(index_path)
        fixed: List[Dict[str, Any]] = []

        for r in rows:
            try:
                if str(r.get("character_id", "")) != str(character_id):
                    continue

                wav = str(r.get("wav_path", ""))
                if path_map and wav in path_map:
                    wav = str(path_map[wav])

                if not wav or (not os.path.exists(wav)):
                    continue

                r["character_name"] = str(character_name)
                r["wav_path"] = os.path.abspath(wav)
                fixed.append(r)
            except Exception:
                continue

        fixed.sort(key=lambda x: int(x.get("created_at_ms", 0) or 0), reverse=True)
        if keep_limit and len(fixed) > int(keep_limit):
            fixed = fixed[: int(keep_limit)]

        try:
            with open(index_path, "w", encoding="utf-8") as f:
                for r in fixed:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        except Exception:
            return 0

        return len(fixed)

    def delete_character_cache(self, character_id: str, character_name: str = "") -> int:
        """删除该角色在 temp_output 下的整个 <昵称> 文件夹。

        返回：
        - 1: 成功删除
        - 0: 目录不存在/无需删除
        - -1: 删除失败（Windows 文件占用等）
        """
        safe_name = _sanitize_component(character_name) if character_name else ""
        if not safe_name or self._is_reserved_dir_name(safe_name):
            return 0

        desired = os.path.join(self.base_dir, safe_name)
        if not os.path.isdir(desired):
            return 0
        try:
            shutil.rmtree(desired)
            return 1
        except Exception:
            # Windows 文件占用导致删除失败时，上层会提示用户停止播放后重试
            return -1

    def rename_character_cache(self, character_id: str, old_name: str, new_name: str) -> bool:
        """角色改名时，同步更新 temp_output 下目录名与 wav 文件名前缀，并修正 history.jsonl。"""
        new_safe = _sanitize_component(new_name)
        old_safe = _sanitize_component(old_name)

        if (not new_safe) or self._is_reserved_dir_name(new_safe):
            return False

        os.makedirs(self.base_dir, exist_ok=True)

        old_dir = os.path.join(self.base_dir, old_safe)
        if not os.path.isdir(old_dir):
            return False
        target_dir = os.path.join(self.base_dir, new_safe)
        if os.path.exists(target_dir):
            return False
        try:
            os.rename(old_dir, target_dir)
        except Exception:
            return False

        # 统一把 target_dir 内所有 wav 重命名为新前缀
        path_map: Dict[str, str] = {}
        for wav in self._iter_wavs(target_dir):
            try:
                # 注意：index 内记录的是“改名之前”的绝对路径（旧目录 + 旧文件名）。
                # 这里构造 old_abs 用于映射更新。
                old_abs = os.path.abspath(os.path.join(old_dir, os.path.basename(wav)))
                seq = self._extract_seq_from_filename(os.path.basename(wav))
                if seq is None:
                    continue
                new_abs = os.path.join(target_dir, f"{new_safe}_{seq}.wav")
                if os.path.abspath(old_abs) == os.path.abspath(new_abs):
                    continue
                if os.path.exists(new_abs):
                    j = seq
                    while os.path.exists(new_abs) and j < seq + 10000:
                        j += 1
                        new_abs = os.path.join(target_dir, f"{new_safe}_{j}.wav")
                # wav 当前实际在 target_dir 下，但文件名仍是旧名；用当前路径执行 rename。
                os.replace(os.path.abspath(wav), new_abs)
                path_map[old_abs] = os.path.abspath(new_abs)
            except Exception:
                continue

        # 修正/压缩 index
        try:
            index_path = os.path.join(target_dir, self.INDEX_FILENAME)
            self._rewrite_index_keep_existing(
                index_path,
                character_id=str(character_id),
                character_name=str(new_name),
                path_map=path_map,
                keep_limit=50,
            )
        except Exception:
            pass

        return True

    def prune_character_cache(self, character_id: str, character_name: str, max_files: int = 50) -> int:
        """将该角色目录内 wav 文件数量裁剪到最多 max_files 个。

        按 mtime 从旧到新删除最早的；同时压缩 history.jsonl 以移除失效条目。

        返回：删除的 wav 数量
        """
        max_files = int(max(0, max_files))

        # Only prune existing folder; never create empty folders here.
        d = self.get_character_dir(character_id, character_name)
        if not d or (not os.path.isdir(d)):
            return 0

        wavs = self._iter_wavs(d)
        if max_files <= 0:
            removed = 0
            for p in wavs:
                try:
                    os.remove(p)
                    removed += 1
                except Exception:
                    pass
            try:
                idx = os.path.join(d, self.INDEX_FILENAME)
                if os.path.exists(idx):
                    os.remove(idx)
            except Exception:
                pass
            return removed

        # 删除超出的最早文件
        removed = 0
        try:
            wavs.sort(key=lambda p: os.path.getmtime(p))
        except Exception:
            pass

        if len(wavs) > max_files:
            for p in wavs[: len(wavs) - max_files]:
                try:
                    os.remove(p)
                    removed += 1
                except Exception:
                    pass

        # 压缩 index（只保留仍存在的，并最多 max_files 条）
        try:
            idx = os.path.join(d, self.INDEX_FILENAME)
            self._rewrite_index_keep_existing(
                idx,
                character_id=str(character_id),
                character_name=str(character_name),
                path_map=None,
                keep_limit=max_files,
            )
        except Exception:
            pass

        return removed

    def get_index_path(self, character_id: str, character_name: str) -> str:
        # For writing, always use the current naming rule folder.
        return os.path.join(self.get_character_dir(character_id, character_name), self.INDEX_FILENAME)

    def ensure_character_dir(self, character_id: str, character_name: str) -> str:
        # Ensure project folder exists and marker is written.
        try:
            self._ensure_marker()
        except Exception:
            pass

        safe_name = _sanitize_component(character_name)
        if self._is_reserved_dir_name(safe_name):
            # Avoid clobbering temp_output/logs.
            safe_name = "role"

        target = os.path.join(self.base_dir, safe_name)
        os.makedirs(target, exist_ok=True)
        return target

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

        # 每个角色目录最多保留 50 个 wav；超出删除最早生成的
        try:
            self.prune_character_cache(character_id, character_name, max_files=50)
        except Exception:
            pass

        return appended, group_time


# Singleton

tts_history_store = TTSHistoryStore()

__all__ = [
    "tts_history_store",
    "TTSHistoryStore",
    "_format_dt",
]
