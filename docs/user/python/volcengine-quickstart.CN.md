# Volcengine Provider 快速开始

状态：v0.8
日期：2026-05-28
最近更新：2026-06-12

## 定位

本文说明 Python 版 `vatbrain` 的 Volcengine / 火山方舟 provider 用法。完整 API 字段见 [api-reference.CN.md](api-reference.CN.md)，实现边界见 [volcengine-adapter.CN.md](../../impls/python/volcengine-adapter.CN.md)。

Volcengine adapter 只使用火山方舟 Ark SDK 原生接口：`Ark` / `AsyncArk`、Responses API、Files API、multimodal embeddings、Images API 和 Content Generation tasks。它不使用火山方舟 OpenAI-compatible surface，也不把 OpenAI SDK 配置为火山方舟 base URL。

## 安装与环境

```bash
cd python
../.venv/bin/python -m pip install -e ".[volcengine,test]"
```

初始化 client：

```python
from whero.vatbrain.providers.volcengine import VolcengineClient

client = VolcengineClient(api_key="...")
```

也可以显式传入 Ark SDK client 的非凭据参数；LLM 凭据统一使用 `api_key`：

```python
client = VolcengineClient(
    api_key="...",
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    timeout=30.0,
    max_retries=2,
)
```

## 文本与多模态生成

```python
from whero.vatbrain import ImagePart, MessageItem, TextPart
from whero.vatbrain.providers.volcengine import VolcengineClient

client = VolcengineClient(api_key="...")

response = client.generate(
    model="doubao-seed-1-6-...",
    items=[
        MessageItem.system("You are concise."),
        MessageItem.user([
            TextPart("Describe this image."),
            ImagePart(url="https://example.test/image.png"),
        ]),
    ],
)

for item in response.output_items:
    print(item)
```

视频可使用 URL/base64 data 或先上传后引用 `file_id`。`local_path` 不会隐式上传。

## 流式生成

```python
for event in client.stream_generate(
    model="doubao-seed-1-6-...",
    items=[MessageItem.user("Write a short poem.")],
):
    if event.type == "text.delta":
        print(event.delta, end="")
```

Volcengine streaming 会映射 text、function call arguments、reasoning summary、completed/incomplete/failed/error 等事件，并在 `raw_event` 保留 Ark SDK 原始事件。

## 图片生成

图片生成使用 Ark SDK 原生 `images.generate`。纯文本生成和参考图生成都使用同一个 `generate_image()` 入口：

```python
from whero.vatbrain import ImagePart, MessageItem

response = client.generate_image(
    model="doubao-seedream-5-0-260128",
    prompt="A clean product photo on a walnut desk.",
    input_items=[
        MessageItem.user([
            ImagePart(url="https://example.test/reference.png"),
        ])
    ],
    output_format="png",
    response_format="url",
    watermark=False,
)

for artifact in response.artifacts:
    print(artifact.url or artifact.data)
```

图片流式生成：

```python
for event in client.stream_generate_image(
    model="doubao-seedream-5-0-260128",
    prompt="A cinematic product photo.",
    response_format="url",
):
    if event.artifact:
        print(event.type, event.artifact.url or event.artifact.data)
```

异步入口为 `agenerate_image()` 与 `astream_generate_image()`。

图片生成不提供 normalized `size` 参数。默认由模型从 prompt 中感知分辨率、长宽比和构图规格；如需使用火山方舟原生分辨率控制，应通过 `provider_options` 显式传递对应 Ark 参数。

图片生成请求提供 `watermark` 参数，默认 `True`，并会映射到 Ark `images.generate` 的同名参数。

Volcengine 图片生成当前不支持 normalized `background` 和 `quality`，adapter 会忽略这两个字段。Ark 原生 `size`、`sequential_image_generation`、`sequential_image_generation_options`、`optimize_prompt_options` 等能力可通过 `provider_options` 显式传递；`count` 会映射为 `sequential_image_generation_options.max_images`。

## 视频生成任务

