# Python API 参考

状态：v0.8
日期：2026-05-13
最近更新：2026-06-12

## 定位

本文是 Python 版本的用户侧 API 参考，覆盖 v0.8 已暴露给用户的主要接口、数据结构和当前 OpenAI / Volcengine / Anthropic / DeepSeek adapter 支持范围。渐进式使用流程见 [quickstart.CN.md](quickstart.CN.md)；Volcengine provider 用法见 [volcengine-quickstart.CN.md](volcengine-quickstart.CN.md)；Anthropic provider 用法见 [anthropic-quickstart.CN.md](anthropic-quickstart.CN.md)；DeepSeek provider 用法见 [deepseek-quickstart.CN.md](deepseek-quickstart.CN.md)；Pydantic structured output 细节见 [user/python/pydantic-structured-output.CN.md](pydantic-structured-output.CN.md)。

`aiflect` 的核心约束：

- 用户显式选择 provider 和 model。
- generation 调用始终以完整 `items` 作为语义上下文。
- provider-side state 只作为优化 hint。
- `aiflect` 不自动执行工具、不自动重试 agent loop、不自动 provider routing。

## 导入方式

常用 core 模型可直接从 `whero.aiflect` 导入：

```python
from whero.aiflect import MessageItem, GenerationConfig, ToolSpec
```

Provider client 从各 provider 包导入：

```python
from whero.aiflect.providers.openai import OpenAIClient
from whero.aiflect.providers.volcengine import VolcengineClient
from whero.aiflect.providers.anthropic import AnthropicClient
from whero.aiflect.providers.deepseek import DeepSeekClient
```

Pydantic structured output helper 从 `whero.aiflect.structured` 导入：

```python
from whero.aiflect.structured import pydantic_output
```

## Client

### ClientConfig

`ClientConfig` 是通用 provider client 初始化配置：

```python
from whero.aiflect import ClientConfig

config = ClientConfig(
    api_key="...",
    base_url="...",
    timeout=30.0,
    max_retries=2,
    provider_options={"default_headers": {"x-trace-id": "demo"}},
    adapter_options={},
)
```

字段：

- `api_key`：provider API key。`ClientConfig` 会将该字段包装为 `SecretString`，避免在 repr 中裸露。
- `base_url`：provider base URL。
- `timeout`：provider SDK 超时配置。
- `max_retries`：provider SDK 重试配置。
- `provider_options`：透传给 provider SDK client 初始化的额外参数。
- `adapter_options`：控制 aiflect provider wrapper 自身行为的字典，不会传给 provider SDK。Core 只保存该字典；具体 key 由各 provider wrapper 自行定义。

### OpenAIClient

当前已实现 provider：OpenAI、Volcengine、Anthropic、DeepSeek。

```python
from whero.aiflect.providers.openai import OpenAIClient

client = OpenAIClient(api_key="...")
```

OpenAI API key 必须在初始化时显式传入，或通过 `ClientConfig(api_key=...)` 提供：

```python
client = OpenAIClient(api_key="...", base_url="...", timeout=30.0)
```

初始化参数：

- `config`：`ClientConfig`。
- `api_key`、`base_url`、`timeout`、`max_retries`：覆盖 `config` 中的同名字段。
- `client`：注入已有同步 OpenAI SDK client，常用于测试或复用连接。
- `async_client`：注入已有异步 OpenAI SDK client。
- `model_capability_overrides`：用户侧模型能力覆写。
- `**openai_client_options`：透传给 OpenAI SDK client 的初始化参数；其中已知 secret 字段会以 `SecretString` 保存。

OpenAI client 方法：

- `generate(...) -> GenerationResponse`
- `agenerate(...) -> GenerationResponse`
- `stream_generate(...) -> Iterator[GenerationStreamEvent]`
- `astream_generate(...) -> AsyncIterator[GenerationStreamEvent]`
- `generate_parsed(...) -> ParsedGenerationResponse`
- `agenerate_parsed(...) -> ParsedGenerationResponse`
- `embed(...) -> EmbeddingResponse`
- `aembed(...) -> EmbeddingResponse`
- `generate_image(...) -> ImageGenerationResponse`
- `agenerate_image(...) -> ImageGenerationResponse`
- `stream_generate_image(...) -> Iterator[ImageGenerationStreamEvent]`
- `astream_generate_image(...) -> AsyncIterator[ImageGenerationStreamEvent]`
- `get_adapter_capability() -> AdapterCapability`
- `get_model_capability(model, overrides=None) -> ModelCapability`

### VolcengineClient

Volcengine provider 使用火山方舟 Ark SDK 原生接口，不使用 OpenAI-compatible SDK surface。

```python
from whero.aiflect.providers.volcengine import VolcengineClient

client = VolcengineClient(api_key="...")
```

