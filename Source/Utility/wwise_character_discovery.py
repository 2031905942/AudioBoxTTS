"""Wwise WorkUnit 发现模块

目标：用于 AI语音 角色导入。

设计原则：
- 不从 Sound/SFX 级别导入（会爆炸式增长、且大量不是“角色”）
- 以 Actor-Mixer Hierarchy 下的 WorkUnit 作为候选；默认仅返回“叶子 WorkUnit”（没有子 WorkUnit 的那批）
- 同时为每个 WorkUnit 计算一个可用的参考 Voice 路径（仅 Voices；不使用 SFX 作为参考音色）
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Optional

from Source.Utility.config_utility import config_utility, ProjectData


ACTOR_MIXER_HIERARCHY = "Actor-Mixer Hierarchy"


@dataclass(frozen=True)
class WorkUnitCandidate:
    """WorkUnit 导入候选"""

    work_unit_id: str
    name: str
    wwu_file_path: str
    parent_work_unit_id: str | None = None
    full_path: str | None = None
    reference_voice_path: str | None = None
    voice_count: int = 0


class ScanCancelled(Exception):
    """用于中断大项目扫描的取消异常。"""


def _safe_text(elem: ET.Element | None) -> str:
    if elem is None or elem.text is None:
        return ""
    return str(elem.text).strip()


def _parse_originals_dir_from_wproj(wwise_project_path: str) -> str:
    """读取 .wproj 里的 Originals 路径配置；取不到则回退为 'Originals'。"""
    try:
        tree = ET.parse(wwise_project_path)
        root = tree.getroot()
        misc = root.find("./ProjectInfo/Project/MiscSettings/MiscSettingEntry[@Name='Originals']")
        p = _safe_text(misc)
        return p if p else "Originals"
    except Exception:
        return "Originals"


def _get_cache_path() -> str:
    try:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    except Exception:
        repo_root = os.getcwd()
    return os.path.join(repo_root, "temp_output", ".wwise_workunit_cache.json")


def _load_cache() -> dict:
    path = _get_cache_path()
    try:
        if not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    path = _get_cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except Exception:
        pass
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _candidate_to_dict(c: WorkUnitCandidate) -> dict:
    return {
        "work_unit_id": c.work_unit_id,
        "name": c.name,
        "wwu_file_path": c.wwu_file_path,
        "parent_work_unit_id": c.parent_work_unit_id,
        "full_path": c.full_path,
        "reference_voice_path": c.reference_voice_path,
        "voice_count": int(c.voice_count or 0),
    }


def _candidate_from_dict(d: dict) -> WorkUnitCandidate:
    return WorkUnitCandidate(
        work_unit_id=str(d.get("work_unit_id") or ""),
        name=str(d.get("name") or ""),
        wwu_file_path=str(d.get("wwu_file_path") or ""),
        parent_work_unit_id=str(d.get("parent_work_unit_id") or "") or None,
        full_path=str(d.get("full_path") or "") or None,
        reference_voice_path=str(d.get("reference_voice_path") or "") or None,
        voice_count=int(d.get("voice_count") or 0),
    )


def _find_wwu_files(actor_mixer_dir: str) -> list[str]:
    wwu_files: list[str] = []
    for root, _dirs, files in os.walk(actor_mixer_dir):
        for f in files:
            if f.lower().endswith(".wwu"):
                wwu_files.append(os.path.join(root, f))
    wwu_files.sort()
    return wwu_files


def _parse_wwu_work_unit_and_audio_pairs(
    wwu_file_path: str,
    *,
    wwise_project_dir: str,
    originals_dir: str,
) -> tuple[str | None, str | None, str | None, list[tuple[str, str]]]:
    """一次解析 .wwu：返回 (work_unit_id, name, parent_id, audio_pairs)。"""
    try:
        root = ET.parse(wwu_file_path).getroot()
    except Exception:
        return None, None, None, []

    work_unit = root.find(".//WorkUnit")
    if work_unit is None:
        return None, None, None, []

    work_unit_id = str(work_unit.attrib.get("ID") or "").strip() or None
    name = str(work_unit.attrib.get("Name") or "").strip() or None
    parent_id = str(work_unit.attrib.get("ParentDocumentID") or "").strip() or None

    results: list[tuple[str, str]] = []
    for audio_file_source in root.findall(".//AudioFileSource"):
        lang = _safe_text(audio_file_source.find("./Language"))
        rel = _safe_text(audio_file_source.find("./AudioFile"))
        if not rel:
            continue

        rel = rel.replace("\\", "/")
        if (lang or "").upper() == "SFX":
            abs_path = Path(wwise_project_dir) / originals_dir / "SFX" / rel
        else:
            abs_path = Path(wwise_project_dir) / originals_dir / "Voices" / (lang or "") / rel

        abs_path_str = os.path.normpath(str(abs_path))
        if os.path.isfile(abs_path_str):
            results.append((lang or "", abs_path_str))

    return work_unit_id, name, parent_id, results


def _collect_audio_paths_from_wwu(
    wwu_file_path: str,
    *,
    wwise_project_dir: str,
    originals_dir: str,
) -> list[tuple[str, str]]:
    """兼容旧逻辑：收集 (language, abs_wav_path) 列表。"""
    _wid, _name, _pid, pairs = _parse_wwu_work_unit_and_audio_pairs(
        wwu_file_path,
        wwise_project_dir=wwise_project_dir,
        originals_dir=originals_dir,
    )
    return pairs


def _pick_reference_voice(audio_pairs: list[tuple[str, str]]) -> str | None:
    """从候选音频中挑一条作为 reference Voice。

    规则：仅使用 Voices（language!=SFX），按文件大小取最大（更可能是完整句子）。
    """
    if not audio_pairs:
        return None

    def _size(p: str) -> int:
        try:
            return int(os.path.getsize(p))
        except Exception:
            return 0

    voices = [(lang, p) for (lang, p) in audio_pairs if (lang or "").upper() != "SFX"]
    if not voices:
        return None

    voices.sort(key=lambda x: (_size(x[1]), x[1]), reverse=True)
    return voices[0][1]


def _build_full_path(work_unit_id: str, id_to_candidate: dict[str, WorkUnitCandidate]) -> str | None:
    parts: list[str] = []
    cur = work_unit_id
    seen: set[str] = set()
    while cur and cur not in seen:
        seen.add(cur)
        c = id_to_candidate.get(cur)
        if c is None:
            break
        if c.name:
            parts.insert(0, c.name)
        cur = c.parent_work_unit_id or ""
    if not parts:
        return None
    return " / ".join(parts)


def discover_leaf_work_units_from_project(
    project_id: str,
    *,
    progress_cb=None,
    is_cancelled=None,
) -> list[WorkUnitCandidate]:
    """从项目的 Actor-Mixer Hierarchy 里发现“叶子 WorkUnit”候选。

    Args:
        project_id: 项目ID
        progress_cb: 进度回调 (current:int, total:int, text:str)
        is_cancelled: 取消检查回调 ()->bool
    """
    project_data = config_utility.get_project_data(project_id)
    if not project_data:
        raise ValueError(f"项目ID无效: {project_id}")

    wwise_project_path = project_data.get(ProjectData.WWISE_PROJECT_PATH)
    if not wwise_project_path:
        raise ValueError("项目未配置Wwise项目路径")

    if not os.path.exists(wwise_project_path):
        raise FileNotFoundError(f"Wwise项目文件不存在: {wwise_project_path}")

    wwise_project_dir = os.path.dirname(wwise_project_path)
    actor_mixer_dir = os.path.join(wwise_project_dir, ACTOR_MIXER_HIERARCHY)
    if not os.path.isdir(actor_mixer_dir):
        return []

    # 缓存：根据 wproj 与 Actor-Mixer 目录 mtime 判定是否可复用
    cache_key = f"{wwise_project_path}|{actor_mixer_dir}"
    try:
        wproj_mtime = os.path.getmtime(wwise_project_path)
    except Exception:
        wproj_mtime = 0.0
    try:
        actor_mixer_mtime = os.path.getmtime(actor_mixer_dir)
    except Exception:
        actor_mixer_mtime = 0.0

    cache = _load_cache()
    entry = cache.get(cache_key) if isinstance(cache, dict) else None
    if isinstance(entry, dict):
        try:
            if (
                float(entry.get("wproj_mtime", 0.0)) == float(wproj_mtime)
                and float(entry.get("actor_mixer_mtime", 0.0)) == float(actor_mixer_mtime)
            ):
                data = entry.get("candidates") or []
                if isinstance(data, list) and data:
                    try:
                        if callable(progress_cb):
                            progress_cb(1, 1, "已从缓存加载")
                    except Exception:
                        pass
                    return [_candidate_from_dict(d) for d in data]
        except Exception:
            pass

    originals_dir = _parse_originals_dir_from_wproj(wwise_project_path)

    raw: list[WorkUnitCandidate] = []
    id_to_wwu: dict[str, str] = {}
    parent_ids: set[str] = set()

    wwu_files = _find_wwu_files(actor_mixer_dir)
    total = len(wwu_files)
    for idx, wwu in enumerate(wwu_files):
        try:
            if callable(is_cancelled) and bool(is_cancelled()):
                raise ScanCancelled()
        except ScanCancelled:
            raise
        except Exception:
            pass

        try:
            if callable(progress_cb):
                progress_cb(int(idx), int(total), f"解析: {os.path.basename(wwu)}")
        except Exception:
            pass

        wid, name, parent_id, audio_pairs = _parse_wwu_work_unit_and_audio_pairs(
            wwu,
            wwise_project_dir=wwise_project_dir,
            originals_dir=originals_dir,
        )
        if not wid or not name:
            continue

        voice_pairs = [(lang, p) for (lang, p) in audio_pairs if (lang or "").upper() != "SFX"]

        cand = WorkUnitCandidate(
            work_unit_id=wid,
            name=name,
            wwu_file_path=wwu,
            parent_work_unit_id=parent_id,
            reference_voice_path=_pick_reference_voice(audio_pairs),
            voice_count=len(voice_pairs),
        )
        raw.append(cand)
        id_to_wwu[wid] = wwu
        if parent_id:
            parent_ids.add(parent_id)

    if not raw:
        return []

    id_to_candidate: dict[str, WorkUnitCandidate] = {c.work_unit_id: c for c in raw}

    # 叶子：没有任何其他 WorkUnit 以它作为 ParentDocumentID
    leaf = [c for c in raw if c.work_unit_id not in parent_ids]

    # 计算 full_path（用于 UI 更清晰展示）
    enriched: list[WorkUnitCandidate] = []
    for c in leaf:
        full_path = _build_full_path(c.work_unit_id, id_to_candidate)
        enriched.append(
            WorkUnitCandidate(
                work_unit_id=c.work_unit_id,
                name=c.name,
                wwu_file_path=c.wwu_file_path,
                parent_work_unit_id=c.parent_work_unit_id,
                full_path=full_path,
                reference_voice_path=c.reference_voice_path,
                voice_count=c.voice_count,
            )
        )

    enriched.sort(key=lambda x: (x.full_path or x.name, x.name))

    try:
        if callable(progress_cb):
            progress_cb(int(total), int(total), f"发现 {len(enriched)} 个候选")
    except Exception:
        pass

    try:
        cache[cache_key] = {
            "wproj_mtime": float(wproj_mtime),
            "actor_mixer_mtime": float(actor_mixer_mtime),
            "candidates": [_candidate_to_dict(c) for c in enriched],
        }
        _save_cache(cache)
    except Exception:
        pass

    return enriched

