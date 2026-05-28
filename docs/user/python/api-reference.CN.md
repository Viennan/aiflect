# Python API 参考

状态：v0.4
日期：2026-05-13
最近更新：2026-05-28

## 定位

本文是 Python 版本的用户侧 API 参考，覆盖 v0.4 已暴露给用户的主要接口、数据结构和当前 OpenAI / Volcengine adapter 支持范围。渐进式使用流程见 [user/python/quickstart.CN.md](user/python/quickstart.CN.md)；Volcengine provider 用法见 [user/python/volcengine-quickstart.CN.md](user/python/volcengine-quickstart.CN.md)；Pydantic structured output 细节见 [user/python/pydantic-structured-output.CN.md](user/python/pydantic-structured-output.CN.md)。

`vatbrain` 的核心约束：

- 用户显式选择 provider 和 model。
- generation 调用始终以完整 `items` 作为语义上下文。
- provider-side state 只作为优化 hint。
- `vatbrain` 不自动执行工具、不自动重试 agent loop、不自动 provider routing。

## 导入方式

常用 core 模型可直接从 `whero.vatbrain` 导入：

```python
from whero.vatbrain import MessageItem, GenerationConfig, ToolSpec
```

Provider client 从各 provider 包导入：

```python
from whero.vatbrain.providers.openai import OpenAIClient
from whero.vatbrain.providers.volcengine import VolcengineClient
```

Pydantic structured output helper 从 `whero.vatbrain.structured` 导入：

```python
from whero.vatbrain.structured import pydantic_output
```

## Client

### ClientConfig

`ClientConfig` 是通用 provider client 初始化配置：

```python
from whero.vatbrain import ClientConfig

config = ClientConfig(
    api_key="...",
    base_url="...",
    timeout=30.0,
    max_retries=2,
    provider_options={"default_headers": {"x-trace-id": "demo"}},
)
```

字段：

- `api_key`：provider API key。
- `base_url`：provider base URL。
- `timeout`：provider SDK 超时配置。
- `max_retries`：provider SDK 重试配置。
- `provider_options`：透传给 provider SDK client 初始化的额外参数。

### OpenAIClient

当前已实现 provider：OpenAI、Volcengine。

```python
from whero.vatbrain.providers.openai import OpenAIClient

client = OpenAIClient()
```

OpenAI API key 可通过 `ENV_VATBRAIN_OPENAI_API_KEY` 提供，也可在初始化时传入：

```python
client = OpenAIClient(api_key="...", base_url="...", timeout=30.0)
```

初始化参数：

- `config`：`ClientConfig`。
- `api_key`、`base_url`、`timeout`、`max_retries`：覆盖 `config` 中的同名字段。
- `client`：注入已有同步 OpenAI SDK client，常用于测试或复用连接。
- `async_client`：注入已有异步 OpenAI SDK client。
- `model_capability_overrides`：用户侧模型能力覆写。
- `**openai_client_options`：透传给 OpenAI SDK client 的初始化参数。

OpenAI client 方法：

- `generate(...) -> GenerationResponse`
- `agenerate(...) -> GenerationResponse`
- `stream_generate(...) -> Iterator[GenerationStreamEvent]`
- `astream_generate(...) -> AsyncIterator[GenerationStreamEvent]`
- `generate_parsed(...) -> ParsedGenerationResponse`
- `agenerate_parsed(...) -> ParsedGenerationResponse`
- `embed(...) -> EmbeddingResponse`
- `aembed(...) -> EmbeddingResponse`
- `get_adapter_capability() -> AdapterCapability`
- `get_model_capability(model, overrides=None) -> ModelCapability`

### VolcengineClient

Volcengine provider 使用火山方舟 Ark SDK 原生接口，不使用 OpenAI-compatible SDK surface。

```python
from whero.vatbrain.providers.volcengine import VolcengineClient

client = VolcengineClient()
```

Volcengine API key 可通过 `ENV_VATBRAIN_VOLCENGINE_API_KEY` 提供，也可在初始化时传入：

```python
client = VolcengineClient(api_key="...", base_url="...", timeout=30.0)
```

