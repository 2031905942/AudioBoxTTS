"""API 路由定义"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ..config import Settings, get_settings
from ..models import (
    HealthResponse,
    QueueStatusResponse,
    SynthesizeRequest,
    SynthesizeResponse,
)
from ..services import TTSQueue, TTSService
from .deps import get_tts_queue, get_tts_service, verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["TTS"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    service: TTSService = Depends(get_tts_service),
    queue: TTSQueue = Depends(get_tts_queue),
    settings: Settings = Depends(get_settings),
):
    """
    健康检查

    返回服务状态、模型加载状态和队列长度。
    """
    return HealthResponse(
        status="ok" if service.is_model_loaded else "model_not_loaded",
        model_loaded=service.is_model_loaded,
        device=service.device,
        version=settings.version,
        queue_length=queue.queue_length,
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness_check(
    service: TTSService = Depends(get_tts_service),
    queue: TTSQueue = Depends(get_tts_queue),
    settings: Settings = Depends(get_settings),
):
    """就绪检查（Readiness）

    - 仅当模型加载完成且推理引擎存活时返回 200
    - 否则返回 503，便于 Docker/K8s 判定服务是否可接流量
    """
    if not service.is_model_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="模型未就绪",
        )

    return HealthResponse(
        status="ok",
        model_loaded=True,
        device=service.device,
        version=settings.version,
        queue_length=queue.queue_length,
    )


@router.get("/queue", response_model=QueueStatusResponse)
async def queue_status(queue: TTSQueue = Depends(get_tts_queue)):
    """
    队列状态

    返回当前队列长度和预估等待时间。
    """
    return QueueStatusResponse(
        queue_length=queue.queue_length,
        max_queue_size=queue.max_queue_size,
        estimated_wait_seconds=queue.estimated_wait_time(queue.queue_length),
    )


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize(
    request: SynthesizeRequest,
    service: TTSService = Depends(get_tts_service),
    queue: TTSQueue = Depends(get_tts_queue),
    api_key: str = Depends(verify_api_key),
):
    """
    文本转语音合成

    将文本转换为语音，支持音色克隆和情感控制。

    - **text**: 要合成的文本（1-2000字符）
    - **speaker_audio_base64**: 音色参考音频的 base64 编码（wav/mp3格式）
    - **emo_mode**: 情感模式（0=与音色相同, 2=向量控制）
    - **emo_vector**: 8维情感向量 [喜,怒,哀,惧,厌恶,低落,惊喜,平静]（仅 emo_mode=2 时有效）
    - **emo_weight**: 情感权重 0.0-1.0

    请求会进入队列串行处理，避免 GPU 显存溢出。
    """
    if not service.is_model_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="模型未加载，请稍后重试",
        )

    # 创建异步合成任务
    async def synthesize_task():
        return await service.synthesize(request)

    try:
        # 提交到队列
        result, position = await queue.submit(synthesize_task)

        # 将队列位置写入响应（便于客户端提示排队情况）
        try:
            result = result.model_copy(update={"queue_position": position})
        except Exception:
            pass

        if not result.success:
            logger.warning(f"合成失败: {result.error}")

        return result

    except asyncio.QueueFull:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="服务繁忙，请稍后重试",
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="请求处理超时",
        )
    except Exception as e:
        logger.exception(f"合成异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部错误: {e}",
        )
