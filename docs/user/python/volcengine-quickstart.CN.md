# Volcengine Provider 快速开始

状态：v0.4
日期：2026-05-28
最近更新：2026-05-28

## 定位

本文说明 Python 版 `vatbrain` 的 Volcengine / 火山方舟 provider 用法。完整 API 字段见 [user/python/api-reference.CN.md](user/python/api-reference.CN.md)，实现边界见 [impls/python/volcengine-adapter.CN.md](impls/python/volcengine-adapter.CN.md)。

v0.4 只使用火山方舟 Ark SDK 原生接口：`Ark` / `AsyncArk`、Responses API、Files API 和 multimodal embeddings。它不使用火山方舟 OpenAI-compatible surface，也不把 OpenAI SDK 配置为火山方舟 base URL。

## 安装与环境

```bash
cd python
.venv/bin/python -m pip install -e ".[volcengine,test]"
export ENV_VATBRAIN_VOLCENGINE_API_KEY="..."
```

初始化 client：

```python
from whero.vatbrain.providers.volcengine import VolcengineClient

client = VolcengineClient()
```

也可以显式传入 Ark SDK client 参数：

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

client = VolcengineClient()

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

v0.4 支持 user-executed function tools，不支持通用 custom tools、provider-hosted tools、Remote MCP 的稳定 helper。

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

embedding = client.embed(
    model="doubao-embedding-vision-...",
    inputs=[
        EmbeddingInput([
            TextPart("blue sky"),
            ImagePart(url="https://example.test/image.png"),
        ])
    ],
    instructions="Target_modality: text.",
    dimensions=1024,
    sparse_embedding=True,
)

vector = embedding.vectors[0]
print(vector.dense)
print(vector.sparse)
```

v0.4 的 Volcengine embedding 每次只提交一个 `EmbeddingInput`，该输入内部可以混合 text/image/video parts。Ark 多模态 embedding 一次返回一个向量；如需处理多个样本，请在用户代码中循环调用。

## Remote Context 与 Replay

```python
from whero.vatbrain import MessageItem, RemoteContextHint, ReplayPolicy

first_items = [MessageItem.user("Summarize this topic.")]
first = client.generate(
    model="doubao-seed-1-6-...",
    items=first_items,
    remote_context=RemoteContextHint(store=True),
)

history = [*first_items, *first.output_items]
items = [*history, MessageItem.user("Now give three action items.")]

second = client.generate(
    model="doubao-seed-1-6-...",
    items=items,
    remote_context=RemoteContextHint(
        previous_response_id=first.id,
        covered_item_count=len(history),
    ),
    replay_policy=ReplayPolicy(
        on_remote_context_invalid="replay_without_remote_context",
    ),
)
```

用户仍传完整 `items`。当 `previous_response_id` 与 `covered_item_count` 同时存在时，adapter 会向 Ark Responses API 发送未覆盖的 suffix。只有显式启用 `replay_without_remote_context` 时，previous response 失效才会自动用完整 `items` 重试一次。

## 当前限制

- Generation 只使用 Ark SDK Responses API，不提供 Chat API fallback。
- 不使用 OpenAI-compatible SDK surface。
- 不自动上传本地文件。
- 不自动执行工具。
- 不提供 provider-hosted tools / MCP 的稳定通用抽象。
- 不支持跨 provider replay。
- Model capability 默认 unknown，可由用户通过 overrides 补充。