安装 extra：

```bash
cd python
.venv/bin/python -m pip install -e ".[volcengine]"
```

初始化参数：

- `config`：`ClientConfig`。
- `api_key`、`base_url`、`timeout`、`max_retries`：覆盖 `config` 中的同名字段。
- `client`：注入已有同步 Ark SDK client，常用于测试或复用连接。
- `async_client`：注入已有异步 Ark SDK client。
- `model_capability_overrides`：用户侧模型能力覆写。
- `**ark_client_options`：透传给 Ark SDK client 的初始化参数，例如 `ak`、`sk`、`region` 等。

Volcengine client 方法：

- `generate(...) -> GenerationResponse`
- `agenerate(...) -> GenerationResponse`
- `stream_generate(...) -> Iterator[GenerationStreamEvent]`
- `astream_generate(...) -> AsyncIterator[GenerationStreamEvent]`
- `generate_parsed(...) -> ParsedGenerationResponse`
- `agenerate_parsed(...) -> ParsedGenerationResponse`
- `embed(...) -> EmbeddingResponse`
- `aembed(...) -> EmbeddingResponse`
- `upload_file(...) -> FileResource`
- `aupload_file(...) -> FileResource`
- `retrieve_file(file_id, ...) -> FileResource`
- `aretrieve_file(file_id, ...) -> FileResource`
- `list_files(...) -> tuple[FileResource, ...]`
- `alist_files(...) -> tuple[FileResource, ...]`
- `delete_file(file_id, ...) -> FileResource`
- `adelete_file(file_id, ...) -> FileResource`
- `wait_for_file_processing(file_id, ...) -> FileResource`
- `await_file_processing(file_id, ...) -> FileResource`
- `get_adapter_capability() -> AdapterCapability`
- `get_model_capability(model, overrides=None) -> ModelCapability`

## Items

`Item` 是 generation 上下文和模型输出的核心单位。v0.3 的 `Item` 联合类型包含：

- `MessageItem`
- `FunctionCallItem`
- `FunctionResultItem`
- `ReasoningItem`

相关枚举：

- `Role`：`system`、`developer`、`user`、`assistant`、`tool`。
- `ItemKind`：`message`、`function_call`、`function_result`、`reasoning`。
- `ItemPurpose`：`instruction`、`query`、`context`、`answer`、`tool_io`、`artifact`。
- `PartKind`：`text`、`image`、`audio`、`video`、`file`。

### MessageItem

`MessageItem` 表达 message-like 上下文项。`parts` 可以是字符串，也可以是 content part 列表。

```python
from whero.vatbrain import MessageItem, TextPart, ImagePart

items = [
    MessageItem.system("You are concise."),
    MessageItem.user("Hello"),
    MessageItem.user([
        TextPart("Describe this image."),
        ImagePart(url="https://example.test/image.png"),
    ]),
]
```

便捷构造：

- `MessageItem.system(parts)`
- `MessageItem.developer(parts)`
- `MessageItem.user(parts)`
- `MessageItem.assistant(parts, assistant_phase=None)`

`assistant_phase` 只对 assistant message 有意义：

```python
from whero.vatbrain import AssistantMessagePhase, MessageItem

item = MessageItem.assistant(
    "Let me inspect that.",
    assistant_phase=AssistantMessagePhase.COMMENTARY,
)
```

OpenAI adapter 会把 `AssistantMessagePhase.COMMENTARY` / `FINAL_ANSWER` 映射到 OpenAI Responses API 的 `phase`。Provider response 映射出的 message 通常还会携带 `provider_snapshots`，用于同 provider 高保真重放。

### Content Parts

`TextPart`：

```python
TextPart("hello")
```

`ImagePart` 需要且只能提供 `url` 或 `data` 之一：

```python
ImagePart(url="https://example.test/image.png", detail="high")
ImagePart(data="data:image/png;base64,...")
```

`AudioPart`、`VideoPart`、`FilePart` 支持 `file_id`、`url`、`data`、`local_path` 等引用方式，但同一 part 只能选择一个来源：

