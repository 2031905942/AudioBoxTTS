import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DevConfig:
    force_ai_voice_welcome_every_time: bool = False


class DevConfigUtility:
    """读取开发配置。

    规则（类似角色列表的 default/local）：
    - 仓库默认：config/dev.default.json（应提交到版本库）
    - 本地覆盖：config/dev.json（仅本地存在，应被 SVN/Git 忽略）

    读取逻辑：
    - 若存在本地覆盖文件，则读取本地覆盖文件
    - 否则读取默认文件
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
        """本地覆盖文件路径（不应提交）。"""
        return cls._repo_root() / "config" / "dev.json"

    @classmethod
    def dev_default_config_path(cls) -> Path:
        """仓库默认文件路径（应提交）。"""
        return cls._repo_root() / "config" / "dev.default.json"

    def _effective_path(self) -> Path:
        local_path = self.dev_config_path()
        if local_path.exists():
            return local_path
        return self.dev_default_config_path()

    def _load_json(self) -> dict[str, Any]:
        path = self._effective_path()
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
        path = self._effective_path()
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
                # 默认值：跟随仓库默认文件；若默认文件缺失，则偏向 True（方便开发期显式提醒）
                default=True,
            )
        )

        self._cached = cfg
        self._cached_mtime = mtime
        return cfg

    def force_ai_voice_welcome_every_time(self) -> bool:
        return bool(self.load().force_ai_voice_welcome_every_time)

    def set_force_ai_voice_welcome_every_time(self, value: bool) -> bool:
        """写入本地覆盖文件 config/dev.json（按需创建）。

        返回：是否写入成功
        """
        try:
            local_path = self.dev_config_path()
            default_path = self.dev_default_config_path()
            data: dict[str, Any] = {}
            if local_path.exists():
                try:
                    data = json.loads(local_path.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            elif default_path.exists():
                try:
                    data = json.loads(default_path.read_text(encoding="utf-8"))
                except Exception:
                    data = {}

            data["force_ai_voice_welcome_every_time"] = bool(value)

            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            # 失效缓存
            self._cached = None
            self._cached_mtime = None
            return True
        except Exception:
            return False


dev_config_utility = DevConfigUtility()
