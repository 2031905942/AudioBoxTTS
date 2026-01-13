
:::warning
2024.07.10开始提供声音复刻ICL1.0效果，调用时注意传递`model_type=1`，另外原始音频如果不是中文也必须指定语种。
2025.04.30开始提供DiT复刻效果（更适合非实时场景），`model_type=2`为DiT标准版效果（音色、不还原用户的风格），`model_type=3`为DiT还原版效果（音色、还原用户口音、语速等风格）。
2025.10.16开始提供声音复刻ICL2.0效果，调用时注意传递`model_type=4`为声音复刻ICL2.0效果。
:::
:::warning
`model_type=1/2/3/4`时，在合成时需要替换`cluster`。
`model_type=1/2/3`为声音复刻ICL1.0效果，`model_type=4`为声音复刻ICL2.0效果。
如使用字符版，控制台显示的旧`cluster`为`volcano_mega`，需替换为`volcano_icl`;
如使用并发版，控制台显示的旧`cluster`为`volcano_mega_concurr`，需替换为`volcano_icl_concurr`
在使用大模型语音合成-双向流式API时，
`X-Api-Resource-Id`：
`seed-icl-1.0`（声音复刻ICL1.0字符版）
`seed-icl-1.0-concurr`（声音复刻ICL1.0并发版）
`seed-icl-2.0`  (声音复刻ICL2.0字符版)
:::
<span id="597da1a0"></span>
# 上传训练音色

1. 请求方式

**域名：** https://openspeech.bytedance.com
具体请求方式可参考下方`示例代码`
<Attachment link="https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/93d4703b6380432dbc8678342fd55f86~tplv-goo7wpa0wc-image.image" name="uploadAndStatus.py" ></Attachment>

2. 训练（upload接口）

