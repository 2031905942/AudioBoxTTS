"""IndexTTS2 云服务主入口"""

import asyncio
import logging
import os
import sys

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .api.deps import get_tts_queue, get_tts_service
from .config import get_settings

# 配置日志
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("=== IndexTTS2 云服务启动 ===")
    logger.info(f"版本: {settings.version}")
    logger.info(f"模型目录: {settings.get_absolute_path(settings.model_dir)}")
    logger.info(f"队列大小: {settings.max_queue_size}")

    # 获取服务实例
    tts_service = get_tts_service(settings)
    tts_queue = get_tts_queue(settings)

    # 启动队列处理器
    await tts_queue.start()

    # 异步加载模型（不要阻塞 FastAPI 启动监听端口）
    # 这样 /api/v1/health 仍可用来观察 model_loaded 状态。
    model_load_task: asyncio.Task | None = None

    async def _load_model_background() -> None:
        try:
            logger.info("正在加载模型(后台)...")
            await tts_service.load_model()
            logger.info(f"模型加载完成, device={tts_service.device}")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            logger.warning("服务将以未加载模型状态运行，请手动检查配置")

    model_load_task = asyncio.create_task(_load_model_background())

    yield

    # 关闭服务
    logger.info("正在关闭服务...")
    if model_load_task is not None and not model_load_task.done():
        model_load_task.cancel()
        try:
            await model_load_task
        except Exception:
            pass
    await tts_queue.stop()
    await tts_service.shutdown()
    logger.info("=== 服务已关闭 ===")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="""
IndexTTS2 云端语音合成服务

## 功能

- **语音合成**: 将文本转换为语音
- **音色克隆**: 使用参考音频克隆音色
- **情感控制**: 支持8维情感向量控制

## 认证

所有 API 请求需要在 Header 中携带 `X-API-Key`。

## 队列机制

为避免 GPU 显存溢出，请求会进入队列串行处理。可通过 `/api/v1/queue` 查看当前队列状态。
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