Volcengine LLM API key 必须在初始化时显式传入，或通过 `ClientConfig(api_key=...)` 提供：

```python
client = VolcengineClient(api_key="...", base_url="...", timeout=30.0)
```

安装 extra：

```bash
cd python
../.venv/bin/python -m pip install -e ".[volcengine]"
```

初始化参数：

- `config`：`ClientConfig`。
- `api_key`、`base_url`、`timeout`、`max_retries`：覆盖 `config` 中的同名字段。
- `client`：注入已有同步 Ark SDK client，常用于测试或复用连接。
- `async_client`：注入已有异步 Ark SDK client。
- `model_capability_overrides`：用户侧模型能力覆写。
- `**ark_client_options`：透传给 Ark SDK client 的非凭据初始化参数，例如 `region` 等。LLM 凭据统一使用 `api_key` / `ClientConfig.api_key`。

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
- `generate_image(...) -> ImageGenerationResponse`
- `agenerate_image(...) -> ImageGenerationResponse`
- `stream_generate_image(...) -> Iterator[ImageGenerationStreamEvent]`
- `astream_generate_image(...) -> AsyncIterator[ImageGenerationStreamEvent]`
- `create_video_generation_task(...) -> MediaGenerationTask`
- `acreate_video_generation_task(...) -> MediaGenerationTask`
- `get_video_generation_task(task_id, ...) -> MediaGenerationTask`
- `aget_video_generation_task(task_id, ...) -> MediaGenerationTask`
- `wait_for_video_generation_task(task_id, ...) -> MediaGenerationTask`
- `await_video_generation_task(task_id, ...) -> MediaGenerationTask`
- `get_adapter_capability() -> AdapterCapability`
- `get_model_capability(model, overrides=None) -> ModelCapability`

### AnthropicClient

Anthropic provider 使用官方 Anthropic Python SDK 的 Messages API。

```python
from whero.aiflect.providers.anthropic import AnthropicClient

client = AnthropicClient(api_key="...")
```

安装 extra：

```bash
cd python
../.venv/bin/python -m pip install -e ".[anthropic]"
```

Anthropic API key 必须在初始化时显式传入，或通过 `ClientConfig(api_key=...)` 提供：

```python
client = AnthropicClient(api_key="...", base_url="...", timeout=30.0)
```

初始化参数：

- `config`：`ClientConfig`。
- `api_key`、`base_url`、`timeout`、`max_retries`：覆盖 `config` 中的同名字段。
- `client`：注入已有同步 Anthropic SDK client，常用于测试或复用连接。
- `async_client`：注入已有异步 Anthropic SDK client。
- `model_capability_overrides`：用户侧模型能力覆写。
- `**anthropic_client_options`：透传给 Anthropic SDK client 的初始化参数；其中已知 secret 字段会以 `SecretString` 保存。

Anthropic client 方法：

- `generate(...) -> GenerationResponse`
- `agenerate(...) -> GenerationResponse`
- `stream_generate(...) -> Iterator[GenerationStreamEvent]`
- `astream_generate(...) -> AsyncIterator[GenerationStreamEvent]`
- `generate_parsed(...) -> ParsedGenerationResponse`
- `agenerate_parsed(...) -> ParsedGenerationResponse`
- `get_adapter_capability() -> AdapterCapability`
- `get_model_capability(model, overrides=None) -> ModelCapability`

Anthropic adapter 支持文本、图片理解、JSON Schema structured output、Pydantic structured output helper、ReasoningConfig extended thinking、function tools、streaming、async 和 automatic prefix caching。`GenerationConfig.max_output_tokens` 必须设置，或通过 `provider_options["max_tokens"]` 传入 Anthropic 原生参数。

Anthropic adapter 不支持 Files API、embedding、media generation、provider-hosted/server tools、SDK Tool Runner、`ReasoningConfig.include_trace` 或 `reasoning.provider_options`。`ResponseFormat` 会映射为 Anthropic Messages API `output_config.format` JSON Schema。`ReasoningConfig` 会映射为 Anthropic `thinking` 与 `output_config.effort`。`RemoteContextHint.enable_cache=True` 会启用 automatic prompt caching；`session_key` 会被兼容接收但不下发；`new_items_start_index` 会被忽略，不触发差分传输。

### DeepSeekClient

DeepSeek provider 当前使用 DeepSeek Anthropic-compatible Messages API，底层复用 Anthropic Python SDK。

```python
from whero.aiflect.providers.deepseek import DeepSeekClient

client = DeepSeekClient(api_key="...")
```

安装 extra：

```bash
cd python
../.venv/bin/python -m pip install -e ".[deepseek]"
```

DeepSeek API key 必须在初始化时显式传入，或通过 `ClientConfig(api_key=...)` 提供：