视频生成使用 Ark SDK 原生 `content_generation.tasks.create/get`，以异步任务模型暴露。除 `prompt` 外，`input_items` 还可以携带参考图片、参考视频、参考音频或带 media type 的文件引用：

```python
from whero.vatbrain import ImagePart, MessageItem, VideoPart

task = client.create_video_generation_task(
    model="doubao-seedance-2-0-260128",
    prompt="A short cinematic clip of a product turntable.",
    input_items=[
        MessageItem.user([
            ImagePart(
                url="https://example.test/first-frame.png",
                metadata={"role": "first_frame"},
            ),
            VideoPart(url="https://example.test/motion-reference.mp4", fps=2.0),
        ])
    ],
    duration_seconds=8,
    ratio="16:9",
    generate_audio=True,
    watermark=False,
    provider_options={"return_last_frame": True},
)

task = client.get_video_generation_task(task.id)
task = client.wait_for_video_generation_task(task.id)

for artifact in task.artifacts:
    print(artifact.url)
```

`metadata["role"]` 可用于传递 Ark Content Generation 的 provider-native reference role，例如 `first_frame`、`last_frame`、`reference_image`、`reference_video`。`file_id` 与 `local_path` 不会被隐式上传或读取；需要文件引用时，应使用 URL/base64 data，或先通过 provider 原生流程准备可被任务接口引用的素材 URL。

视频生成请求也提供 `watermark` 参数，默认 `True`，并会映射到 Ark Content Generation task create 的同名参数。

视频任务的 normalized 字段覆盖 `duration_seconds`、`ratio`、`resolution`、`generate_audio` 和 `watermark`。Ark 原生 `seed`、`frames`、`return_last_frame`、`callback_url`、`service_tier`、`execution_expires_after`、`draft`、`priority`、`safety_identifier` 等参数通过 `provider_options` 传递。

`wait_for_video_generation_task()` 会轮询到终态：`completed`、`failed`、`canceled` 或 `expired`；超时会抛 `TimeoutError`。异步入口为 `acreate_video_generation_task()`、`aget_video_generation_task()` 和 `await_video_generation_task()`。

## Reasoning 与 Structured Output

```python
from whero.vatbrain import MessageItem, ReasoningConfig, ResponseFormat

response = client.generate(
    model="doubao-seed-1-6-...",
    items=[MessageItem.user("Extract a JSON object.")],
    reasoning=ReasoningConfig(mode="enabled", effort="low"),
    response_format=ResponseFormat(
        json_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        json_schema_name="answer",
        json_schema_strict=True,
    ),
)
```

Volcengine adapter 将 `ReasoningConfig.mode` 映射为 Ark `thinking.type`，将 `ReasoningConfig.effort` 映射为 `reasoning.effort`。停止序列不属于 `GenerationConfig` 的 normalized 参数；如果目标 Ark API 支持某个原生扩展字段，可通过 `provider_options` 明确传递。

## Function Tools

```python
import json

from whero.vatbrain import FunctionCallItem, FunctionResultItem, MessageItem, ToolSpec

tools = [
    ToolSpec(
        name="get_weather",
        description="Get weather by city.",
        parameters_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        strict=True,
    )
]

items = [MessageItem.user("What is the weather in Shanghai?")]
response = client.generate(model="doubao-seed-1-6-...", items=items, tools=tools)

for output in response.output_items:
    if isinstance(output, FunctionCallItem):
        args = json.loads(output.arguments)
        result = {"city": args["city"], "temperature_c": 22}
        items.extend([
            output,
            FunctionResultItem(call_id=output.call_id, output=json.dumps(result)),
        ])

followup = client.generate(model="doubao-seed-1-6-...", items=items, tools=tools)
```

当前 Volcengine adapter 支持 user-executed function tools，不支持通用 custom tools、provider-hosted tools、Remote MCP 的稳定 helper。

## Files API

