# IndexTTS2 云服务

将 IndexTTS2 模型部署为云端 API 服务，让客户端无需安装依赖和模型即可使用语音合成功能。

## 快速开始

### 服务端部署

#### 1. 准备环境

- Docker 20.10+
- NVIDIA Container Toolkit（GPU 支持）
- 显存 12GB+ 的 NVIDIA GPU

#### 2. 准备模型文件

确保 `checkpoints/` 目录包含以下文件：
- `config.yaml`
- `gpt.pth`
- `s2mel.pth`
- `bpe.model`
- `wav2vec2bert_stats.pt`
- `hf_cache/`（HuggingFace 模型缓存）

#### 3. 配置服务

```bash
# 复制环境变量配置
cp .env.example .env

# 编辑配置
vim .env
```

#### 4. 启动服务

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

#### 5. 验证服务

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# 查看 API 文档
# 浏览器打开 http://localhost:8000/docs
```

### 客户端配置

修改 `config/tts_config.json`：

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

## API 接口

### 健康检查

```
GET /api/v1/health
```

响应示例：
```json
{
    "status": "ok",
    "model_loaded": true,
    "device": "cuda:0",
    "version": "1.0.0",
    "queue_length": 0
}
```

### 语音合成

```
POST /api/v1/synthesize
Header: X-API-Key: your-api-key
Content-Type: application/json
```

请求体：
```json
{
    "text": "你好，这是一段测试文本。",
    "speaker_audio_base64": "<base64编码的参考音频>",
    "emo_mode": 0,
    "emo_vector": [0, 0, 0, 0, 0, 0, 0, 0],
    "emo_weight": 1.0
}
```

响应：
```json
{
    "success": true,
    "audio_base64": "<base64编码的生成音频>",
    "sample_rate": 22050,
    "duration_seconds": 2.5
}
```

### 队列状态

```
GET /api/v1/queue
```

## 配置说明

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| TTS_API_KEYS | API Key 列表（逗号分隔） | 空（不启用认证） |
| TTS_USE_FP16 | 是否使用半精度推理 | false |
| TTS_USE_CUDA_KERNEL | 是否使用 CUDA kernel | true |
| TTS_MAX_QUEUE_SIZE | 最大队列长度 | 50 |
| TTS_REQUEST_TIMEOUT | 请求超时时间（秒） | 300 |
| TTS_LOG_LEVEL | 日志级别 | INFO |

## 性能建议

- **5-20 人团队**：单 GPU（16GB+）即可，启用请求队列
- **20+ 人团队**：建议多 GPU 或多实例负载均衡

## 故障排除

### 模型加载失败

1. 检查模型文件是否完整
2. 检查 GPU 显存是否充足
3. 查看日志：`docker-compose logs tts-api`

### 请求超时

1. 检查队列状态：`GET /api/v1/queue`
2. 考虑增加超时时间或扩容