```python
client = DeepSeekClient(api_key="...", base_url="...", timeout=30.0)
```

初始化参数：

- `config`：`ClientConfig`。
- `api_key`、`base_url`、`timeout`、`max_retries`：覆盖 `config` 中的同名字段。
- `api_format`：当前支持 `"anthropic"`；`"openai_completion"` 为预留值，初始化时抛 `ValueError`。
- `client`：注入已有同步 Anthropic SDK client，常用于测试或复用连接。
- `async_client`：注入已有异步 Anthropic SDK client。
- `model_capability_overrides`：用户侧模型能力覆写。
- `**deepseek_client_options`：透传给 Anthropic SDK client 的初始化参数；其中已知 secret 字段会以 `SecretString` 保存。

DeepSeek client 方法：

- `generate(...) -> GenerationResponse`
- `agenerate(...) -> GenerationResponse`
- `stream_generate(...) -> Iterator[GenerationStreamEvent]`
- `astream_generate(...) -> AsyncIterator[GenerationStreamEvent]`
- `get_adapter_capability() -> AdapterCapability`
- `get_model_capability(model, overrides=None) -> ModelCapability`

DeepSeek adapter 支持文本生成、streaming、async、function tools、`ReasoningConfig.mode` / `ReasoningConfig.effort` 和 usage 映射。`GenerationConfig.max_output_tokens` 必须设置，或通过 `provider_options["max_tokens"]` 传入 Anthropic-compatible 原生参数。

DeepSeek adapter 不支持 image/document/file/audio/video input、structured output、Pydantic parsed convenience、Files API、embedding、media generation、custom tools、explicit `cache_control` 或可靠禁用 parallel tool calls。`RemoteContextHint.enable_cache=True` 与 `session_key` 会被兼容接收但不下发 cache control 或 session 参数；`new_items_start_index` 会被忽略，不触发差分传输。

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
from whero.aiflect import MessageItem, TextPart, ImagePart

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
from whero.aiflect import AssistantMessagePhase, MessageItem

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
from whero.aiflect import AudioPart, FilePart, VideoPart

AudioPart(url="https://example.test/audio.mp3", mime_type="audio/mpeg")
VideoPart(file_id="file_video_123", provider="volcengine")
FilePart(local_path="./contract.pdf", mime_type="application/pdf")
```

`local_path` 只是 metadata，不会自动读取或上传文件。需要 provider 文件资源时，应使用对应 provider adapter 的显式 file/resource API。OpenAI adapter 尚未暴露文件管理方法；Volcengine adapter 已支持 Ark Files API。

Anthropic adapter 仅在 generation 中支持 `TextPart` 与 user message 中的 `ImagePart`。`AudioPart`、`VideoPart`、`FilePart` 不会映射到 Anthropic Messages API。

### FunctionCallItem

`FunctionCallItem` 是模型请求调用用户工具的输出项：

```python
from whero.aiflect import FunctionCallItem

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
from whero.aiflect import FunctionResultItem

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
from whero.aiflect import ReasoningItem

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
from whero.aiflect import provider_snapshot_for, provider_snapshot_key

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
- `remote_context`：provider-side cache/delta hint。
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
from whero.aiflect import GenerationRequest, MessageItem

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
from whero.aiflect import GenerationConfig

config = GenerationConfig(
    temperature=0.2,
    top_p=0.9,
    max_output_tokens=300,
)
```

### ResponseFormat

`ResponseFormat` 只表达 JSON Schema structured output，不兼容 JSON mode / `json_object`：

```python
from whero.aiflect import ResponseFormat

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
from whero.aiflect import ReasoningConfig

reasoning = ReasoningConfig(
    mode="auto",
    effort="low",
    budget_tokens=1024,
    summary="auto",
    include_trace=False,
    provider_options={},
)
```

不同 provider 对 `effort` 的取值和语义可能不同。支持的 effort 应通过 capability 查询。Volcengine adapter 将 `mode` 映射为 Ark `thinking.type`，将 `effort` 映射为 `reasoning.effort`。DeepSeek adapter 将 `mode="enabled"/"auto"` 映射为 `thinking={"type": "enabled"}`，将 `mode="disabled"/"none"` 映射为 `thinking={"type": "disabled"}`，将 `effort="high"/"max"` 映射为 `output_config.effort`。Anthropic adapter 将 `mode="disabled"/"none"` 映射为 `thinking={"type": "disabled"}`，将 `budget_tokens` 映射为 manual `thinking={"type": "enabled", "budget_tokens": ...}`，将 `mode="auto"/"enabled"/"adaptive"` 映射为 `thinking={"type": "adaptive"}`，并将 `effort` 映射为 `output_config.effort`。Anthropic adapter 暂不支持 `include_trace` 或 `reasoning.provider_options`。Provider 返回的 thinking content block 会尽量映射为 `ReasoningItem`。

### ToolCallConfig

```python
from whero.aiflect import ToolCallConfig, ToolChoice

