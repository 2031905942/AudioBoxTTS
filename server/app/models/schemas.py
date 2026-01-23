"""IndexTTS2 云服务数据模型定义"""

from enum import IntEnum
from typing import List, Optional

from pydantic import BaseModel, Field


class EmotionMode(IntEnum):
    """情感模式"""
    SAME_AS_SPEAKER = 0  # 与音色参考音频相同
    VECTOR_CONTROL = 2   # 使用情感向量控制


class SynthesizeRequest(BaseModel):
    """合成请求"""
    text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="要合成的文本"
    )
    speaker_audio_base64: str = Field(
        ...,
        description="音色参考音频 (base64编码, 支持wav/mp3格式)"
    )
    emo_mode: EmotionMode = Field(
        default=EmotionMode.SAME_AS_SPEAKER,
        description="情感模式: 0=与音色相同, 2=向量控制"
    )
    emo_vector: Optional[List[float]] = Field(
        default=None,
        min_length=8,
        max_length=8,
        description="8维情感向量 [喜,怒,哀,惧,厌恶,低落,惊喜,平静], 仅emo_mode=2时有效"
    )
    emo_weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="情感权重 0.0-1.0"
    )
    # 高级参数（可选）
    temperature: Optional[float] = Field(
        default=None,
        ge=0.05,
        le=1.5,
        description="生成温度, 默认0.7"
    )
    top_p: Optional[float] = Field(
        default=None,
        ge=0.05,
        le=0.99,
        description="Top-p采样, 默认0.9"
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=0,
        le=200,
        description="Top-k采样, 默认40"
    )
    repetition_penalty: Optional[float] = Field(
        default=None,
        ge=0.8,
        le=1.4,
        description="重复惩罚, 默认1.05"
    )


class SynthesizeResponse(BaseModel):
    """合成响应"""
    success: bool = Field(description="是否成功")
    audio_base64: Optional[str] = Field(
        default=None,
        description="生成的音频 (base64编码, wav格式)"
    )
    sample_rate: int = Field(default=22050, description="采样率")
    duration_seconds: Optional[float] = Field(
        default=None,
        description="音频时长(秒)"
    )
    error: Optional[str] = Field(default=None, description="错误信息")
    queue_position: Optional[int] = Field(
        default=None,
        description="当前队列位置(如果在排队)"
    )


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(description="服务状态: ok/error")
    model_loaded: bool = Field(description="模型是否已加载")
    device: str = Field(description="推理设备")
    version: str = Field(description="服务版本")
    queue_length: int = Field(default=0, description="当前队列长度")


class QueueStatusResponse(BaseModel):
    """队列状态响应"""
    queue_length: int = Field(description="当前队列长度")
    max_queue_size: int = Field(description="最大队列容量")
    estimated_wait_seconds: Optional[float] = Field(
        default=None,
        description="预估等待时间(秒)"
    )
