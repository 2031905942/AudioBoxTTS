# syntax=docker/dockerfile:1.7

# IndexTTS2 云服务 Dockerfile
# 基于 NVIDIA CUDA 镜像，支持 GPU 推理
#
# 使用 uv sync 安装依赖（遵循作者推荐的安装方式）
# 构建命令: docker compose build
# 或: DOCKER_BUILDKIT=1 docker build -f server/Dockerfile -t indextts2-cloud ..

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONUTF8=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_LINK_MODE=copy

# 安装系统依赖
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    git \
    wget \
    curl \
    libsndfile1 \
    ffmpeg \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

# 安装 uv（官方推荐方式）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 创建工作目录
WORKDIR /app

# ============================================================
# 第一阶段：安装服务端依赖（FastAPI 等，变化较少）
# ============================================================
COPY server/requirements.txt ./server/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r server/requirements.txt

# ============================================================
# 第二阶段：安装 IndexTTS2 依赖（使用 uv sync，遵循作者推荐）
# ============================================================
# 复制 pyproject.toml 和 uv.lock
COPY Runtime/IndexTTS2/pyproject.toml Runtime/IndexTTS2/uv.lock ./Runtime/IndexTTS2/

WORKDIR /app/Runtime/IndexTTS2

# 使用 uv sync 安装依赖
# --no-install-project: 只安装依赖，不安装项目本体（因为源码通过 PYTHONPATH 加载）
# --frozen: 使用 uv.lock 中的精确版本
# --no-dev: 不安装开发依赖
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# ============================================================
# 第三阶段：复制应用代码（变化最频繁，放最后）
# ============================================================
WORKDIR /app
COPY server/app ./server/app
COPY Source/indextts ./Source/indextts
COPY Runtime/IndexTTS2/engine_worker.py ./Runtime/IndexTTS2/

# 环境变量配置
ENV PYTHONPATH="/app/Source:/app"
ENV HF_HOME="/app/hf_cache"
ENV HF_HUB_CACHE="/app/hf_cache"
ENV CUDA_VISIBLE_DEVICES="0"

# 服务端配置（可通过环境变量覆盖）
ENV TTS_MODEL_DIR="checkpoints"
ENV TTS_RUNTIME_PYTHON="Runtime/IndexTTS2/.venv/bin/python"
ENV TTS_ENGINE_WORKER="Runtime/IndexTTS2/engine_worker.py"
ENV TTS_SOURCE_DIR="Source"
ENV TTS_USE_FP16="false"
ENV TTS_USE_CUDA_KERNEL="true"
ENV TTS_MAX_QUEUE_SIZE="50"
ENV TTS_LOG_LEVEL="INFO"

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# 启动命令
WORKDIR /app/server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