tool_call_config = ToolCallConfig(
    parallel_tool_calls=False,
    tool_choice=ToolChoice.AUTO,
)
```

`tool_choice` 也可以传 provider 原生 dict；只有具备跨 provider 语义的配置才建议进入通用字段。

### RemoteContextHint

`RemoteContextHint` 表达 provider-side cache/delta 优化 hint：

```python
from whero.aiflect import RemoteContextHint

remote_context = RemoteContextHint(
    enable_cache=True,
    session_key="chat-thread-42",
    new_items_start_index=4,
)
```

字段：

- `enable_cache`：是否启用 provider-side cache/stored response 优化。
- `session_key`：可选的多轮 session/cache pool 稳定标识。建议使用业务 session id 的 hash 或其他非敏感稳定字符串。
- `new_items_start_index`：完整 `items` 中新增 item 的起始 index。
- `provider_options`：provider-specific remote context 参数。

用户仍必须传入完整 `items`。OpenAI/Volcengine adapter 在 `enable_cache=True` 且边界前一个 item 的 provider snapshot metadata 中存在 response id 时，只向 provider 发送新增 suffix；如果 response id 缺失或失效，则会重新使用完整 `items`。`session_key` 在 OpenAI adapter 中映射为 `prompt_cache_key`；在 Volcengine adapter 中启用 adapter-managed Responses API Session cache，自动设置 `caching={"type":"enabled"}` 与 1 小时 `expire_at`。Anthropic adapter 忽略 `new_items_start_index`，只在 `enable_cache=True` 时启用 automatic prompt caching；`session_key` 当前兼容接收但不下发。DeepSeek adapter 兼容接收 `RemoteContextHint`，但不下发 `cache_control`，也不做差分传输。

如果通过路由商、网关或 OpenAI-compatible 服务间接调用 OpenAI Responses API，且目标服务的 `previous_response_id` / stored response 链接能力不稳定，可以在 OpenAI client 初始化时关闭 OpenAI adapter 的自动 response delta 传输：

```python
from whero.aiflect import ClientConfig
from whero.aiflect.providers.openai import OpenAIClient

client = OpenAIClient(
    config=ClientConfig(
        api_key="...",
        adapter_options={
            "remote_context": {
                "response_delta": False,
            },
        },
    ),
)
```

关闭后，用户代码仍可继续传入 `RemoteContextHint(enable_cache=True, session_key=..., new_items_start_index=...)`；OpenAI adapter 会发送完整 `items`，不发送 `previous_response_id`，但仍保留 `store=True` 与 `prompt_cache_key` 等 cache/session 参数。该 `adapter_options` key 当前只由 OpenAI adapter 识别；其他 provider wrapper 不保证识别或复用同名 key。

OpenAI/Volcengine 非流式 generation 会在 `GenerationResponse.metadata["remote_context"]` 中记录 response-style remote context 的请求路径。常见字段包括：

- `api_family`: `"responses"`。
- `cache_enabled`: 本次 request 是否启用 cache。
- `session_cache_enabled`: 本次 request 是否启用了通用 `session_key` 对应的 session/cache pool 策略。
- `session_key_present`: 请求中是否提供了 `session_key`；metadata 不包含原始 key。
- `attempted_previous_response_id`: 初始请求是否携带 `previous_response_id`。
- `final_request_used_previous_response_id`: 最终成功的请求是否携带 `previous_response_id`。
- `refreshed_after_invalid_context`: 是否因 previous response/context invalid 或 expired 自动 refresh。
- `refreshed_before_expiry`: Volcengine session cache 中，是否因为 anchor response 即将过期而主动改用完整 `items`。
- `previous_response_expire_at`: Volcengine anchor response 的过期时间戳，若 adapter 可从 snapshot 中取得。
- `new_items_start_index`: 请求中提供的新增 item 起始位置。

OpenAI adapter 额外记录：

- `response_delta_mode`: 本次 response delta 策略，当前为 `"auto"` 或 `"disabled"`。
- `response_delta_disabled_by_adapter_options`: 是否因 `ClientConfig.adapter_options` 主动禁用了 response delta。

当 `attempted_previous_response_id=True`、`final_request_used_previous_response_id=True` 且 `refreshed_after_invalid_context=False` 时，可以确认该次 response-style 请求直接使用 previous response 成功，而不是通过 full-context refresh 兜底成功。

### ReplayPolicy

```python
from whero.aiflect import ReplayPolicy