```python
from whero.vatbrain import AudioPart, FilePart, VideoPart

AudioPart(url="https://example.test/audio.mp3", mime_type="audio/mpeg")
VideoPart(file_id="file_video_123", provider="volcengine")
FilePart(local_path="./contract.pdf", mime_type="application/pdf")
```

`local_path` 只是 metadata，不会自动读取或上传文件。需要 provider 文件资源时，应使用对应 provider adapter 的显式 file/resource API。OpenAI adapter 尚未暴露文件管理方法；Volcengine adapter 已支持 Ark Files API。

### FunctionCallItem

`FunctionCallItem` 是模型请求调用用户工具的输出项：

```python
from whero.vatbrain import FunctionCallItem

call = FunctionCallItem(
    name="get_weather",
    arguments='{"city":"Shanghai"}',
    call_id="call_123",
)
```

字段：

- `name`：工具名称。
- `arguments`：function tool 的 JSON string 参数；custom tool 中为了兼容也会保存 raw input。
- `call_id`：工具调用关联 ID，回填结果时必须使用。
- `id`、`status`：provider 输出项 ID 与状态。
- `type`：`function` 或 `custom`。
- `input`：custom tool 的 raw string input。
- `provider_snapshots`：同 provider/API family replay snapshot。

### FunctionResultItem

用户执行工具后，将结果作为 `FunctionResultItem` 加入下一轮完整上下文：

```python
from whero.vatbrain import FunctionResultItem

result = FunctionResultItem(
    call_id="call_123",
    output='{"temperature_c":22}',
)
```

custom tool 结果需要携带 `tool_type="custom"`，OpenAI adapter 才能映射为 `custom_tool_call_output`：

```python
FunctionResultItem(call_id="call_123", output="done", tool_type="custom")
```

### ReasoningItem

`ReasoningItem` 表达 provider 返回的 reasoning summary、reasoning text 或原始 reasoning 内容：

```python
from whero.vatbrain import ReasoningItem

reasoning = ReasoningItem(
    summary="The model compared two options.",
    provider="openai",
    visibility="summary",
)
```

字段：

- `text`、`summary`、`raw`：三者至少提供一个。
- `provider`：来源 provider。
- `visibility`：provider-specific 可见性描述。
- `can_be_replayed`：是否适合作为后续上下文回放。
- `provider_snapshots`：原生 replay payload。

### ProviderItemSnapshot

`ProviderItemSnapshot` 保存同 provider/API family 下可重放的原始 item payload：

```python
from whero.vatbrain import provider_snapshot_for, provider_snapshot_key

key = provider_snapshot_key("openai", "responses")
snapshot = provider_snapshot_for(item, provider="openai", api_family="responses")
```

用户通常不需要手工构造 snapshot；provider adapter 会在 response mapping 时挂载。Snapshot 只用于同 provider 高保真重放，不支持跨 provider replay。

## Generation

### generate / agenerate

同步生成：

```python
response = client.generate(
    model="gpt-5.1",
    items=[MessageItem.user("Hello")],
)
```

异步生成：

```python
response = await client.agenerate(
    model="gpt-5.1",
    items=[MessageItem.user("Hello")],
)
```

参数：

- `model`：provider model id。
- `items`：完整语义上下文。
- `tools`：`ToolSpec` 序列。
- `generation_config`：温度、top_p、输出长度等。
- `response_format`：JSON Schema structured output。
- `reasoning`：reasoning 行为配置。
- `tool_call_config`：工具调用行为配置。
- `remote_context`：previous response/store hint。
- `replay_policy`：provider-native replay 行为。
- `provider_options`：透传 provider 请求参数。

返回 `GenerationResponse`：

- `id`：provider response id。
- `provider`：provider id。
- `model`：provider 返回的 model。
- `output_items`：模型输出项。
- `stop_reason`：停止原因或 provider 状态。
- `usage`：`Usage`。
- `metadata`、`raw`：诊断与原始响应。

### GenerationRequest

Provider client 通常替用户构造 `GenerationRequest`。如果需要在测试 mapper 或构建 adapter 时直接使用，可以这样写：

