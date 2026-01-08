import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DevConfig:
    force_ai_voice_welcome_every_time: bool = False


class DevConfigUtility:
    """读取仓库内的开发配置（config/dev.json）。

    目标：
    - 替代环境变量开关，避免污染同事环境
    - 文件不存在时使用默认值（全部关闭）
    """

    def __init__(self):
        self._cached: DevConfig | None = None
        self._cached_mtime: float | None = None

    @staticmethod
    def _repo_root() -> Path:
        # Source/Utility/dev_config_utility.py -> parents: Utility -> Source -> repo root
        return Path(__file__).resolve().parents[2]

    @classmethod
    def dev_config_path(cls) -> Path:
        return cls._repo_root() / "config" / "dev.json"

    def _load_json(self) -> dict[str, Any]:
        path = self.dev_config_path()
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _get_bool(data: dict[str, Any], *keys: str, default: bool = False) -> bool:
        for key in keys:
            if key in data:
                v = data.get(key)
                if isinstance(v, bool):
                    return v
                if isinstance(v, (int, float)):
                    return bool(v)
                if isinstance(v, str):
                    s = v.strip().lower()
                    if s in {"1", "true", "yes", "y", "on"}:
                        return True
                    if s in {"0", "false", "no", "n", "off"}:
                        return False
        return default

    def load(self) -> DevConfig:
        path = self.dev_config_path()
        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = None

        if self._cached is not None and self._cached_mtime == mtime:
            return self._cached

        data = self._load_json()
        cfg = DevConfig(
            force_ai_voice_welcome_every_time=self._get_bool(
                data,
                "force_ai_voice_welcome_every_time",
                "forceAiVoiceWelcomeEveryTime",
                default=False,
            )
        )

        self._cached = cfg
        self._cached_mtime = mtime
        return cfg

    def force_ai_voice_welcome_every_time(self) -> bool:
        return bool(self.load().force_ai_voice_welcome_every_time)


dev_config_utility = DevConfigUtility()
