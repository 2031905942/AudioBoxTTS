# IndexTTS2 云服务部署说明（Docker + GPU）

本文档面向把本仓库中的 IndexTTS2 推理能力部署成一个云端 HTTP API 服务，供 SVN 拉取项目的客户端直接调用。

> 目录说明：本仓库服务端代码在 `server/`（小写）。Linux 环境大小写敏感，请勿写成 `Server/`。

---

## 1. 部署前提

### 1.1 硬件建议

- NVIDIA GPU：建议 12GB 显存以上（团队并发建议 16GB+）
- 内存：32GB 起步（建议 64GB）
- 磁盘：NVMe 100GB+（模型与缓存）
- 上行带宽：至少 50–100Mbps（参考音频上传 + 生成音频下载）

### 1.2 软件环境

- Linux 服务器（推荐 Ubuntu 22.04）
- NVIDIA 驱动已安装且 `nvidia-smi` 可用
- Docker 20.10+（建议 24+）
- NVIDIA Container Toolkit（让容器能用 GPU）

---

## 2. 准备仓库与模型

### 2.1 获取代码

把整个仓库拉到服务器（SVN checkout 或直接复制目录均可）。

要求至少包含这些目录：

- `server/`（云服务代码与 docker-compose）
- `Source/indextts/`（推理核心 Python 包）
- `Runtime/IndexTTS2/engine_worker.py`（子进程推理桥接）
- `checkpoints/`（模型权重与配置）

### 2.2 放置模型文件

确认仓库根目录的 `checkpoints/` 下至少包含（以你的实际版本为准）：

- `config.yaml`
- `gpt.pth`
- `s2mel.pth`
- `bpe.model`
- `wav2vec2bert_stats.pt`
- `hf_cache/`（可选但强烈建议，用于 HuggingFace 缓存）

> 说明：服务容器会把宿主机的 `checkpoints/` 以只读方式挂载到 `/app/checkpoints`。

---

## 3. 安装 NVIDIA Container Toolkit（Ubuntu 22.04 示例）

> 如果你已能在 Docker 中运行 `nvidia-smi`，可跳过本节。

1) 验证宿主机 GPU：

```bash
nvidia-smi
```

2) 安装 Docker（略）。

3) 安装 NVIDIA Container Toolkit（按官方文档为准）：

- 安装完成后验证容器 GPU：

```bash
docker run --rm --gpus all nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04 nvidia-smi
```

如果能输出 GPU 信息，说明容器 GPU 配置完成。

---

## 4. 配置服务端

### 4.1 创建 .env

在 `server/` 目录下：

```bash
cd server
cp .env.example .env
```

编辑 `.env`，至少建议配置：

- `TTS_API_KEYS`：设置为一个或多个 API Key（逗号分隔）。不设置则不启用认证。
- `TTS_MAX_QUEUE_SIZE`：队列长度上限（默认 50）
- `TTS_REQUEST_TIMEOUT`：单请求超时（默认 300 秒）

> 提示：当前 API 通过 Header `X-API-Key` 进行认证。

---

## 5. 启动（Docker Compose）

在仓库根目录执行：

```bash
docker compose -f server/docker-compose.yml up -d --build
```

查看日志：

```bash
docker compose -f server/docker-compose.yml logs -f --tail=200
```

预期现象：

- 首次启动会安装依赖并加载模型，耗时较长
- 日志里出现“模型加载完成”后，服务即可对外提供合成

---

## 6. 验证服务

### 6.1 健康检查

```bash
curl http://localhost:8000/api/v1/health
```

- `/api/v1/health`：存活检查（Liveness）。服务已启动就会返回 200，但可能仍在加载模型。

就绪检查（推荐用于编排 healthcheck）：

```bash
curl -i http://localhost:8000/api/v1/ready
```

- `/api/v1/ready`：就绪检查（Readiness）。仅当模型已加载完成才返回 200，否则返回 503。

### 6.2 打开 API 文档

浏览器访问：

- `http://<server-ip>:8000/docs`

### 6.3 合成测试（示例）

> 由于请求体包含 base64 参考音频，建议用脚本生成请求。

PowerShell 示例（把 WAV 转 base64 并调用）：

```powershell
$wavPath = "./ref.wav"
$apiKey = "your-api-key"
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($wavPath))
$body = @{ text = "测试文本"; speaker_audio_base64 = $b64; emo_mode = 0; emo_weight = 1.0 } | ConvertTo-Json -Depth 6
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/synthesize" -Headers @{"X-API-Key"=$apiKey} -ContentType "application/json" -Body $body
```

---

## 7. 客户端如何接入（SVN 项目侧）

客户端只需要：

- 能访问 `http://<server>:8000`
- 配置 URL 与 API Key

如果你采用了 `config/tts_config.json` 的切换方式，示例：

```json
{
  "tts_mode": "remote",
  "remote": {
    "url": "http://your-server:8000",
    "api_key": "your-api-key",
    "timeout": 300
  }
}
```

---

## 8. 常见问题排查

### 8.1 /health 显示 model_not_loaded

- 检查 `checkpoints/` 文件是否齐全
- 检查 GPU 显存是否足够
- 查看容器日志，定位加载失败原因

### 8.2 请求返回“服务繁忙”

- 队列满：提高 `TTS_MAX_QUEUE_SIZE` 或增加 GPU/实例
- 参考音频过大：建议限制参考音频时长（例如 3–15 秒）

### 8.3 参考音频非 WAV 报错

服务端会对非 WAV 尝试用 `ffmpeg` 转换；如果环境没有 `ffmpeg` 或格式异常，会要求上传 WAV。

---

## 9. 生产建议（强烈建议）

- 反向代理 + HTTPS：使用 Nginx/Traefik 终止 TLS
- 限流与配额：按 API Key 做 QPS/并发限制
- 请求体大小限制：避免超大 base64 导致内存压力
- 异步任务形态：把同步 `/synthesize` 升级为 `task_id` 异步（更抗压）
- “Enroll + voice_id” 形态：避免每次都上传参考音频（更接近商业 Voice Cloning API）