```python
from whero.vatbrain import GenerationRequest, MessageItem

request = GenerationRequest(
    model="gpt-5.1",
    items=[MessageItem.user("Hello")],
    provider_options={"metadata": {"trace_id": "demo"}},
)
```

字段与 `client.generate()` 参数一致：

- `model`
- `items`
- `tools`
- `generation_config`
- `response_format`
- `reasoning`
- `tool_call_config`
- `stream_options`
- `remote_context`
- `replay_policy`
- `provider_options`

### GenerationConfig

```python
from whero.vatbrain import GenerationConfig

config = GenerationConfig(
    temperature=0.2,
    top_p=0.9,
    max_output_tokens=300,
)
```

### ResponseFormat

`ResponseFormat` 只表达 JSON Schema structured output，不兼容 JSON mode / `json_object`：

```python
from whero.vatbrain import ResponseFormat

response_format = ResponseFormat(
    json_schema={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "additionalProperties": False,
    },
    json_schema_name="person",
    json_schema_description="Extracted person.",
    json_schema_strict=True,
)
```

`json_schema` 应是 schema body，不是 provider wrapper。

### ReasoningConfig

```python
from whero.vatbrain import ReasoningConfig

reasoning = ReasoningConfig(
    mode="auto",
    effort="low",
    budget_tokens=1024,
    summary="auto",
    include_trace=False,
    provider_options={},
)
```

不同 provider 对 `effort` 的取值和语义可能不同。支持的 effort 应通过 capability 查询。Volcengine adapter 将 `mode` 映射为 Ark `thinking.type`，将 `effort` 映射为 `reasoning.effort`。

### ToolCallConfig

```python
from whero.vatbrain import ToolCallConfig, ToolChoice

tool_call_config = ToolCallConfig(
    parallel_tool_calls=False,
    tool_choice=ToolChoice.AUTO,
)
```

`tool_choice` 也可以传 provider 原生 dict；只有具备跨 provider 语义的配置才建议进入通用字段。

### RemoteContextHint

`RemoteContextHint` 表达 provider-side previous response/store 优化 hint：

```python
from whero.vatbrain import RemoteContextHint

remote_context = RemoteContextHint(
    previous_response_id="resp_123",
    covered_item_count=4,
    store=True,
)
```

字段：

- `previous_response_id`：provider response id。
- `covered_item_count`：该 response id 已覆盖完整 `items` 的前缀 item 数。
- `store`：是否请求 provider 存储本轮 response。
- `provider_options`：provider-specific remote context 参数。

用户仍必须传入完整 `items`。OpenAI adapter 在 `previous_response_id` 与 `covered_item_count` 同时存在时，只向 provider 发送未覆盖的 suffix；如果 previous response 失效且用户显式启用 fallback，则会重新用完整 `items` 请求。

### ReplayPolicy

```python
from whero.vatbrain import ReplayPolicy

policy = ReplayPolicy(
    mode="prefer_provider_native",
    on_remote_context_invalid="raise",
)
```

`mode`：

- `normalized_only`：只用 normalized mapper。
- `prefer_provider_native`：有 provider snapshot 时优先使用，缺失时降级。
- `require_provider_native`：强制使用 snapshot，缺失即报错。

`on_remote_context_invalid`：

- `raise`：previous response 失效时抛错。
- `replay_without_remote_context`：显式允许移除失效 remote context，用完整 `items` 自动重试一次。

`cross_provider` 当前只支持 `unsupported`。

### Streaming

`StreamOptions` 当前只有 `include_usage`：

```python
from whero.vatbrain import StreamOptions

stream_options = StreamOptions(include_usage=True)
```

这是通用 core 字段；OpenAI / Volcengine Responses API 当前不会把它映射为 provider 的 `stream_options.include_usage`。

同步流式：

```python
for event in client.stream_generate(
    model="gpt-5.1",
    items=[MessageItem.user("Write a haiku.")],
):
    if event.type == "text.delta":
        print(event.delta, end="")
```

异步流式：

```python
async for event in client.astream_generate(
    model="gpt-5.1",
    items=[MessageItem.user("Write a haiku.")],
):
    ...
```