policy = ReplayPolicy(
    mode="prefer_provider_native",
)
```

`mode`：

- `normalized_only`：只用 normalized mapper。
- `prefer_provider_native`：有 provider snapshot 时优先使用，缺失时降级。
- `require_provider_native`：强制使用 snapshot，缺失即报错。

`cross_provider` 当前只支持 `unsupported`。

### Streaming

`StreamOptions` 当前只有 `include_usage`：

```python
from whero.aiflect import StreamOptions

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
from whero.aiflect.core.generation import StreamEventType

if event.type == StreamEventType.TEXT_DELTA.value:
    ...
```

使用 `GenerationStreamAccumulator` 可从流式事件重建最终响应：

```python
from whero.aiflect import GenerationStreamAccumulator

accumulator = GenerationStreamAccumulator(provider="openai")
for event in client.stream_generate(model="gpt-5.1", items=[MessageItem.user("Hi")]):
    accumulator.add(event)

response = accumulator.to_response()
```

## Tools

`ToolSpec` 是 `FunctionToolSpec` 的兼容别名。当前通用 core 只覆盖用户代码执行的 function/custom tool。

### Function Tool

```python
from whero.aiflect import ToolSpec

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
from whero.aiflect.structured import pydantic_output

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

OpenAI、Volcengine 与 Anthropic client 提供薄封装：

```python
parsed = client.generate_parsed(
    model="gpt-5.1",
    items=[MessageItem.user("Extract a contact.")],
    output_type=Contact,
)
```

`generate_parsed()` / `agenerate_parsed()` 使用默认 Pydantic helper 行为；如需自定义 schema name、description 或 strict，请显式使用 `pydantic_output()` + `generate()`。

Anthropic adapter 不调用 Anthropic SDK `messages.parse()`；它会把 `ResponseFormat` 映射为 `output_config.format`，最终仍由 `pydantic_output()` 解析 assistant text。Anthropic JSON outputs 与 assistant message prefill 不兼容；请求携带 `ResponseFormat` 时最后一条消息不能是 assistant prefill。

DeepSeek adapter 当前不支持 `ResponseFormat`，也不提供 `generate_parsed()` / `agenerate_parsed()`。

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
from whero.aiflect import EmbeddingInput, ImagePart, MessageItem, TextPart

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
from whero.aiflect import EmbeddingRequest

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
from whero.aiflect import SparseEmbedding, EmbeddingVector

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

Volcengine 多模态 embedding 每次 request 只提交一个 `EmbeddingInput`；该 input 内部可以混合 text/image/video parts。Ark API 一次返回一个向量，如需多个样本，请在用户代码中循环调用。`sparse_embedding=True/False` 映射为 Ark `sparse_embedding.type`，仅支持纯文本输入；包含图片或视频时 adapter 会拒绝该配置。

## Resources

v0.3 已定义 resource/file core 模型。OpenAI adapter 尚未暴露文件资源方法；Volcengine adapter 已实现 Ark Files API。

### FileUploadRequest

```python
from whero.aiflect import FilePreprocessConfig, FileUploadRequest

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
from whero.aiflect import FilePreprocessConfig

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
from whero.aiflect import FileResource, FileStatus

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

Media generation 是独立 API family，不复用 `GenerationRequest` 或 `ToolSpec`。v0.5 已实现 OpenAI 直接 Images API、Volcengine Ark Images API，以及 Volcengine Ark Content Generation 视频任务。

### MediaArtifact

```python
from whero.aiflect import MediaArtifact, MediaKind

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
from whero.aiflect import ImageGenerationRequest

