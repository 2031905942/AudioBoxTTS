"""服务端配置"""

import json
import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 服务基本配置
    app_name: str = "IndexTTS2 Cloud Service"
    version: str = "1.0.0"
    debug: bool = False

    # API 认证
    # 重要：pydantic-settings 会把 List[str] 当作“复杂类型”优先用 json.loads 解析环境变量。
    # 在 Windows/PowerShell 下常见写法是 `TTS_API_KEYS=key1,key2`（非 JSON），会导致启动失败。
    # 因此这里把原始值按 str 接收，然后在运行期手动解析成 list。
    api_keys: str = ""  # 支持逗号分隔字符串或 JSON 数组

    def get_api_keys(self) -> List[str]:
        """返回解析后的 API Key 列表。

        支持：
        - TTS_API_KEYS=key1,key2
        - TTS_API_KEYS=["key1","key2"]
        - 留空/未设置 -> []
        """
        raw = (self.api_keys or "").strip()
        if not raw:
            return []

        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                pass

        return [p.strip() for p in raw.split(",") if p.strip()]

    # 路径配置（相对于项目根目录）
    model_dir: str = "checkpoints"
    # HuggingFace 缓存目录（相对于项目根目录）。
    # 注意：如果 model_dir 被挂载为只读（如 Docker 里 checkpoints:ro），
    # 默认的 model_dir/hf_cache 将无法写入，从而导致模型加载失败。
    hf_cache_dir: str = "hf_cache"
    runtime_python: str = "Runtime/IndexTTS2/.venv/Scripts/python.exe"
    engine_worker: str = "Runtime/IndexTTS2/engine_worker.py"
    source_dir: str = "Source"

    # 推理配置
    use_fp16: bool = False
    use_cuda_kernel: bool = True

    # 队列配置
    max_queue_size: int = 50
    request_timeout: float = 300  # 5分钟

    # 日志
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_prefix = "TTS_"
        case_sensitive = False

    def get_absolute_path(self, relative_path: str) -> str:
        """获取绝对路径（相对于项目根目录）"""
        # 项目根目录：Server 的父目录
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, relative_path)


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