`GenerationStreamEvent` 字段：

- `type`：标准化事件类型字符串。
- `sequence`：本地事件序号。
- `provider`：provider id。
- `response_id`、`item_id`：provider 关联 ID。
- `delta`：增量内容。
- `item`：标准化 item。
- `usage`：usage 更新。
- `response`：完整 response。
- `error`：错误文本。
- `metadata`：事件元数据。
- `raw_event`：provider 原始事件。

常见事件类型：

- `response.created`、`response.started`、`response.completed`
- `item.created`、`item.completed`
- `content_part.created`、`content_part.completed`
- `text.delta`、`text.completed`
- `tool_call.delta`、`tool_call.completed`
- `reasoning.delta`、`reasoning.completed`
- `usage.updated`
- `response.incomplete`、`response.failed`、`response.error`
- `unknown`

这些事件类型也可通过 `StreamEventType` 枚举引用：

```python
from whero.vatbrain.core.generation import StreamEventType

if event.type == StreamEventType.TEXT_DELTA.value:
    ...
```

使用 `GenerationStreamAccumulator` 可从流式事件重建最终响应：

```python
from whero.vatbrain import GenerationStreamAccumulator

accumulator = GenerationStreamAccumulator(provider="openai")
for event in client.stream_generate(model="gpt-5.1", items=[MessageItem.user("Hi")]):
    accumulator.add(event)

response = accumulator.to_response()
```

## Tools

`ToolSpec` 是 `FunctionToolSpec` 的兼容别名。当前通用 core 只覆盖用户代码执行的 function/custom tool。

### Function Tool

```python
from whero.vatbrain import ToolSpec

tool = ToolSpec(
    name="get_weather",
    description="Get weather by city.",
    parameters_schema={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
    strict=True,
)
```

字段：

- `name`：工具名，必填。
- `description`：工具说明。
- `parameters_schema`：JSON Schema 参数定义；空 schema 表示普通 function tool 的空 object 参数，不表示 custom tool。
- `strict`：是否请求 provider 使用严格参数 schema。
- `type`：`function` 或 `custom`，默认 `function`。
- `execution_owner`：当前只能是 `user`。
- `provider_options`：工具声明级 provider-specific 参数。

### Custom Tool

custom tool 用于让模型直接输出任意字符串输入，例如代码、查询语句或自然语言：

```python
tool = ToolSpec(
    name="run_code",
    description="Run Python code.",
    type="custom",
)
```

OpenAI adapter 将其映射为 OpenAI custom tool。Volcengine adapter v0.4 不支持 custom tool，只支持普通 function tool。模型输出仍是 `FunctionCallItem`，但 OpenAI custom tool 的 `type == "custom"` 且 raw input 位于 `input` 字段。回填结果时使用 `FunctionResultItem(tool_type="custom")`。

## Structured Output

### Pydantic Helper

```python
from pydantic import BaseModel
from whero.vatbrain.structured import pydantic_output

class Contact(BaseModel):
    name: str
    email: str

output = pydantic_output(Contact, name="contact")
response = client.generate(
    model="gpt-5.1",
    items=[MessageItem.user("Extract a contact.")],
    response_format=output.response_format,
)
contact = output.parse_response(response).output_parsed
```

`pydantic_output()` 参数：

- `output_type`：Pydantic v2 支持的类型。
- `name`：schema name；默认使用类型名。
- `description`：schema description；默认使用类型 docstring。
- `strict`：默认 `True`，会生成更适合 structured output 的 strict schema。

返回 `PydanticOutputSpec`：

- `response_format`：普通 `ResponseFormat`。
- `parse_text(text)`：解析 JSON 文本。
- `parse_response(response)`：解析 `GenerationResponse` 中 assistant text。

`ParsedGenerationResponse` 字段：

- `response`
- `output_text`
- `output_parsed`

解析失败抛出 `StructuredOutputParseError`，其中包含 `output_text`、`response` 与原始 `cause`。

### Client Convenience

OpenAI client 提供薄封装：

```python
parsed = client.generate_parsed(
    model="gpt-5.1",
    items=[MessageItem.user("Extract a contact.")],
    output_type=Contact,
)
```