request = ImageGenerationRequest(
    model="image-model",
    prompt="A product photo on a clean desk.",
    quality="high",
    background="transparent",
    output_format="png",
    response_format="url",
    count=1,
    watermark=True,
)
```

`ImageGenerationResponse` 包含：

- `provider`
- `model`
- `artifacts`
- `usage`
- `metadata`
- `raw`

`ImageGenerationRequest` 不包含 `tools`。Media generation 不复用 generation/function calling 的 `ToolSpec`；provider-native 媒体生成开关通过 `provider_options` 显式传递。OpenAI adapter 只覆盖直接 Images API，不覆盖通过 GPT/Responses 内置 image generation tool 的间接路径；是否存在参考图由 OpenAI adapter 自动路由到 `images.generate` 或 `images.edit`。

字段说明：

- `model`：provider model id。
- `prompt`：图片生成提示词。
- `input_items`：参考图片上下文；OpenAI adapter 根据是否存在参考图选择 `images.generate` 或 `images.edit`，Volcengine adapter 映射为 Ark `images.generate` 的 `image` 参数。
- `quality`：图片质量控制。OpenAI adapter 发送给 Images API；Volcengine adapter 当前忽略，因为 Ark Images API 没有等价字段。
- `background`：背景控制。OpenAI adapter 支持 `auto`、`transparent`、`opaque`；Volcengine adapter 当前忽略。能力可通过 `MediaGenerationCapability.image_background_control` 和 `image_background_values` 查询。
- `output_format`：输出文件格式，例如 `png`、`jpeg`、`webp`；具体 provider/model 支持范围以 capability 和 provider 文档为准。
- `response_format`：返回形态，例如 `url` 或 `b64_json`。
- `count`：期望生成数量。OpenAI 映射为 `n`；Volcengine 映射为 Ark `sequential_image_generation_options.max_images`，通常需配合 `provider_options={"sequential_image_generation": "auto"}` 使用组图能力。
- `watermark`：是否要求 provider 添加 AI 水印，默认 `True`。
- `stream_options`：保留的通用流式选项；图片生成当前不映射 provider-native stream options。
- `provider_options`：provider-native 参数。OpenAI 可传 `moderation`、`output_compression`、`partial_images`、`user` 等；Volcengine 可传 `size`、`sequential_image_generation`、`sequential_image_generation_options`、`optimize_prompt_options`、`seed` 等 Ark 参数。

`watermark` 用于表达是否要求 provider 添加 AI 水印，默认 `True`。若 provider 或模型没有可控水印能力，adapter 会忽略该参数；OpenAI Images API 当前不会接收该参数。

`ImageGenerationRequest` 也不包含 normalized `size` 字段。图片生成默认采用 auto 模式，由模型从 prompt 中感知分辨率、长宽比和构图规格；如果必须使用 provider 原生分辨率控制，应通过 `provider_options` 明确传递。

`ImageGenerationStreamEvent` 用于表达图片生成流式事件，字段包括 `type`、`sequence`、`provider`、`task_id`、`artifact`、`delta`、`usage`、`error`、`metadata`、`raw_event`。

OpenAI 图片生成：

```python
response = client.generate_image(
    model="gpt-image-1",
    prompt="A product photo on a clean desk.",
    output_format="png",
    response_format="b64_json",
)
```

OpenAI 参考图生成仍使用同一个入口。存在 `ImagePart(data=...)` 时，adapter 自动调用 `images.edit`：

```python
from whero.aiflect import ImagePart, MessageItem

response = client.generate_image(
    model="gpt-image-1",
    prompt="Restyle this product photo.",
    input_items=[
        MessageItem.user([
            ImagePart(data="data:image/png;base64,..."),
        ])
    ],
)
```

OpenAI adapter 不会隐式下载 `ImagePart(url=...)` 作为 edit 输入。需要参考图时应提供显式图片内容。

Volcengine 图片生成同样使用 `generate_image()`；纯文本生成与参考图生成都映射到 Ark SDK 原生 `images.generate`：

```python
response = client.generate_image(
    model="doubao-seedream-5-0-260128",
    prompt="A product photo on a clean desk.",
    input_items=[
        MessageItem.user([
            ImagePart(url="https://example.test/reference.png"),
        ])
    ],
    response_format="url",
    watermark=False,
)
```

图片流式生成：

```python
for event in client.stream_generate_image(
    model="gpt-image-1",
    prompt="A cinematic product photo.",
    provider_options={"partial_images": 2},
):
    if event.artifact:
        print(event.type, event.artifact.url or event.artifact.data)
```

异步入口为 `agenerate_image()` 与 `astream_generate_image()`。

### VideoGenerationRequest

`VideoGenerationRequest` 表达视频生成任务。当前由 Volcengine adapter 实现；OpenAI adapter v0.5 不暴露视频生成方法。

字段：

- `model`
- `prompt`
- `input_items`
- `duration_seconds`
- `ratio`
- `resolution`
- `generate_audio`
- `watermark`
- `stream_options`
- `provider_options`

字段说明：

- `model`：provider model id。
- `prompt`：视频生成提示词；Volcengine adapter 会作为 `content` 的首个 text part 发送。
- `input_items`：参考图片、视频、音频、文件或补充文本。它是 media reference context，不是对话历史。
- `duration_seconds`：目标时长，Volcengine 映射为 `duration`。Ark 要求整数秒；adapter 当前会转换为 `int`。
- `ratio`：视频宽高比，例如 `16:9`、`4:3`、`1:1`、`3:4`、`9:16`、`21:9`、`adaptive`。
- `resolution`：输出分辨率，例如 `480p`、`720p`、`1080p`；不同 Volcengine 模型支持范围不同。
- `generate_audio`：是否生成与画面同步的声音。
- `watermark`：是否要求 provider 添加 AI 水印，默认 `True`。
- `stream_options`：保留字段；当前视频生成走异步任务，不映射为 provider stream 参数。
- `provider_options`：provider-native 参数。Volcengine 可传 `seed`、`frames`、`return_last_frame`、`callback_url`、`service_tier`、`execution_expires_after`、`draft`、`priority`、`safety_identifier` 等 Ark task create 参数。

`input_items` 可携带参考图片、视频、音频或文件。Volcengine adapter 支持 `ImagePart(url/data)`、`VideoPart(url/data)`、`AudioPart(url/data)`，以及带 image/video/audio `media_type` 或 `mime_type` 的 `FilePart(url/data)`。`file_id` 与 `local_path` 不会被隐式上传或读取。若需要指定参考素材 role，可在 part metadata 中传入 `role`，例如 `first_frame`、`last_frame`、`reference_image`、`reference_video`。

`watermark` 用于表达是否要求 provider 添加 AI 水印，默认 `True`。若 provider 或模型没有可控水印能力，adapter 会忽略该参数。

### MediaGenerationTask

```python
from whero.aiflect import ImagePart, MediaGenerationTask, MessageItem, TaskStatus, VideoGenerationRequest

