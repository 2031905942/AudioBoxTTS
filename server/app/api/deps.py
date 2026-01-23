"""FastAPI 依赖注入"""

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import APIKeyHeader

from ..config import Settings, get_settings
from ..services import TTSQueue, TTSService

# 全局单例
_tts_service: TTSService | None = None
_tts_queue: TTSQueue | None = None

# API Key 认证
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Depends(api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """验证 API Key"""
    # 如果没有配置 API Keys，跳过验证
    if not settings.get_api_keys():
        return "anonymous"

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key not in settings.get_api_keys():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


def get_tts_service(settings: Settings = Depends(get_settings)) -> TTSService:
    """获取 TTS 服务单例"""
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService(
            model_dir=settings.get_absolute_path(settings.model_dir),
            hf_cache_dir=settings.get_absolute_path(settings.hf_cache_dir),
            runtime_python=settings.get_absolute_path(settings.runtime_python),
            engine_worker=settings.get_absolute_path(settings.engine_worker),
            source_dir=settings.get_absolute_path(settings.source_dir),
            use_fp16=settings.use_fp16,
            use_cuda_kernel=settings.use_cuda_kernel,
            # 合成超时默认与队列超时对齐，避免“队列 5 分钟、推理 10 分钟”的不一致
            synthesize_timeout=settings.request_timeout,
        )
    return _tts_service


def get_tts_queue(settings: Settings = Depends(get_settings)) -> TTSQueue:
    """获取 TTS 队列单例"""
    global _tts_queue
    if _tts_queue is None:
        _tts_queue = TTSQueue(
            max_queue_size=settings.max_queue_size,
            request_timeout=settings.request_timeout,
        )
    return _tts_queue