`generate_parsed()` / `agenerate_parsed()` 使用默认 Pydantic helper 行为；如需自定义 schema name、description 或 strict，请显式使用 `pydantic_output()` + `generate()`。

## Embedding

### embed / aembed

```python
response = client.embed(
    model="text-embedding-3-small",
    inputs=["first document", "second document"],
)
```

异步：

```python
response = await client.aembed(
    model="text-embedding-3-small",
    inputs=["first document"],
)
```

OpenAI adapter 支持文本 embedding。Volcengine adapter 支持多模态 embedding、instructions、dimensions、encoding_format 与 sparse vectors。

### EmbeddingInput

```python
from whero.vatbrain import EmbeddingInput, ImagePart, MessageItem, TextPart

EmbeddingInput.text("hello")
EmbeddingInput.from_message(MessageItem.user("hello"))
EmbeddingInput([ImagePart(url="https://example.test/image.png")], modality="image")
EmbeddingInput([TextPart("blue sky"), ImagePart(url="https://example.test/image.png")])
```

字段：

- `parts`：embedding-compatible content parts。
- `modality`：输入模态提示。
- `metadata`：用户元数据。

### EmbeddingRequest

Provider client 通常由 `embed()` 代替用户构造 `EmbeddingRequest`，但模型如下：

```python
from whero.vatbrain import EmbeddingRequest

request = EmbeddingRequest(
    model="embedding-model",
    inputs=["hello"],
    instructions="Represent this as a search query.",
    dimensions=1024,
    encoding_format="float",
    sparse_embedding=True,
)
```

### EmbeddingVector / SparseEmbedding

```python
from whero.vatbrain import SparseEmbedding, EmbeddingVector

sparse = SparseEmbedding(indices=[1, 5], values=[0.2, 0.8], dimensions=1000)
vector = EmbeddingVector(index=0, dense=[0.1, 0.2], sparse=sparse)
```

`EmbeddingVector.embedding` 是兼容旧用法的 dense 别名；新代码优先读取 `dense` 和 `sparse`。

`EmbeddingResponse` 字段：

- `provider`
- `model`
- `vectors`
- `dimensions`
- `usage`
- `metadata`
- `raw`

Volcengine 多模态 embedding 每次 request 只提交一个 `EmbeddingInput`；该 input 内部可以混合 text/image/video parts。Ark API 一次返回一个向量，如需多个样本，请在用户代码中循环调用。

## Resources

v0.3 已定义 resource/file core 模型。OpenAI adapter 尚未暴露文件资源方法；Volcengine adapter 已实现 Ark Files API。

### FileUploadRequest

```python
from whero.vatbrain import FilePreprocessConfig, FileUploadRequest

request = FileUploadRequest(
    file="./demo.mp4",
    filename="demo.mp4",
    mime_type="video/mp4",
    preprocess=FilePreprocessConfig(video_fps=1.0),
)
```

`FileUploadRequest.file` 可以是 bytes、字符串路径、`PathLike` 或 provider adapter 支持的文件对象。Core 不执行本地 I/O。

`FilePreprocessConfig` 只包含：

- `video_fps`：视频文件预处理抽帧帧率提示。
- `provider_options`：provider-native 预处理参数。

Volcengine client 可直接调用文件方法：

```python
from whero.vatbrain import FilePreprocessConfig

file = volcengine_client.upload_file(
    file="demo.mp4",
    filename="demo.mp4",
    purpose="user_data",
    mime_type="video/mp4",
    preprocess=FilePreprocessConfig(video_fps=0.3),
)

ready_file = volcengine_client.wait_for_file_processing(file.id)
```

### FileResource

```python
from whero.vatbrain import FileResource, FileStatus

resource = FileResource(
    id="file_123",
    provider="volcengine",
    filename="demo.mp4",
    status=FileStatus.READY,
)
```

相关枚举：

- `FileStatus`：`uploaded`、`processing`、`ready`、`failed`、`deleted`、`expired`、`unknown`。