request = VideoGenerationRequest(
    model="video-model",
    prompt="A short cinematic clip.",
    input_items=[
        MessageItem.user([
            ImagePart(
                url="https://example.test/first-frame.png",
                metadata={"role": "first_frame"},
            ),
        ])
    ],
    duration_seconds=8,
    ratio="16:9",
    watermark=True,
)

task = MediaGenerationTask(
    id="task_123",
    provider="volcengine",
    model="video-model",
    status=TaskStatus.RUNNING,
)
```

`TaskStatus`：`queued`、`running`、`completed`、`failed`、`canceled`、`expired`、`unknown`。

Volcengine client 暴露视频任务方法：

```python
task = client.create_video_generation_task(
    model="doubao-seedance-2-0-260128",
    prompt="A short cinematic clip.",
    input_items=request.input_items,
    duration_seconds=8,
    ratio="16:9",
    generate_audio=True,
    watermark=False,
)

task = client.get_video_generation_task(task.id, provider_options={})
task = client.wait_for_video_generation_task(
    task.id,
    poll_interval=10.0,
    max_wait_seconds=600.0,
    provider_options={},
)
```

`get_video_generation_task()` / `aget_video_generation_task()` 的 `provider_options` 会透传给 Ark task get。`wait_for_video_generation_task()` / `await_video_generation_task()` 会轮询到终态：`completed`、`failed`、`canceled` 或 `expired`；`poll_interval` 控制轮询间隔，`max_wait_seconds` 控制最大等待时间，超时会抛 `TimeoutError`。OpenAI adapter v0.5 不暴露视频生成方法。

## Capability

Capability 用于描述 adapter/model 已知能力及其来源，不是内部权威模型库。

### CapabilityValue

```python
from whero.aiflect import CapabilityValue

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
- `image_background_control`
- `image_background_values`
- `metadata`

`image_background_values` 当前使用 OpenAI Images API 的背景枚举：

- `auto`：由模型/provider 自动选择背景模式。
- `transparent`：请求透明背景，通常需要支持透明通道的输出格式。
- `opaque`：请求不透明背景。

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
- `supports_structured_output`
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

错误类位于 `whero.aiflect.core.errors`：

```python
from whero.aiflect.core.errors import (
    InvalidItemError,
    ProviderRequestError,
    ProviderResponseMappingError,
    UnsupportedCapabilityError,
    AiflectError,
)
```

常见错误：

- `InvalidItemError`：item 无法用于目标 API family，或 remote context 覆盖范围非法。
- `UnsupportedCapabilityError`：请求了 adapter 明确不支持的能力。
- `ProviderRequestError`：provider SDK/API 调用失败。
- `ProviderResponseMappingError`：provider 响应无法映射为 aiflect 模型。
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
- `RemoteContextHint.enable_cache/new_items_start_index` remote context hint。
- `RemoteContextHint.session_key` 映射为 Responses API `prompt_cache_key`。
- 基于 snapshot response id 与新增边界的 OpenAI previous response 差分传输。
- `ClientConfig.adapter_options["remote_context"]["response_delta"] = False` 可关闭 OpenAI previous response 差分传输。
- previous response 失效时的自动 full-context refresh。
- provider-native item snapshot replay。
- OpenAI assistant message `phase` 与 `AssistantMessagePhase`。
- text embedding。
- Images API 图片生成、参考图生成与图片流式生成。
- adapter/model capability 查询与用户覆写。

当前 OpenAI adapter 不支持：