```python
from whero.vatbrain import FilePart, FilePreprocessConfig, MessageItem, TextPart

file = client.upload_file(
    file="demo.mp4",
    filename="demo.mp4",
    purpose="user_data",
    mime_type="video/mp4",
    preprocess=FilePreprocessConfig(video_fps=0.3),
)

response = client.generate(
    model="doubao-seed-1-6-...",
    items=[
        MessageItem.user([
            TextPart("Summarize the video."),
            FilePart(file_id=file.id, media_type="video/mp4", provider="volcengine"),
        ])
    ],
)
```

文件方法：

- `upload_file()` / `aupload_file()`
- `retrieve_file()` / `aretrieve_file()`
- `list_files()` / `alist_files()`
- `delete_file()` / `adelete_file()`
- `wait_for_file_processing()` / `await_file_processing()`

火山方舟 Files API 的原生 purpose 是 `user_data`。`vatbrain` core 不定义文件 purpose 通用枚举，也不在 `FileResource` 上保留 normalized purpose；该字段现阶段只作为 Volcengine adapter 的 provider-native 字符串参数使用，返回原始 purpose 保存在 `metadata["raw_purpose"]`。

## 多模态 Embedding

```python
from whero.vatbrain import EmbeddingInput, ImagePart, TextPart

multimodal_embedding = client.embed(
    model="doubao-embedding-vision-...",
    inputs=[
        EmbeddingInput([
            TextPart("blue sky"),
            ImagePart(url="https://example.test/image.png"),
        ])
    ],
    instructions="Target_modality: text.",
    dimensions=1024,
)

text_embedding = client.embed(
    model="doubao-embedding-vision-...",
    inputs=["blue sky"],
    instructions="Target_modality: text.",
    sparse_embedding=True,
)

vector = text_embedding.vectors[0]
print(vector.dense)
print(vector.sparse)
```

Volcengine embedding 每次只提交一个 `EmbeddingInput`，该输入内部可以混合 text/image/video parts。Ark 多模态 embedding 一次返回一个向量；如需处理多个样本，请在用户代码中循环调用。`sparse_embedding` 是 Ark 原生稀疏向量开关，仅支持纯文本输入；混合图片或视频时不要开启。

## Remote Context 与 Replay

```python
from whero.vatbrain import MessageItem, RemoteContextHint

first_items = [MessageItem.user("Summarize this topic.")]
first = client.generate(
    model="doubao-seed-1-6-...",
    items=first_items,
    remote_context=RemoteContextHint(enable_cache=True),
)

history = [*first_items, *first.output_items]
items = [*history, MessageItem.user("Now give three action items.")]

second = client.generate(
    model="doubao-seed-1-6-...",
    items=items,
    remote_context=RemoteContextHint(
        enable_cache=True,
        session_key="topic-session",
        new_items_start_index=len(history),
    ),
)
```

用户仍传完整 `items`。当 `enable_cache=True` 且边界前一个 item 的 provider snapshot metadata 中存在 response id 时，adapter 会向 Ark Responses API 发送未覆盖的 suffix。previous response 失效时，adapter 会自动移除失效 id 并用完整 `items` refresh 一次。

提供 `session_key` 时，Volcengine adapter 会启用 Responses API Session cache：自动设置 `store=True`、`caching={"type":"enabled"}` 和 `expire_at=当前时间+1小时`。`expire_at` 不作为 generation public 参数暴露；如果 anchor response 已接近过期，adapter 会跳过 `previous_response_id` 并直接用完整 `items` 建立新的缓存链。`GenerationResponse.metadata["remote_context"]` 会记录是否使用了 previous response、是否因为即将过期而 refresh，以及不会记录原始 `session_key`。

## 当前限制

- 文本 generation 只使用 Ark SDK Responses API，不提供 Chat API fallback。
- 图片生成只使用 Ark SDK Images API。
- 视频生成只使用 Ark SDK Content Generation tasks。
- 不使用 OpenAI-compatible SDK surface。
- generation 不暴露自定义 `expire_at`；Session cache 生命周期固定 1 小时。
- 不自动上传本地文件。
- 不自动执行工具。
- 不提供 provider-hosted tools / MCP 的稳定通用抽象。
- 不支持跨 provider replay。
- Model capability 默认 unknown，可由用户通过 overrides 补充。