**接口路径:** `POST`/api/v1/mega_tts/audio/upload
**接口描述: 提交音频训练音色**
认证方式使用Bearer Token，在请求的header中加上`"Authorization": "Bearer; {token}"`，并在请求的json中填入对应的appid。
:::warning
Bearer和token使用分号 ; 分隔，替换时请勿保留{}
AppID/Token/Cluster 等信息可参考 [控制台使用FAQ-Q1](https://www.volcengine.com/docs/6561/196768#q1%EF%BC%9A%E5%93%AA%E9%87%8C%E5%8F%AF%E4%BB%A5%E8%8E%B7%E5%8F%96%E5%88%B0%E4%BB%A5%E4%B8%8B%E5%8F%82%E6%95%B0appid%EF%BC%8Ccluster%EF%BC%8Ctoken%EF%BC%8Cauthorization-type%EF%BC%8Csecret-key-%EF%BC%9F)
:::
<span id="ca9fa4cb"></span>
#### 请求参数
**Header:**

| | | | | \
|参数名称 |参数类型 |必须参数 |备注 |
|---|---|---|---|
| | | | | \
|Authorization |string |必填 |Bearer;${Access Token} |
| | | | | \
|Resource-Id |string |必填 |`seed-icl-1.0`   (声音复刻1.0) |\
| | | |`seed-icl-2.0`   (声音复刻2.0) |\
| | | |（声音复刻ICL目前已经支持双向流式） |

**Body:**

| | | | | | \
|参数名称 |层级 |参数类型 |必须参数 |备注 |
|---|---|---|---|---|
| | | | | | \
|appid |1 |string |必填 | |
| | | | | | \
|speaker_id |1 |string |必填 |唯一音色代号 |
| | | | | | \
|audios |1 |list |必填 |音频格式支持：wav、mp3、ogg、m4a、aac、pcm，其中pcm仅支持24k 单通道目前限制单文件上传最大10MB，每次最多上传1个音频文件 |
| | | | | | \
|audio_bytes |2 |string |必填 |二进制音频字节，需对二进制音频进行base64编码 |
| | | | | | \
|audio_format |2 |string | |音频格式，pcm、m4a必传，其余可选 |
| | | | | | \
|text |2 |string | |可以让用户按照该文本念诵，服务会对比音频与该文本的差异。若差异过大会返回1109 WERError |
| | | | | | \
|source |1 |int |必填 |固定值：2 |
| | | | | | \
|language |1 |int | |`model_type`为0或者1时候，支持以下语种 |\
| | | | | |\
| | | | |* cn = 0 中文（默认）  |\
| | | | |* en = 1 英文  |\
| | | | |* ja = 2 日语  |\
| | | | |* es = 3 西班牙语  |\
| | | | |* id = 4 印尼语  |\
| | | | |* pt = 5 葡萄牙语  |\
| | | | | |\
| | | | |`model_type`为2时候，支持以下语种  |\
| | | | | |\
| | | | |* cn = 0 中文（默认）  |\
| | | | |* en = 1 英文 |\
| | | | |* ja = 2 日语  |\
| | | | |* es = 3 西班牙语  |\
| | | | |* id = 4 印尼语  |\
| | | | |* pt = 5 葡萄牙语  |\
| | | | |* de = 6 德语 |\
| | | | |* fr = 7 法语 |\
| | | | | |\
| | | | |`model_type`为3或4时候，仅支持以下语种  |\
| | | | | |\
| | | | |* cn = 0 中文（默认）  |\
| | | | |* en = 1 英文 |
| | | | | | \
|model_type |1 |int | |默认为0 |\
| | | | | |\
| | | | |* 0为声音复刻MEGA效果(不推荐使用) |\
| | | | |* 1为声音复刻ICL1.0效果 |\
| | | | |* 2为DiT标准版效果（音色、不还原用户的风格） |\
| | | | |* 3为DiT还原版效果（音色、还原用户口音、语速等风格） |\
| | | | |* 4为声音复刻ICL2.0效果 |
| | | | | | \
|extra_params |1 |jsonstring | |额外参数 |\
| | | | | |\
| | | | |默认为: `"{}"`,是个 json 字符串 |\
| | | | | |
| | | | | | \
|enable_audio_denoise |2 |bool | |是否开启降噪，开启降噪可能会对声音细节有一定影响，**音频样本噪声较大的情况下建议开启降噪**，音频样本质量较好的情况下建议关闭降噪。声音复刻ICL1.0，即`model_type`为`1/2/3`时默认值为`true`，声音复刻ICL2.0，即`model_type`为4时默认值为`false`。 |\
| | | | |Python示例： |\
| | | | |`"extra_params": json.dumps({"enable_audio_denoise": False})` |
| | | | | | \
|voice_clone_denoise_model_id |2 |string | |人声美化模型选择，去除音频样本中的噪音等（可能会不同程度影响声音细节） |\
| | | | |复刻结果有明显噪声的情况下可以尝试切换不同的模型来测试不同效果。 |\
| | | | |默认为: `""` （空的时候默认是 `SpeechInpaintingV2`） |\
| | | | |可选值： |\
| | | | | |\
| | | | |* `SpeechInpaintingV2` （默认值） |\
| | | | |* `VocalDiffusionV2` |\
| | | | |* `VocalDiffusionV2_44k` |\
| | | | | |\
| | | | |Python示例： |\
| | | | |`"extra_params": json.dumps({"voice_clone_denoise_model_id": "SpeechInpaintingV2"})` |
| | | | | | \
|voice_clone_enable_mss |2 |bool | |是否使用音源分离去除音频样本中背景音，默认值：`false`。 |\
| | | | |Python示例： |\
| | | | |`"extra_params": json.dumps({"voice_clone_enable_mss": False})` |
| | | | | | \
|enable_crop_by_asr |2 |bool | |ASR 截断能避免单个字的发音被切开，核心原因是它能精准定位单个字在音频中的位置。默认的音频时长截断（时长 25s）则可能出现单个字发音被切开的情况。 |\
| | | | |默认值：false |\
| | | | |Python示例： |\
| | | | |`"extra_params": json.dumps({"enable_crop_by_asr": True})` |

**json示例**
```JSON
{
        "speaker_id": "S_*******",（需从控制台获取，参考文档：声音复刻下单及使用指南）
        "appid": "your appid",
        "audios": [{
                "audio_bytes": "base64编码后的音频",
                "audio_format": "wav"
        }],
        "source": 2,
        "language": 0,
        "model_type": 1,
        "extra_params": "{\"voice_clone_denoise_model_id\": \"\"}"
}
```

<span id="10484156"></span>
#### 返回数据
**Body:**

| | | | | | \
|参数名称 |层级 |参数类型 |必须参数 |备注 |
|---|---|---|---|---|
| | | | | | \
|BaseResp |1 |object |必填 | |
| | | | | | \
|StatusCode |2 |int |必填 |成功:0 |
| | | | | | \
|StatusMessage |2 |string | |错误信息 |
| | | | | | \
|speaker_id |1 |string |必填 |唯一音色代号 |

**json示例**
```JSON
{
    "BaseResp":{
        "StatusCode":0,
        "StatusMessage":""
    },
    "speaker_id":"S_*******"
}
```


3. 返回码：


| | | | \
|Success |0 |成功 |
|---|---|---|
| | | | \
|BadRequestError |1001 |请求参数有误 |
| | | | \
|AudioUploadError |1101 |音频上传失败 |
| | | | \
|ASRError |1102 |ASR（语音识别成文字）转写失败 |
| | | | \
|SIDError |1103 |SID声纹检测失败 |
| | | | \
|SIDFailError |1104 |声纹检测未通过，声纹跟名人相似度过高 |
| | | | \
|GetAudioDataError |1105 |获取音频数据失败 |
| | | | \
|SpeakerIDDuplicationError |1106 |SpeakerID重复 |
| | | | \
|SpeakerIDNotFoundError |1107 |SpeakerID未找到 |
| | | | \
|AudioConvertError |1108 |音频转码失败 |
| | | | \
|WERError |1109 |wer检测错误，上传音频与请求携带文本对比字错率过高 |
| | | | \
|AEDError |1111 |aed检测错误，通常由于音频不包含说话声 |
| | | | \
|SNRError |1112 |SNR检测错误，通常由于信噪比过高 |
| | | | \
|DenoiseError |1113 |降噪处理失败 |
| | | | \
|AudioQualityError |1114 |音频质量低，降噪失败 |
| | | | \
|ASRNoSpeakerError |1122 |未检测到人声 |
| | | | \
|已达上传次数限制 |1123 |上传接口已经达到次数限制，目前同一个音色支持10次上传 |


4. 状态查询（status接口）

**接口路径:** `POST`/api/v1/mega_tts/status
**接口描述: 查询音色训练状态**
<span id="7d8a3c2a"></span>
#### 请求参数
**Header:**

| | | | | \
|参数名称 |参数类型 |必须参数 |备注 |
|---|---|---|---|
| | | | | \
|Authorization |string |必填 |Bearer;${Access Token} |
| | | | | \
|Resource-Id |string |必填 |填入 |\
| | | |`seed-icl-1.0 `  (声音复刻ICL 1.0) |\
| | | |`seed-icl-2.0`   (声音复刻ICL 2.0) |

**Body:**

| | | | | | \
|参数名称 |层级 |类型 |必填 |备注 |
|---|---|---|---|---|
| | | | | | \
|appid |1 |string |必填 | |
| | | | | | \
|speaker_id |1 |string |必填 |唯一音色代号 |

**json示例**
```JSON
{
    "appid": "your appid",
    "speaker_id": "S_*******"（需从控制台获取，参考文档：声音复刻下单及使用指南）
}
```

<span id="776080fe"></span>
#### 返回数据
**Body:**

| | | | | | \
|参数名称 |层级 |参数类型 |必须参数 |备注 |
|---|---|---|---|---|
| | | | | | \
|BaseResp |1 |object |必填 | |
| | | | | | \
|StatusCode |2 |int |必填 |成功:0 |
| | | | | | \
|StatusMessage |2 |string | |错误信息 |
| | | | | | \
|speaker_id |1 |string |必填 |唯一音色代号 |
| | | | | | \
|status |1 |enum { NotFound = 0 Training = 1 Success = 2 Failed = 3 Active = 4 } |必填 |训练状态，状态为2或4时都可以调用tts |
| | | | | | \
|create_time |1 |int |必填 |创建时间 |
| | | | | | \
|version |1 |string |选填 |训练版本 |
| | | | | | \
|demo_audio |1 |string |选填 |Success状态时返回，一小时有效，若需要，请下载后使用 |

**json示例**
```JSON
{
    "BaseResp":{
        "StatusCode":0,
        "StatusMessage":""
    },
    "creaet_time":1701055304000,
    "version": "V1",
    "demo_audio": "http://**********.wav"
    "speaker_id":"S_*******",
    "status":2
}
```

<span id="4a39abd8"></span>
# TTS 语音合成接口（WS/HTTP）
音色训练成功后，需要通过调用TTS接口来使用音色合成指定文本的音频。
:::warning
接口与TTS参数有差别，需要将`cluster`换成`volcano_icl`，`voice_type`传`声音id`。
:::
<span id="90321bbf"></span>
## Websocket
> 使用账号申请部分申请到的appid&access_token进行调用
> 文本一次性送入，后端边合成边返回音频数据

<span id="8473acf1"></span>
### 1. 接口说明
> 接口地址为 **wss://openspeech.bytedance.com/api/v1/tts/ws_binary**

<span id="b36183d7"></span>
### 2. 身份认证
认证方式使用Bearer Token，在请求的header中加上`"Authorization": "Bearer; {token}"`，并在请求的json中填入对应的appid。
:::warning
Bearer和token使用分号 ; 分隔，替换时请勿保留{}
:::
AppID/Token/Cluster 等信息可参考 [控制台使用FAQ-Q1](/docs/6561/196768#q1：哪里可以获取到以下参数appid，cluster，token，authorization-type，secret-key-？)
<span id="cb29e655"></span>
### 3. 请求方式
<span id="eebd84f7"></span>
#### 3.1 二进制协议
<span id="a8a704c1"></span>
##### 报文格式(Message format)
![Image](https://lf3-volc-editor.volccdn.com/obj/volcfe/sop-public/upload_cc1c1cdd61bf29f5bde066dc693dcb2b.png =1816x)
所有字段以 [Big Endian(大端序)](https://zh.wikipedia.org/wiki/%E5%AD%97%E8%8A%82%E5%BA%8F#%E5%A4%A7%E7%AB%AF%E5%BA%8F) 的方式存储。
<span id="3431cf06"></span>
###### **字段描述**

| | | | \
|字段 Field (大小, 单位bit) |描述 Description |值 Values |
|---|---|---|
| | | | \
|协议版本(Protocol version) (4) |可能会在将来使用不同的协议版本，所以这个字段是为了让客户端和服务器在版本上保持一致。 |`0b0001` - 版本 1 (目前只有版本1) |
| | | | \
|报头大小(Header size) (4) |header实际大小是 `header size value x 4` bytes. |\
| |这里有个特殊值 `0b1111` 表示header大小大于或等于60(15 x 4 bytes)，也就是会存在header extension字段。 |`0b0001` - 报头大小 = 4 (1 x 4) |\
| | |`0b0010` - 报头大小 = 8 (2 x 4) |\
| | |`0b1010` - 报头大小 = 40 (10 x 4) |\
| | |`0b1110` - 报头大小 = 56 (14 x 4) |\
| | |`0b1111` - 报头大小为60或更大; 实际大小在header extension中定义 |
| | | | \
|消息类型(Message type) (4) |定义消息类型。 |`0b0001` - full client request. |\
| | |`~~0b1001~~` ~~- full server response(弃用).~~ |\
| | |`0b1011` - Audio-only server response (ACK). |\
| | |`0b1111` - Error message from server (例如错误的消息类型，不支持的序列化方法等等) |
| | | | \
|Message type specific flags (4) |flags含义取决于消息类型。 |\
| |具体内容请看消息类型小节. | |
| | | | \
|序列化方法(Message serialization method) (4) |定义序列化payload的方法。 |\
| |注意：它只对某些特定的消息类型有意义 (例如Audio-only server response `0b1011` 就不需要序列化). |`0b0000` - 无序列化 (raw bytes) |\
| | |`0b0001` - JSON |\
| | |`0b1111` - 自定义类型, 在header extension中定义 |
| | | | \
|压缩方法(Message Compression) (4) |定义payload的压缩方法。 |\
| |Payload size字段不压缩(如果有的话，取决于消息类型)，而且Payload size指的是payload压缩后的大小。 |\
| |Header不压缩。 |`0b0000` - 无压缩 |\
| | |`0b0001` - gzip |\
| | |`0b1111` - 自定义压缩方法, 在header extension中定义 |
| | | | \
|保留字段(Reserved) (8) |保留字段，同时作为边界 (使整个报头大小为4个字节). |`0x00` - 目前只有0 |

<span id="aef9feaa"></span>
##### 消息类型详细说明
目前所有TTS websocket请求都使用full client request格式，无论"query"还是"submit"。
<span id="27fb7710"></span>
##### Full client request

* Header size为`b0001`(即4B，没有header extension)。
* Message type为`b0001`.
* Message type specific flags固定为`b0000`.
* Message serialization method为`b0001`JSON。字段参考上方表格。
* 如果使用gzip压缩payload，则payload size为压缩后的大小。

<span id="9e31c953"></span>
##### Audio-only server response

* Header size应该为`b0001`.
* Message type为`b1011`.
* Message type specific flags可能的值有：
   * `b0000` - 没有sequence number.
   * `b0001` - sequence number > 0.
   * `b0010`or`b0011` - sequence number < 0，表示来自服务器的最后一条消息，此时客户端应合并所有音频片段(如果有多条)。
* Message serialization method为`b0000`(raw bytes).

<span id="5b40b4b2"></span>
### 4.注意事项

* 每次合成时reqid这个参数需要重新设置，且要保证唯一性（建议使用uuid.V4生成）
* websocket demo中单条链接仅支持单次合成，若需要合成多次，需自行实现。每次创建websocket连接后，按顺序串行发送每一包。一次合成结束后，可以发送新的合成请求。
* operation需要设置为submit才是流式返回
* 在 websocket 握手成功后，会返回这些 Response header


| | | | \
|Key |说明 |Value 示例 |
|---|---|---|
| | | | \
|X-Tt-Logid |服务端返回的 logid，建议用户获取和打印方便定位问题 |202407261553070FACFE6D19421815D605 |

<span id="7152ac17"></span>
### 5.Demo
<span id="a0669346"></span>
#### python
<Attachment link="https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_0061e1b1abf97e3a792a3ba991c054a3.py" name="tts_websocket_demo.py" size="6.89KB"></Attachment>
<span id="f15c69a4"></span>
#### Java
<Attachment link="https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_d2e2db82dda30a4e291c2fd69823a8f4.zip" name="tts-demo-java.zip" size="7.01KB"></Attachment>
<span id="04d6b71e"></span>
#### Go
<Attachment link="https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_e8bb462f7b7459c6c35ffc332e68a649.go" name="tts_websocket_demo.go" size="7.68KB"></Attachment>
<span id="79dbd2f5"></span>
## HTTP
> 使用账号申请部分申请到的appid&access_token进行调用
> 文本全部合成完毕之后，一次性返回全部的音频数据


<span id="062e0694"></span>
### 1. 接口说明
> 接口地址为 **https://openspeech.bytedance.com/api/v1/tts**

<span id="6ceb285d"></span>
### 2. 身份认证
认证方式采用 Bearer Token.
1)需要在请求的 Header 中填入"Authorization":"Bearer;${token}"
:::warning
Bearer和token使用分号 ; 分隔，替换时请勿保留${}
:::
AppID/Token/Cluster 等信息可参考 [控制台使用FAQ-Q1](/docs/6561/196768#q1：哪里可以获取到以下参数appid，cluster，token，authorization-type，secret-key-？)
<span id="ae690903"></span>
### 3. 注意事项

* 使用 HTTP Post 方式进行请求，返回的结果为 JSON 格式，需要进行解析
* 因 json 格式无法直接携带二进制音频，音频经base64编码。使用base64解码后，即为二进制音频
* 每次合成时 reqid 这个参数需要重新设置，且要保证唯一性（建议使用 UUID/GUID 等生成）
* websocket demo中单条链接仅支持单次合成，若需要合成多次，需自行实现。每次创建websocket连接后，按顺序串行发送每一包。一次合成结束后，可以发送新的合成请求。

4. Demo
<span id="c9bb6471"></span>
### Python
<Attachment link="https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_a24e9f8b99a6d19e3050fd8151919e8a.py" name="tts_http_demo.py" size="1.33KB"></Attachment>
<span id="87485822"></span>
### Java
<Attachment link="https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_eb8a4d1920e352a3bb15a3e1d8b0638b.zip" name="tts_http_demo.zip" size="13.27KB"></Attachment>
<span id="657131c3"></span>
### Go
<Attachment link="https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_875974e0ad7f3e56db5c8240d7fbedc8.go" name="tts_http_demo.go" size="3.44KB"></Attachment>
<span id="e58375cb"></span>
## 参数说明

| | | | | | | \
|**字段** |含义 |层级 |格式 |必需 |备注 |
|---|---|---|---|---|---|
| | | | | | | \
|**app** |应用相关配置 |1 |dict |✓ | |
| | | | | | | \
|**appid** |应用标识 |2 |string |✓ |需要申请 |
| | | | | | | \
|**token** |应用令牌 |2 |string |✓ |可传任意非空字符串 |
| | | | | | | \
|**cluster** |业务集群 |2 |string |✓ |`volcano_icl`或`volcano_icl_concurr` |
| | | | | | | \
|**user** |用户相关配置 |1 |dict |✓ | |
| | | | | | | \
|**uid** |用户标识 |2 |string |✓ |可传任意非空字符串，传入值可以通过服务端日志追溯 |
| | | | | | | \
|**audio** |音频相关配置 |1 |dict |✓ |语音合成参考音色列表；声音复刻语音合成请通过下单获取 |
| | | | | | | \
|**voice_type** |音色类型 |2 |string |✓ |填入S_开头的声音id（SpeakerId） |
| | | | | | | \
|**encoding** |音频编码格式 |2 |string | |wav / pcm / ogg_opus / mp3，默认为 pcm |\
| | | | | |注意：wav 不支持流式 |
| | | | | | | \
|**loudness_ratio** |音量调节 |2 |float | |[0.5,2]，默认为1，通常保留一位小数即可。0.5代表原音量0.5倍，2代表原音量2倍 |
| | | | | | | \
|**rate** |音频采样率 |2 |int | |默认为 24000，可选8000，16000 |
| | | | | | | \
|**speed_ratio** |语速 |2 |float | |[0.2,3]，默认为1，通常保留一位小数即可 |
| | | | | | | \
|**explicit_language** |明确语种 |2 |string | |仅读指定语种的文本 |\
| | | | | | |\
| | | | | |* 不给定参数，正常中英混 |\
| | | | | |* `crosslingual` 启用多语种前端（包含zh/en/ja/es-ms/id/pt-br） |\
| | | | | |* `zh` 中文为主，支持中英混 |\
| | | | | |* `en` 仅英文 |\
| | | | | |* `ja` 仅日文 |\
| | | | | |* `es-mx` 仅墨西 |\
| | | | | |* `id` 仅印尼 |\
| | | | | |* `pt-br` 仅巴葡 |\
| | | | | | |\
| | | | | |当音色是使用model_type=2训练的，即采用dit标准版效果时，建议指定明确语种，目前支持：  |\
| | | | | | |\
| | | | | |* 不给定参数，启用多语种前端`zh,en,ja,es-mx,id,pt-br,de,fr` |\
| | | | | |* `zh,en,ja,es-mx,id,pt-br,de,fr` 启用多语种前端 |\
| | | | | |* `zh` 中文为主，支持中英混  |\
| | | | | |* `en` 仅英文 |\
| | | | | |* `ja` 仅日文  |\
| | | | | |* `es-mx` 仅墨西  |\
| | | | | |* `id` 仅印尼  |\
| | | | | |* `pt-br` 仅巴葡  |\
| | | | | |* `de` 仅德语 |\
| | | | | |* `fr` 仅法语 |\
| | | | | | |\
| | | | | |当音色是使用model_type=3训练的，即采用dit还原版效果时，必须指定明确语种，目前支持：  |\
| | | | | | |\
| | | | | |* `zh` 中文为主，支持中英混  |\
| | | | | |* `en` 仅英文 |
| | | | | | | \
|**context_language** |参考语种 |2 |string | |给模型提供参考的语种 |\
| | | | | | |\
| | | | | |* 不给定 西欧语种采用英语 |\
| | | | | |* id 西欧语种采用印尼 |\
| | | | | |* es 西欧语种采用墨西 |\
| | | | | |* pt 西欧语种采用巴葡 |
| | | | | | | \
|**request** |请求相关配置 |1 |dict |✓ | |
| | | | | | | \
|**text_type** |文本类型 |2 |string | |plain / ssml, 默认为plain。ssml参考[SSML标记语言--语音技术-火山引擎 (volcengine.com)](https://www.volcengine.com/docs/6561/1330194) |\
| | | | | |（DiT音色暂不支持ssml） |
| | | | | | | \
|**with_timestamp** |时间戳相关 |2 |int  |\
| | | |string | |传入1时表示启用，可返回原文本的时间戳，而非TN后文本，即保留原文中的阿拉伯数字或者特殊符号等。注意：原文本中的多个标点连用或者空格依然会被处理，但不影响时间戳连贯性 |
| | | | | | | \
|**reqid** |请求标识 |2 |string |✓ |需要保证每次调用传入值唯一，建议使用 UUID |
| | | | | | | \
|**text** |文本 |2 |string |✓ |合成语音的文本，长度限制 1024 字节（UTF-8编码） |
| | | | | | | \
|**operation** |操作 |2 |string |✓ |query（非流式，http只能query） / submit（流式） |
| | | | | | | \
|**split_sentence** |复刻1.0语速相关 |2 |int |\
| | | |string | |传入1时表示启用，用以解决1.0的声音复刻合成时语速过快的情况 |
| | | | | | | \
|**silence_duration** |句尾静音 |2 |float | |设置该参数可在句尾增加静音时长，范围0~30000ms。（注：增加的句尾静音主要针对传入文本最后的句尾，而非每句话的句尾）若启用该参数，必须在request下首先设置enable_trailing_silence_audio = true |
| | | | | | | \
|**extra_param** |额外参数 |2 |jsonstring | | |
| | | | | | | \
|**mute_cut_remain_ms** |句首静音参数 |3 |string | |该参数需配合mute_cut_threshold参数一起使用，其中： |\
| | | | | |"mute_cut_threshold": "400",   // 静音判断的阈值（音量小于该值时判定为静音） |\
| | | | | |"mute_cut_remain_ms": "50", // 需要保留的静音长度 |\
| | | | | |注：参数和value都为string格式 |\
| | | | | |以python为示例： |\
| | | | | |```Python |\
| | | | | |"extra_param":("{\"mute_cut_threshold\":\"400\", \"mute_cut_remain_ms\": \"100\"}") |\
| | | | | |``` |\
| | | | | | |\
| | | | | |特别提醒： |\
| | | | | | |\
| | | | | |* 因MP3格式的特殊性，句首始终会存在100ms内的静音无法消除，WAV格式的音频句首静音可全部消除，建议依照自身业务需求综合判断选择 |
| | | | | | | \
|**disable_emoji_filter** |emoji不过滤显示 |3 |bool | |开启emoji表情在文本中不过滤显示，默认为False，建议搭配时间戳参数一起使用。 |\
| | | | | |Python示例："extra_param": json.dumps({"disable_emoji_filter": True}) |
| | | | | | | \
|**unsupported_char_ratio_thresh** |不支持语种占比阈值 |3 |float | |默认: 0.3，最大值: 1.0 |\
| | | | | |检测出不支持语种超过设置的比例，则会返回错误码或者返回兜底音频。 |\
| | | | | |Python示例："extra_param": json.dumps({"unsupported_char_ratio_thresh": 0.3}) |
| | | | | | | \
|**cache_config** |缓存相关参数 |3 |dict | |开启缓存，开启后合成相同文本时，服务会直接读取缓存返回上一次合成该文本的音频，可明显加快相同文本的合成速率，缓存数据保留时间1小时。 |\
| | | | | |（通过缓存返回的数据不会附带时间戳） |\
| | | | | |Python示例："extra_param": json.dumps({"cache_config": {"text_type": 1,"use_cache": True}}) |
| | | | | | | \
|**text_type** |缓存相关参数 |4 |int | |和use_cache参数一起使用，需要开启缓存时传1 |
| | | | | | | \
|**use_cache** |缓存相关参数 |4 |bool | |和text_type参数一起使用，需要开启缓存时传true |

备注：

1. 支持ssml能力，参考[SSML标记语言--豆包语音-火山引擎 (volcengine.com)](https://www.volcengine.com/docs/6561/1330194)
2. 暂时不支持音高
3. 支持中英混，支持语种自动识别

请求示例
```JSON
{
    "app": {
        "appid": "appid123",
        "token": "access_token",
        "cluster": "volcano_icl"
    },
    "user": {
        "uid": "uid123"
    },
    "audio": {
        "voice_type": "S_xxxx",（需从控制台获取，参考文档：声音复刻下单及使用指南）
        "encoding": "mp3",
        "speed_ratio": 1
    },
    "request": {
        "reqid": "uuid",
        "text": "字节跳动语音合成",
        "operation": "query"
    }
}
```

<span id="265b9128"></span>
## 返回参数

| | | | | | \
|字段 |含义 |层级 |格式 |备注 |
|---|---|---|---|---|
| | | | | | \
|reqid |请求 ID |1 |string |请求 ID,与传入的参数中 reqid 一致 |
| | | | | | \
|code |请求状态码 |1 |int |错误码，参考下方说明 |
| | | | | | \
|message |请求状态信息 |1 |string |错误信息 |
| | | | | | \
|sequence |音频段序号 |1 |int |负数表示合成完毕 |
| | | | | | \
|data |合成音频 |1 |string |返回的音频数据，base64 编码 |
| | | | | | \
|addition |额外信息 |1 |string |额外信息父节点 |
| | | | | | \
|duration |音频时长 |2 |string |返回音频的长度，单位ms |


* 在 websocket/http 握手成功后，会返回这些 Response header


| | | | \
|Key |说明 |Value 示例 |
|---|---|---|
| | | | \
|X-Tt-Logid |服务端返回的 logid，建议用户获取和打印方便定位问题，使用默认格式即可，不要自定义格式 |202407261553070FACFE6D19421815D605 |


<span id="a2106be9"></span>
# 
响应示例
```JSON
{
    "reqid": "reqid",
    "code": 3000,
    "operation": "query",
    "message": "Success",
    "sequence": -1,
    "data": "base64 encoded binary data",
    "addition": {
        "duration": "1960"
    }
}
```

<span id="553dedc3"></span>
## 返回码说明

| | | | | \
|错误码 |错误描述 |举例 |建议行为 |
|---|---|---|---|
| | | | | \
|3000 |请求正确 |正常合成 |正常处理 |
| | | | | \
|3001 |无效的请求 |一些参数的值非法，比如operation配置错误 |检查参数 |
| | | | | \
|3003 |并发超限 |超过在线设置的并发阈值 |重试；使用sdk的情况下切换离线 |
| | | | | \
|3005 |后端服务忙 |后端服务器负载高 |重试；使用sdk的情况下切换离线 |
| | | | | \
|3006 |服务中断 |请求已完成/失败之后，相同reqid再次请求 |检查参数 |
| | | | | \
|3010 |文本长度超限 |单次请求超过设置的文本长度阈值 |检查参数 |
| | | | | \
|3011 |无效文本 |参数有误或者文本为空、文本与语种不匹配、文本只含标点 |检查参数 |
| | | | | \
|3030 |处理超时 |单次请求超过服务最长时间限制 |重试或检查文本 |
| | | | | \
|3031 |处理错误 |后端出现异常 |重试；使用sdk的情况下切换离线 |
| | | | | \
|3032 |等待获取音频超时 |后端网络异常 |重试；使用sdk的情况下切换离线 |
| | | | | \
|3040 |后端链路连接错误 |后端网络异常 |重试 |
| | | | | \
|3050 |音色不存在 |检查使用的voice_type代号 |检查参数 |

<span id="2b1e6803"></span>
## 常见错误返回说明

1. 错误返回：

    "message": "quota exceeded for types: xxxxxxxxx_lifetime"
**错误原因：试用版用量用完了，需要开通正式版才能继续使用**

2. 错误返回：

"message": "quota exceeded for types: concurrency"
**错误原因：并发超过了限定值，需要减少并发调用情况或者增购并发**

3. 错误返回：

    "message": "Fail to feed text, reason Init Engine Instance failed"
**错误原因：voice_type / cluster 传递错误**

4. 错误返回：

"message": "illegal input text!"
**错误原因：传入的text无效，没有可合成的有效文本。比如全部是标点符号或者emoji表情，或者使用中文音色时，传递日语，以此类推。多语种音色，也需要使用language指定对应的语种**

5. 错误返回：

"message": "authenticate request: load grant: requested grant not found"
**错误原因：鉴权失败，需要检查appid&token的值是否设置正确，同时，鉴权的正确格式为**
**headers["Authorization"] = "Bearer;${token}"**
<span id="83f5315a"></span>
# 音色接口
<span id="cda74ea0"></span>
## API接入说明
<span id="2e989347"></span>
### 访问鉴权

1. 鉴权方式说明 [公共参数--API签名调用指南-火山引擎 (volcengine.com)](https://www.volcengine.com/docs/6369/67268)

线上请求地址域名 open.volcengineapi.com

2. 固定公共参数

```Plain Text
Region = "cn-north-1"
Service = "speech_saas_prod"
Version = "2023-11-07"
解释
```


3. AKSK获取 [访问控制-火山引擎 (volcengine.com)](https://console.volcengine.com/iam/keymanage)

说明：[Access Key（密钥）管理--API访问密钥（Access Key）-火山引擎 (volcengine.com)](https://www.volcengine.com/docs/6291/65568)

4. 调用方式
   1. SDK [SDK概览--API签名调用指南-火山引擎 (volcengine.com)](https://www.volcengine.com/docs/6369/156029)
   2. 直接签名后调用

结合文档内api说明调用 `ListMegaTTSTrainStatus` 的例子(*其他语言和使用sdk调用的方式请参考火山鉴权源码[说明](https://www.volcengine.com/docs/6369/185600) 一)

   3. 示例代码：

<Attachment link="https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/9f981eea343847aaac7fb1b011ba8d86~tplv-goo7wpa0wc-image.image" name="sign.go" ></Attachment>
<Attachment link="https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/24071af48c6049f28f6b60e3239da6f2~tplv-goo7wpa0wc-image.image" name="sign.py" ></Attachment>
<Attachment link="https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/a467b4e10dc44767a9226f09fa3f6ecf~tplv-goo7wpa0wc-image.image" name="sign.java" ></Attachment>
<span id="15d26d16"></span>
### 错误码

1. 非 **2xx** 开头的HTTP返回状态码被可以认为是**错误**
2. 错误的HTTP返回结构体如下

```JSON
{
    "ResponseMetadata": 
    {
        "RequestId": "20220214145719010211209131054BC103", // header中的X-Top-Request-Id参数
        "Action": "ListMegaTTSTrainStatus",
        "Version": "2023-11-07",
        "Service": "{Service}",// header中的X-Top-Service参数
        "Region": "{Region}", // header中的X-Top-Region参数
        "Error": 
        {
            "Code": "InternalError.NotCaptured",
            "Message": "xxx"
        }
    }
}
```


3. **"ResponseMetadata.Error.Code"** 客户端可以依照这个字段判断错误种类，已知种类和含义如下


| | | \
|Code |Description |
|---|---|
| | | \
|OperationDenied.InvalidSpeakerID |账号或AppID无权限操作或无法操作SpeakerID列表中的一个或多个实例 |
| | | \
|OperationDenied.InvalidParameter |请求体字段不合法（缺失必填字段、类型错误等） |
| | | \
|InternalError.NotCaptured |未知的服务内部错误 |

<span id="243e99e6"></span>
## API列表
<span id="d4956898"></span>
### 查询 SpeakerID 状态信息 `ListMegaTTSTrainStatus`
<span id="61d4b195"></span>
#### 接口说明
查询已购买的音色状态信息，支持按`SpeakerIDs`和`State`过滤。
如果查询条件为空，返回账号的AppID下所有的列表（音色超过1000，强烈建议使用分页接口`BatchListMegaTTSTrainStatus`）。
<span id="b9c479bc"></span>
#### **请求方式**
 `POST`
<span id="225a69ce"></span>
#### 请求参数

| | | | | | \
|Parameter |Type |Must |Argument type |Description |
|---|---|---|---|---|
| | | | | | \
|Content-Type |string |Y |header |固定字符串: application/json; charset=utf-8 |
| | | | | | \
|Action |string |Y |query |ListMegaTTSTrainStatus |
| | | | | | \
|Version |string |Y |query |2023-11-07 |
| | | | | | \
|AppID |string |Y |body |AppID |
| | | | | | \
|SpeakerIDs |[]string |N |body |SpeakerID的列表，如果忽略SpeakerIDs查询数据，强烈建议使用分页接口：BatchListMegaTTSTrainStatus |
| | | | | | \
|State |string |N |body |音色状态，支持取值：Unknown、Training、Success、Active、Expired、Reclaimed |\
| | | | |详见附录：State状态枚举值 |
| | | | | | \
|ResourceIDs |[]string |N |body |音色归属服务或者使用模型，支持传参: |\
| | | | |根据服务传参 |\
| | | | |volc.megatts.voiceclone  声音复刻1.0 |\
| | | | |volc.dialog.voiceclone      实时语音大模型声音复刻 |\
| | | | |volc.seedicl.voiceclone    声音复刻2.0 |\
| | | | |根据模型传参: |\
| | | | |seed-icl-1.0 1.0模型（声音复刻1.0和实时语音大模型声音复刻） |\
| | | | |seed-icl-2.0 2.0模型 (声音复刻2.0) |\
| | | | | |\
| | | | |不传，默认查询全部音色 |
| | | | | | \
|OrderTimeStart |int64 |N |body |下单时间检索上边界毫秒级时间戳，受实例交付速度影响，可能比支付完成的时间晚 |
| | | | | | \
|OrderTimeEnd |int64 |N |body |下单时间检索下边界毫秒级时间戳，受实例交付速度影响，可能比支付完成的时间晚 |
| | | | | | \
|ExpireTimeStart |int64 |N |body |实例到期时间的检索上边界毫秒级时间戳 |
| | | | | | \
|ExpireTimeEnd |int64 |N |body |实例到期时间的检索下边界毫秒级时间戳 |

<span id="8b872a49"></span>
#### 返回数据
```JSON
      {
          "ResponseMetadata": {
              "RequestId": "20220214145719010211209131054BC103", // header中的X-Top-Request-Id参数
              "Action": "",
              "Version": "",
              "Service": "{Service}",// header中的X-Top-Service参数
              "Region": "{Region}" // header中的X-Top-Region参数
          },
          "Result":{
                  "Statuses": [
                         {
                              "CreateTime": 1700727790000, // unix epoch格式的创建时间，单位ms
                              "DemoAudio": "https://example.com", // http demo链接
                              "InstanceNO": "Model_storage_meUQ8YtIPm", // 火山引擎实例number
                              "IsActivable": true, // 是否可激活
                              "SpeakerID": "S_VYBmqB0A", // speakerID
                              "State": "Success", // speakerID的状态
                              "Version": "V1", // speakerID已训练过的次数
                              "ExpireTime": 1732895999000, //过期时间
                              "Alias": "", //别名，和控制台同步
                              "AvailableTrainingTimes": 9 //剩余训练次数，激活音色为0
                              "OrderTime": 1701771990000, // 下单时间，单位ms
                              "ResourceID": "seed-icl-1.0" // 音色模型，可用于训练和合成接口传参(seed-icl-1.0 ； seed-icl-2.0)
                        },
                        {
                              "SpeakerID": "S_VYBmqB0B", // speakerID
                              "State": "Unknown", // speakerID的状态
                        }
                  ]
          }
      }
```


<span id="a8755e5b"></span>
### 分页查询SpeakerID状态 `BatchListMegaTTSTrainStatus`
<span id="99293c5f"></span>
#### 接口说明
查询已购买的音色状态；相比`ListMegaTTSTrainStatus` 增加了分页相关参数和返回；支持使用token和声明页数两种分页方式；其中，

* 分页token在最后一页为空
* 分页token采用私有密钥进行加密
* 分页接口为新接口，不影响已有接口行为

<span id="1008d9c9"></span>
#### **请求方式**
 `POST`
<span id="4c708b2a"></span>
#### 请求参数

| | | | | | \
|Parameter |Type |Must |Argument type |Description |
|---|---|---|---|---|
| | | | | | \
|Content-Type | |Y |header |固定字符串: application/json; charset=utf-8 |
| | | | | | \
|Action |string |Y |query |BatchListMegaTTSTrainStatus |
| | | | | | \
|Version |string |Y |query |2023-11-07 |
| | | | | | \
|AppID |string |Y |body |AppID |
| | | | | | \
|SpeakerIDs |[]string |N |body |SpeakerID的列表，传空为返回指定APPID下的全部SpeakerID |
| | | | | | \
|State |string |N |body |音色状态，支持取值：Unknown、Training、Success、Active、Expired、Reclaimed |\
| | | | |详见附录：State状态枚举值 |
| | | | | | \
|ResourceIDs |[]string |N |body |音色归属服务或者使用模型，支持传参: |\
| | | | |根据服务传参 |\
| | | | |volc.megatts.voiceclone  声音复刻1.0 |\
| | | | |volc.dialog.voiceclone      实时语音大模型声音复刻 |\
| | | | |volc.seedicl.voiceclone    声音复刻2.0 |\
| | | | |根据模型传参: |\
| | | | |seed-icl-1.0 1.0模型（声音复刻1.0和实时语音大模型声音复刻） |\
| | | | |seed-icl-2.0 2.0模型 (声音复刻2.0) |\
| | | | | |\
| | | | |不传，默认查询全部音色 |
| | | | | | \
|PageNumber |int |N |body |页数, 需大于0, 默认为1 |
| | | | | | \
|PageSize |int |N |body |每页条数, 必须在范围[1, 100]内, 默认为10 |
| | | | | | \
|NextToken |string |N |body |上次请求返回的字符串; 如果不为空的话, 将覆盖PageNumber及PageSize的值 |
| | | | | | \
|MaxResults |int |N |body |与NextToken相配合控制返回结果的最大数量; 如果不为空则必须在范围[1, 100]内, 默认为10 |
| | | | | | \
|OrderTimeStart |int64 |N |body |下单时间检索上边界毫秒级时间戳，受实例交付速度影响，可能比支付完成的时间晚 |
| | | | | | \
|OrderTimeEnd |int64 |N |body |下单时间检索下边界毫秒级时间戳，受实例交付速度影响，可能比支付完成的时间晚 |
| | | | | | \
|ExpireTimeStart |int64 |N |body |实例到期时间的检索上边界毫秒级时间戳 |
| | | | | | \
|ExpireTimeEnd |int64 |N |body |实例到期时间的检索下边界毫秒级时间戳 |

<span id="07ec8372"></span>
#### 返回数据
```JSON
{
    "ResponseMetadata": 
    {
        "RequestId": "20220214145719010211209131054BC103", // header中的X-Top-Request-Id参数
        "Action": "BatchListMegaTTSTrainStatus",
        "Version": "2023-11-07",
        "Service": "{Service}",// header中的X-Top-Service参数
        "Region": "{Region}" // header中的X-Top-Region参数},
        "Result":
        {
            "AppID": "xxx",
            "TotalCount": 2, // speakerIDs总数量
            "NextToken": "", // NextToken字符串，可发送请求后面的结果; 如果没有更多结果将为空
            "PageNumber": 1, // 使用分页参数时的当前页数
            "PageSize": 2, // 使用分页参数时当前页包含的条数
            "Statuses": 
            [
                {
                    "CreateTime": 1700727790000, // unix epoch格式的创建时间，单位ms
                    "DemoAudio": "https://example.com", // http demo链接
                    "InstanceNO": "Model_storage_meUQ8YtIPm", // 火山引擎实例Number
                    "IsActivable": true, // 是否可激活
                    "SpeakerID": "S_VYBmqB0A", // speakerID
                    "State": "Success", // speakerID的状态
                    "Version": "V1" // speakerID已训练过的次数
                    "ExpireTime": 1964793599000, // 到期时间
                    "OrderTime": 1701771990000, // 下单时间
                    "Alias": "", // 别名，和控制台同步
                    "AvailableTrainingTimes": 10, // 剩余训练次数
                    "ResourceID": "seed-icl-1.0" // 音色模型，可用于训练和合成接口传参(seed-icl-1.0 ； seed-icl-2.0)
                },
                {
                    "SpeakerID": "S_VYBmqB0B", // speakerID
                    "State": "Unknown", // speakerID的状态
                    "Version": "V1" // speakerID已训练过的次数
                }
            ]
        }
}
```


<span id="7c43fc32"></span>
### 音色下单`OrderAccessResourcePacks`
<span id="7461c273"></span>
#### 接口说明
一步下单音色并支付订单，前置条件：

* **AppID已经开通声音复刻**
* **账户里面有足够的余额（或代金券），可以自动支付该订单**
* **频率限制：2分钟内最多下单2000个音色**

<span id="1c84b987"></span>
#### **请求方式**
 `POST`
<span id="b4eac64b"></span>
#### 请求参数

| | | | | | \
|Parameter |Type |Must |Argument type |Description |
|---|---|---|---|---|
| | | | | | \
|Content-Type | |Y |header |固定字符串: application/json; charset=utf-8 |
| | | | | | \
|Action |string |Y |query |OrderAccessResourcePacks |
| | | | | | \
|Version |string |Y |query |2023-11-07 |
| | | | | | \
|AppID |int |Y |body |AppID |
| | | | | | \
|ResourceID |string |Y |body |平台的服务类型资源标识，必填： |\
| | | | |volc.megatts.voiceclone  声音复刻1.0 |\
| | | | |volc.seedicl.voiceclone    声音复刻2.0 |\
| | | | |volc.dialog.voiceclone      实时语音大模型声音复刻 |
| | | | | | \
|Code |string |Y |body |平台的计费项标识，必填且唯一： |\
| | | | |Model_storage 声音复刻1.0和2.0填这个 |\
| | | | |S2S_Model_storage 实时语音大模型声音复刻填这个 |
| | | | | | \
|Times |int |Y |body |下单单个音色的时长，单位为月 |
| | | | | | \
|Quantity |int |Y |body |下单音色的个数，如100，即为购买100个音色 |
| | | | | | \
|AutoUseCoupon |bool |N |body |是否自动使用代金券 |
| | | | | | \
|CouponID |string |N |body |代金券ID，通过[代金券管理](https://www.volcengine.com/docs/6269/67339)获取 |
| | | | | | \
|ResourceTag |object |N |body |项目&标签账单配置 |
| | | | | | \
|ResourceTag.CustomTags |map[string]string |N |body |标签，通过[标签管理](https://www.volcengine.com/docs/6649/189381)获取 |
| | | | | | \
|ResourceTag.ProjectName |string |N |body |项目名称，通过[项目管理](https://www.volcengine.com/docs/6649/94336)获取 |

<span id="db02ef6d"></span>
#### 请求示例
```JSON
{
    "AppID": 100000000,
    "ResourceID": "volc.megatts.voiceclone",
    "Code": "Model_storage",
    "Times": 12,
    "Quantity": 2000
}
```

<span id="27634009"></span>
#### 返回数据
```JSON
{
    "ResponseMetadata": 
    {
        "RequestId": "20220214145719010211209131054BC103", // header中的X-Top-Request-Id参数
        "Action": "OrderAccessResourcePacks",
        "Version": "2023-11-07",
        "Service": "{Service}",// header中的X-Top-Service参数
        "Region": "{Region}" // header中的X-Top-Region参数},
        "Result":
        {
            "OrderIDs": 
            [
                "Order20010000000000000001" // 购买成功返回的订单号ID
            ]
        }
}
```


<span id="3a657453"></span>
### 音色续费`RenewAccessResourcePacks`
<span id="7b5015fb"></span>
#### 接口说明
一步续费音色并支付订单，前置条件：

* **账户里面有足够的余额（或代金券），可以自动支付该订单**
* **频率限制：2分钟内最多续费2000个音色**

<span id="45184772"></span>
#### **请求方式**
 `POST`
<span id="f2c357dd"></span>
#### 请求参数

| | | | | | \
|Parameter |Type |Must |Argument type |Description |
|---|---|---|---|---|
| | | | | | \
|Content-Type | |Y |header |固定字符串: application/json; charset=utf-8 |
| | | | | | \
|Action |string |Y |query |`RenewAccessResourcePacks` |
| | | | | | \
|Version |string |Y |query |2023-11-07 |
| | | | | | \
|Times |int |Y |body |续费音色的时长，单位为月 |
| | | | | | \
|SpeakerIDs |[]string |N |body |要续费的SpeakerID的列表，可以通过`BatchListMegaTTSTrainStatus`接口过滤获取 |
| | | | | | \
|AutoUseCoupon |bool |N |body |是否自动使用代金券 |
| | | | | | \
|CouponID |string |N |body |代金券ID，通过[代金券管理](https://www.volcengine.com/docs/6269/67339)获取 |

<span id="1b2c0e9f"></span>
#### 返回数据
```JSON
{
    "ResponseMetadata": 
    {
        "RequestId": "20220214145719010211209131054BC103", // header中的X-Top-Request-Id参数
        "Action": "OrderAccessResourcePacks",
        "Version": "2023-11-07",
        "Service": "{Service}",// header中的X-Top-Service参数
        "Region": "{Region}" // header中的X-Top-Region参数},
        "Result":
        {
            "OrderIDs": 
            [
                "Order20010000000000000001" // 购买成功返回的订单号ID
            ]
        }
}
```



<span id="c2b77147"></span>
### 附录
<span id="cc0d2106"></span>
#### State状态枚举值

| | | \
|State |Description |
|---|---|
| | | \
|Unknown |SpeakerID尚未进行训练 |
| | | \
|Training |声音复刻训练中（长时间处于复刻中状态请联系火山引擎技术人员） |
| | | \
|Success |声音复刻训练成功，可以进行TTS合成 |
| | | \
|Active |已激活（无法再次训练） |
| | | \
|Expired |火山控制台实例已过期或账号欠费 |
| | | \
|Reclaimed |火山控制台实例已回收 |

<span id="7e757ed2"></span>
#### 常见错误枚举值

| | | \
|Error |Description |
|---|---|
| | | \
|InvalidParameter |请求参数错误 |
| | | \
|Forbidden.InvalidService |未开通声音复刻 |
| | | \
|Forbidden.ErrAccountNotPermission |账号没有权限 |
| | | \
|Forbidden.LimitedTradingFrequency |下单限流错误 |
| | | \
|InvalidParameter.AppID |AppID错误或者无效 |
| | | \
|NotFound.ResourcePack |音色（或资源包）不存在 |
| | | \
|InvalidParameter.InstanceNumber |无效的音色（或实例） |