- Chat Completions fallback。
- 自动工具执行。
- provider-hosted tools、remote tools、MCP tools 的通用抽象。
- provider conversation 持久化上下文抽象。
- OpenAI 文件资源管理方法。
- 多模态 embedding。
- video generation 方法。
- OpenAI image variation API。
- 通过 Responses API hosted image generation tool 间接生成图片。
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
- `RemoteContextHint.enable_cache/new_items_start_index` remote context hint。
- `RemoteContextHint.session_key` 启用 adapter-managed Responses API Session cache，固定 1 小时 `expire_at`，并在 previous response 接近过期时自动 full-context refresh。
- 基于 snapshot response id 与新增边界的 previous response 差分传输。
- previous response 失效时的自动 full-context refresh。
- provider-native item snapshot replay。
- Files API upload/retrieve/list/delete/wait。
- 多模态 embedding、instructions、dense/sparse vector。
- Ark Images API 图片生成、参考图生成与图片流式生成。
- Ark Content Generation 视频任务创建、查询与轮询。
- adapter/model capability 查询与用户覆写。

当前 Volcengine adapter 不支持：

- OpenAI-compatible SDK surface。
- Chat Completions fallback。
- 停止序列的 normalized 映射。
- 自动工具执行。
- custom tool。
- provider-hosted tools、remote tools、MCP tools 的稳定通用抽象。
- provider conversation 持久化上下文抽象。
- 自定义 generation `expire_at`；Volcengine session cache 生命周期由 adapter 固定为 1 小时。
- 本地文件隐式上传。
- 跨 provider replay。

## Anthropic Adapter 支持范围

当前 Anthropic adapter 支持：

- 官方 Anthropic SDK Messages API 调用路径。
- Messages API generation。
- Messages API streaming。
- async generation / streaming。
- text/image input。
- initial system/developer instruction prefix 映射为 Anthropic top-level `system`。
- user function tool。
- `tool_use` -> `FunctionCallItem`。
- `FunctionResultItem` -> `tool_result`。
- JSON Schema structured output。
- Pydantic structured output helper。
- `ReasoningConfig` 请求映射：
  - `mode disabled/none` -> `thinking={"type": "disabled"}`。
  - `budget_tokens` -> `thinking={"type": "enabled", "budget_tokens": ...}`。
  - `mode auto/enabled/adaptive` -> `thinking={"type": "adaptive"}`。
  - `effort low/medium/high/max/xhigh` -> `output_config.effort`。
- `RemoteContextHint.enable_cache=True` 映射为 automatic prefix caching。
- `RemoteContextHint.session_key` 兼容接收但不下发。
- `new_items_start_index` 兼容接收但忽略。
- provider-native content block snapshot replay。
- usage cache token mapping。
- adapter/model capability 查询与用户覆写。

当前 Anthropic adapter 不支持：

- Files API。
- embedding。
- media generation。
- previous response 差分传输。
- response-style remote context refresh。
- `ReasoningConfig.include_trace` 或 `reasoning.provider_options`。
- `FunctionToolType.CUSTOM`。
- 显式 Anthropic `cache_control`。
- 显式 Anthropic `output_config` / 旧 beta `output_format`。
- structured output 与 assistant message prefill 同用。
- provider-hosted/server tools、web search、code execution、MCP 或 SDK Tool Runner。
- provider conversation 持久化上下文抽象。
- 跨 provider replay。

## DeepSeek Adapter 支持范围

当前 DeepSeek adapter 支持：

- DeepSeek Anthropic-compatible Messages API 调用路径。
- `api_format="anthropic"`。
- 默认 base URL：`https://api.deepseek.com/anthropic`。
- Messages API generation。
- Messages API streaming。
- async generation / streaming。
- text-only input。
- initial system/developer instruction prefix 映射为 top-level `system`。
- user function tool。
- `tool_use` -> `FunctionCallItem`。
- `FunctionResultItem` -> `tool_result`。
- `ReasoningConfig.mode enabled/auto` -> `thinking={"type": "enabled"}`。
- `ReasoningConfig.mode disabled/none` -> `thinking={"type": "disabled"}`。
- `ReasoningConfig.effort high/max` -> `output_config.effort`。
- `RemoteContextHint.enable_cache=True` 兼容接收但不下发 cache control。
- `RemoteContextHint.session_key` 兼容接收但不下发。
- `new_items_start_index` 兼容接收但忽略。
- provider-native content block snapshot replay。
- usage cache token mapping。
- adapter/model capability 查询与用户覆写。

当前 DeepSeek adapter 不支持：

- `api_format="openai_completion"`。
- image/document/file/audio/video input。
- Files API。
- embedding。
- media generation。
- previous response 差分传输。
- response-style remote context refresh。
- `ResponseFormat` structured output。
- Pydantic parsed convenience。
- `FunctionToolType.CUSTOM`。
- 显式 Anthropic `cache_control`。
- 显式 `output_format` / `output_config.format`。
- 可靠禁用 parallel tool calls。
- provider-hosted/server tools、web search、code execution、MCP 或 SDK Tool Runner。
- provider conversation 持久化上下文抽象。
- 跨 provider replay。