Core 不定义文件 purpose 通用枚举，`FileUploadRequest` / `FileResource` 也不包含 normalized purpose 字段。Volcengine Ark 原生 purpose `user_data` 是 adapter 级字符串参数，返回原始值保存在 `FileResource.metadata["raw_purpose"]`。

## Media

v0.3 已定义 media generation core 模型，但当前 OpenAI / Volcengine adapter 尚未暴露 image/video generation 方法。

### MediaArtifact

```python
from whero.vatbrain import MediaArtifact, MediaKind

artifact = MediaArtifact(
    kind=MediaKind.IMAGE,
    url="https://example.test/image.png",
    mime_type="image/png",
    width=1024,
    height=1024,
)
```

`MediaArtifact` 需要至少提供 `url`、`data`、`file_id` 或 `raw` 之一。

### ImageGenerationRequest / Response

```python
from whero.vatbrain import ImageGenerationRequest

request = ImageGenerationRequest(
    model="image-model",
    prompt="A product photo on a clean desk.",
    size="1024x1024",
    output_format="png",
    count=1,
)
```

`ImageGenerationResponse` 包含：

- `provider`
- `model`
- `artifacts`
- `usage`
- `metadata`
- `raw`

`ImageGenerationStreamEvent` 用于表达图片生成流式事件，字段包括 `type`、`sequence`、`provider`、`task_id`、`artifact`、`delta`、`usage`、`error`、`metadata`、`raw_event`。

### MediaGenerationTask

```python
from whero.vatbrain import MediaGenerationTask, TaskStatus

task = MediaGenerationTask(
    id="task_123",
    provider="volcengine",
    model="video-model",
    status=TaskStatus.RUNNING,
)
```

`TaskStatus`：`queued`、`running`、`completed`、`failed`、`canceled`、`expired`、`unknown`。

## Capability

Capability 用于描述 adapter/model 已知能力及其来源，不是内部权威模型库。

### CapabilityValue

```python
from whero.vatbrain import CapabilityValue

unknown = CapabilityValue.unknown()
declared = CapabilityValue.adapter_builtin(True)
user_value = CapabilityValue.user_supplied(("low", "medium", "high"))
```

字段：

- `value`：能力值；`None` 表示 unknown。
- `source`：来源。
- `reliability`：可靠性。
- `metadata`：诊断元数据。
- `is_known`：`value is not None`。

`CapabilitySource`：`provider_api`、`provider_sdk`、`provider_docs`、`user_config`、`adapter_builtin`、`runtime_observed`、`unknown`。

`CapabilityReliability`：`authoritative`、`declared`、`user_supplied`、`best_effort`、`observed`、`unknown`。

### AdapterCapability

```python
capability = client.get_adapter_capability()
print(capability.generation.supported.value)
print(capability.tools.custom_tools.value)
```

`AdapterCapability` 同时保留 v0.1/v0.2 兼容布尔字段和 v0.3 API family 字段：

- `generation: GenerationCapability`
- `embedding: EmbeddingCapability`
- `resources: ResourceCapability`
- `media_generation: MediaGenerationCapability`
- `tools: ToolCapability`

`GenerationCapability` 字段：

- `supported`
- `streaming`
- `input_modalities`
- `output_modalities`
- `structured_output`
- `reasoning_config`
- `supported_reasoning_efforts`
- `reasoning_output`
- `remote_context`
- `function_tools`
- `metadata`

`EmbeddingCapability` 字段：

- `supported`
- `input_modalities`
- `dense`
- `sparse`
- `dimensions`
- `instructions`
- `metadata`

`ResourceCapability` 字段：

- `file_upload`
- `file_retrieve`
- `file_list`
- `file_delete`
- `preprocessing`
- `metadata`

`MediaGenerationCapability` 字段：

- `image_generation`
- `video_generation`
- `streaming`
- `async_task`
- `output_formats`
- `metadata`

`ToolCapability` 字段：

- `user_function_tools`
- `custom_tools`
- `parallel_tool_calls`
- `tool_choice`
- `metadata`

### ModelCapability

```python
model_capability = client.get_model_capability(
    "gpt-5.1",
    overrides={"supports_streaming": True},
)
```

常用字段：

- `max_context_tokens`
- `max_output_tokens`
- `output_dimensions`
- `supports_streaming`
- `supports_tools`
- `supports_parallel_tool_calls`
- `supports_tool_choice`
- `supports_reasoning_config`
- `supported_reasoning_efforts`
- `supports_reasoning_budget`
- `supports_reasoning_summary`
- `supports_text_embedding`
- `supports_multimodal_embedding`
- `input_modalities`
- `output_modalities`
- `supports_remote_context`
- `supports_sparse_embedding`
- `supports_file_resources`
- `supports_image_generation`
- `supports_video_generation`

用户覆写会被包装为 `CapabilityValue.user_supplied(...)`。

## Usage

`Usage` 统一 token/resource 统计：

```python
usage = response.usage
if usage:
    print(usage.input_tokens, usage.output_tokens, usage.reasoning_tokens)
```

字段：

- `input_tokens`
- `output_tokens`
- `total_tokens`
- `cached_tokens`
- `reasoning_tokens`
- `raw`
- `metadata`

## Errors

错误类位于 `whero.vatbrain.core.errors`：

```python
from whero.vatbrain.core.errors import (
    InvalidItemError,
    ProviderRequestError,
    ProviderResponseMappingError,
    UnsupportedCapabilityError,
    VatbrainError,
)
```

常见错误：

- `InvalidItemError`：item 无法用于目标 API family，或 remote context 覆盖范围非法。
- `UnsupportedCapabilityError`：请求了 adapter 明确不支持的能力。
- `ProviderRequestError`：provider SDK/API 调用失败。
- `ProviderResponseMappingError`：provider 响应无法映射为 vatbrain 模型。
- `StructuredOutputParseError`：structured output 解析失败。

`ProviderRequestError.details` 包含：

- `provider`
- `operation`
- `status_code`
- `request_id`
- `error_type`
- `error_code`
- `error_param`
- `raw`

## OpenAI Adapter 支持范围

当前 OpenAI adapter 支持：

- Responses API generation。
- Responses API streaming。
- JSON Schema structured output。
- Pydantic structured output helper。
- text/image message input 的基础映射。
- user function tool。
- OpenAI custom tool。
- tool call result 回填。
- `previous_response_id` / `store` remote context hint。
- 基于 `covered_item_count` 的 OpenAI previous response 差分传输。
- previous response 失效时的显式 fallback replay。
- provider-native item snapshot replay。
- OpenAI assistant message `phase` 与 `AssistantMessagePhase`。
- text embedding。
- adapter/model capability 查询与用户覆写。

当前 OpenAI adapter 不支持：

- Chat Completions fallback。
- 自动工具执行。
- provider-hosted tools、remote tools、MCP tools 的通用抽象。
- provider conversation 持久化上下文抽象。
- OpenAI 文件资源管理方法。
- 多模态 embedding。
- image/video generation 方法。
- 跨 provider replay。

## Volcengine Adapter 支持范围

当前 Volcengine adapter 支持：

- Ark SDK-only 调用路径。
- Responses API generation。
- Responses API streaming。
- text/image/video/file input。
- JSON Schema structured output。
- Pydantic structured output helper。
- `ReasoningConfig.mode -> thinking.type`。
- `ReasoningConfig.effort -> reasoning.effort`。
- user function tool。
- function call result 回填。
- `previous_response_id` / `store` remote context hint。
- 基于 `covered_item_count` 的 previous response 差分传输。
- previous response 失效时的显式 fallback replay。
- provider-native item snapshot replay。
- Files API upload/retrieve/list/delete/wait。
- 多模态 embedding、instructions、dense/sparse vector。
- adapter/model capability 查询与用户覆写。

当前 Volcengine adapter 不支持：

- OpenAI-compatible SDK surface。
- Chat Completions fallback。
- 停止序列的 normalized 映射。
- 自动工具执行。
- custom tool。
- provider-hosted tools、remote tools、MCP tools 的稳定通用抽象。
- provider conversation 持久化上下文抽象。
- 本地文件隐式上传。
- image/video generation 方法。
- 跨 provider replay。
