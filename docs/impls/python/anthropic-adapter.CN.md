# Python Anthropic Adapter 实现方案

状态：已实现
日期：2026-06-05
最近更新：2026-06-07

## 定位

本文记录 Python 参考实现新增 Anthropic provider adapter 的实现方案。需求状态见 [REQ-2026-06-python-anthropic-adapter.CN.md](../../requirements/REQ-2026-06-python-anthropic-adapter.CN.md)、[REQ-2026-06-python-anthropic-structured-output.CN.md](../../requirements/REQ-2026-06-python-anthropic-structured-output.CN.md) 与 [REQ-2026-06-python-anthropic-reasoning.CN.md](../../requirements/REQ-2026-06-python-anthropic-reasoning.CN.md)，高层设计见 [anthropic-provider-support.CN.md](../../design/anthropic-provider-support.CN.md)。

Anthropic adapter 是 generation-only provider adapter。它使用官方 Anthropic Python SDK 的 Messages API，不实现 Files API、embedding 或 media generation。

## 实现记录

已完成：

- `whero.vatbrain.providers.anthropic.AnthropicClient`。
- `anthropic` optional dependency。
- `to_anthropic_generation_params()` 与 `from_anthropic_generation_response()`。
- `from_anthropic_stream_event()`。
- `ResponseFormat` structured output 请求映射。
- `ReasoningConfig` extended thinking 请求映射。
- `generate_parsed()` / `agenerate_parsed()`。
- Anthropic adapter/model capability。
- 单元测试覆盖 mapper、stream、client 和 capability。

实现决策：

- `ResponseFormat` 映射为 Anthropic Messages API `output_config.format` JSON Schema，不调用 Anthropic SDK `messages.parse()`。
- `ReasoningConfig` 映射为 Anthropic Messages API `thinking` 与 `output_config.effort`；`output_config` 由 adapter 合并 structured output format 与 reasoning effort。
- `RemoteContextHint.enable_cache=True` 映射为 top-level `cache_control={"type": "ephemeral"}`。
- `new_items_start_index` 兼容接收但忽略，不做差分传输。
- 用户显式传入 `cache_control` 会被拒绝，避免形成 explicit cache control 隐式入口。
- 用户显式传入 `output_config` 或旧 beta `output_format` 会被拒绝，避免绕过 `ResponseFormat`。

## 依赖与包结构

`python/pyproject.toml` 新增 optional dependency：

```toml
[project.optional-dependencies]
anthropic = [
    "anthropic>=0.105.2,<1",
]
```

新增 provider package：

```text
python/whero/vatbrain/providers/anthropic/
- __init__.py
- client.py
- mapper.py
- stream.py
- capabilities.py
```

Provider identity：

```text
PROVIDER = "anthropic"
API_FAMILY = "messages"
```

## Client

`AnthropicClient` 与 OpenAI/Volcengine client 保持形状一致：

```python
class AnthropicClient:
    provider = "anthropic"

    def generate(...) -> GenerationResponse: ...
    async def agenerate(...) -> GenerationResponse: ...
    def stream_generate(...) -> Iterator[GenerationStreamEvent]: ...
    async def astream_generate(...) -> AsyncIterator[GenerationStreamEvent]: ...
    def generate_parsed(...) -> ParsedGenerationResponse: ...
    async def agenerate_parsed(...) -> ParsedGenerationResponse: ...
    def get_adapter_capability() -> AdapterCapability: ...
    def get_model_capability(model, overrides=None) -> ModelCapability: ...
```

`generate_parsed()` / `agenerate_parsed()` 与 OpenAI/Volcengine client 一样是薄封装：使用 `pydantic_output(output_type)` 生成 `ResponseFormat`，调用现有 `generate()` / `agenerate()`，再解析最终 assistant text。

初始化参数：

- `config: ClientConfig | None`
- `api_key: str | SecretString | None`
- `base_url: str | None`
- `timeout: float | None`
- `max_retries: int | None`
- `client: Any | None`
- `async_client: Any | None`
- `model_capability_overrides`
- `**anthropic_client_options`

凭据规则沿用现有 provider：

- 未注入 SDK client 时，必须显式传入 `api_key` 或 `ClientConfig.api_key`。
- 不从环境变量自动读取。
- 使用 `SecretString` 存储凭据。

SDK 初始化：

```python
from anthropic import Anthropic, AsyncAnthropic
```

## Request Mapping

入口：

```python
def to_anthropic_generation_params(
    request: GenerationRequest,
    *,
    stream: bool = False,
) -> dict[str, Any]:
    ...
```

Anthropic adapter 不需要 `use_remote_context` 参数，因为它不支持 response-style previous response 差分传输。

### 基本参数

```text
GenerationRequest.model -> model
GenerationConfig.max_output_tokens -> max_tokens
GenerationConfig.temperature -> temperature
GenerationConfig.top_p -> top_p
provider_options -> top-level Anthropic request params, except adapter-owned cache fields
stream=True -> stream=True
```

Anthropic Messages API 要求 `max_tokens`。MVP 建议如果 `GenerationConfig.max_output_tokens` 缺失且 `provider_options` 中没有 `max_tokens`，mapper 抛出 `InvalidItemError`。

`cache_control` 是 Anthropic adapter 保留字段。用户不能通过 `GenerationRequest.provider_options`、`RemoteContextHint.provider_options` 或 tool `provider_options` 显式设置 `cache_control`；遇到该字段时抛 `UnsupportedCapabilityError`，避免形成 explicit cache control 的隐式后门。

`output_config` 与旧 beta `output_format` 也是 Anthropic adapter 保留字段。用户不能通过 `GenerationRequest.provider_options` 或 `RemoteContextHint.provider_options` 显式设置；structured output 应通过 `ResponseFormat` 进入 adapter。

### RemoteContextHint 与 Cache

Anthropic mapper 只使用 `RemoteContextHint.enable_cache`：

```python
if request.remote_context and request.remote_context.enable_cache is True:
    params["cache_control"] = {"type": "ephemeral"}
```

不映射：

- `new_items_start_index`
- `RemoteContextHint.provider_options`

即使存在 `new_items_start_index`，也始终使用完整 `request.items` 构造 Anthropic messages。

### Messages 与 System

初始 `MessageItem.system` 和 `MessageItem.developer` 映射到 Anthropic top-level `system`。

建议策略：

- 在首个非 system/developer item 之前出现的 system/developer item，合并为 top-level `system` content blocks。
- `MessageItem.developer` 在 Anthropic 中没有独立 authority 层，MVP 按 system instruction 处理，并在文档中标记为有损映射。
- 中途出现的 system/developer item 默认抛出 `InvalidItemError`，避免改变上下文顺序或隐式降低/提升指令层级。

普通消息：

```text
MessageItem.user -> {"role": "user", "content": ...}
MessageItem.assistant -> {"role": "assistant", "content": ...}
```

Content part：

```text
TextPart -> {"type": "text", "text": text}
ImagePart(url=...) -> {"type": "image", "source": {"type": "url", "url": url}}
ImagePart(data=...) -> {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": data}}
```

`ImagePart.data` 若是 data URL，mapper 应解析 media type 和 base64 body；若是裸 base64，要求 `mime_type`，或按实现约定默认 `image/png` 并在文档中说明。

Unsupported parts：

- `AudioPart`
- `VideoPart`
- `FilePart`

这些在 MVP 中抛 `InvalidItemError`。Anthropic Files API 不进入范围。

### Tool Mapping

`FunctionToolSpec(type="function")` 映射为 Anthropic client tool：

```text
name -> name
description -> description
parameters_schema -> input_schema
provider_options -> merge non-cache provider-specific fields into tool payload
```

如果 tool `provider_options` 中包含 `cache_control`，MVP 抛 `UnsupportedCapabilityError`。Anthropic explicit tool cache breakpoint 暂不暴露。

`FunctionToolType.CUSTOM` 暂不支持，抛 `UnsupportedCapabilityError`。

`ToolCallConfig.tool_choice`：

```text
ToolChoice.AUTO -> {"type": "auto"}
ToolChoice.NONE -> {"type": "none"}
ToolChoice.REQUIRED -> {"type": "any"}
dict -> 原样透传
```

`ToolCallConfig.parallel_tool_calls=False`：

- 如果已有 tool_choice dict，在其中写入 `disable_parallel_tool_use=True`。
- 如果没有 tool_choice，则生成 `{"type": "auto", "disable_parallel_tool_use": True}`。

`FunctionCallItem` 重放为 assistant message content block：

```text
type="tool_use"
id=call_id
name=name
input=json.loads(arguments)
```

如果 `arguments` 不是合法 JSON object，抛 `InvalidItemError`。

`FunctionResultItem` 映射为 user message content block：

```text
type="tool_result"
tool_use_id=call_id
content=output
is_error=metadata["is_error"] if present
```

mapper 需要把连续的 tool result 与后续 user text 组织为同一个 user message，确保 `tool_result` block 在该 message 的 text block 前面。

### Reasoning 与 Structured Output

`ReasoningConfig` 支持 Anthropic extended thinking 请求映射。Provider 返回的 `thinking` / `redacted_thinking` content block 会尽量映射为 `ReasoningItem`。

请求映射：

```text
ReasoningConfig(mode="disabled"|"none")
  -> thinking={"type": "disabled"}

ReasoningConfig(budget_tokens=1024)
  -> thinking={"type": "enabled", "budget_tokens": 1024}

ReasoningConfig(mode="auto"|"enabled"|"adaptive")
  -> thinking={"type": "adaptive"}

ReasoningConfig(effort="high")
  -> output_config.effort = "high"
```

`summary="auto"` / `"summarized"` 映射为 `thinking.display="summarized"`；`summary="none"` / `"omitted"` 映射为 `thinking.display="omitted"`。`include_trace` 与 `reasoning.provider_options` 暂不支持。

校验规则：

- active thinking 与 assistant message prefill 不兼容。
- active thinking 与 `temperature`、`top_k` 和 forced `tool_choice` 不兼容。
- active thinking 下 `top_p` 如显式设置，必须在 `0.95` 到 `1.0` 之间。
- manual `budget_tokens` 必须为整数、至少 1024，且小于最终 `max_tokens`。

`ResponseFormat` 支持 JSON Schema structured output，并映射为 Anthropic Messages API 的 GA 形态：

```text
ResponseFormat.json_schema -> output_config.format.schema
output_config.format.type = "json_schema"
```

示例 payload：

```python
{
    "output_config": {
        "format": {
            "type": "json_schema",
            "schema": response_format.json_schema,
        }
    }
}
```

当请求同时携带 `ResponseFormat` 与 `ReasoningConfig.effort` 时，adapter 合并为同一个 `output_config`：

```python
{
    "output_config": {
        "format": {"type": "json_schema", "schema": response_format.json_schema},
        "effort": "high",
    }
}
```

`ResponseFormat.json_schema_name`、`json_schema_description` 与 `json_schema_strict` 保留 vatbrain 侧语义，不映射到 Anthropic payload 中未明确支持的字段。Pydantic helper 的 strict schema normalization 仍会体现在 `json_schema` body 中。

实现不调用 Anthropic SDK `messages.parse()`；该 SDK helper 只作为体验参考，adapter 仍走 `messages.create`，保持 request/response mapping、provider-native snapshot、streaming 和 Pydantic helper 的统一行为。

Anthropic 文档标记 JSON outputs 与 message prefilling 不兼容。因此当请求携带 `ResponseFormat` 且转换后的最后一条 message role 为 `assistant` 时，mapper 会提前抛出 `UnsupportedCapabilityError`。

## Response Mapping

入口：

```python
def from_anthropic_generation_response(response: Any) -> GenerationResponse:
    ...
```

响应字段：

```text
response.id -> GenerationResponse.id
provider -> "anthropic"
response.model -> model
response.stop_reason -> stop_reason
usage_from_anthropic(response.usage) -> usage
raw=response
```

Content block 映射：

```text
text -> MessageItem(role=assistant, parts=[TextPart(text)])
tool_use -> FunctionCallItem(name=name, call_id=id, arguments=json.dumps(input))
thinking / redacted_thinking -> ReasoningItem(...)
```

为保留内容顺序，建议按 content block 顺序输出多个 `Item`。例如：

```text
assistant text block
tool_use block
assistant text block
```

映射为：

```text
MessageItem.assistant(...)
FunctionCallItem(...)
MessageItem.assistant(...)
```

Provider-native snapshot：

- 对 text/tool_use/thinking content block 保存 `ProviderItemSnapshot(provider="anthropic", api_family="messages")`。
- snapshot payload 保存 provider 原始 content block。
- replay 时优先使用同 provider/API family snapshot。

## Usage Mapping

```python
def usage_from_anthropic(usage: Any | None) -> Usage | None:
    ...
```

归一化：

```text
provider_input_tokens = usage.input_tokens
cache_creation = usage.cache_creation_input_tokens
cache_read = usage.cache_read_input_tokens
input_tokens = provider_input_tokens + cache_creation + cache_read
output_tokens = usage.output_tokens
total_tokens = input_tokens + output_tokens
cached_tokens = cache_read
```

`Usage.metadata` 保留：

- `provider_input_tokens`
- `cache_creation_input_tokens`
- `cache_read_input_tokens`
- `server_tool_use` if present
- `service_tier` if present

## Streaming

入口：

```python
def from_anthropic_stream_event(event: Any, *, sequence: int) -> GenerationStreamEvent:
    ...
```

事件映射建议：

```text
message_start -> response.created
content_block_start(text) -> content_part.created
content_block_start(tool_use) -> item.created / tool_call.created
content_block_start(thinking) -> reasoning.created
content_block_delta(text_delta) -> text.delta
content_block_delta(input_json_delta) -> tool_call.delta
content_block_delta(thinking_delta/signature_delta) -> reasoning.delta
content_block_stop -> content_part.completed / tool_call.completed / reasoning.completed
message_delta with usage -> usage.updated
message_stop -> response.completed
error -> response.error
unknown -> unknown
```

Anthropic streaming 的 tool input 可能以 partial JSON delta 形式到达。可复用 `GenerationStreamAccumulator` 的 function call delta 重建能力，但 mapper 需要在 metadata 中稳定提供：

- `output_index`
- `content_index`
- `name`
- `call_id`
- `provider_event_type`

## Capability

`capabilities.py`：

```python
def get_adapter_capability() -> AdapterCapability:
    return AdapterCapability(
        provider="anthropic",
        supports_generation=True,
        supports_stream_generation=True,
        supports_async=True,
        supports_text_embedding=False,
        supports_multimodal_embedding=False,
        supports_function_tools=True,
        supports_usage_mapping=True,
        generation=GenerationCapability(...),
        tools=ToolCapability(...),
    )
```

Generation capability：

```text
supported=True
streaming=True
input_modalities=("text", "image")
output_modalities=("text",)
structured_output=True
reasoning_config=True
supported_reasoning_efforts=("low", "medium", "high", "max", "xhigh")
reasoning_output=True
remote_context=True
function_tools=True
metadata["remote_context_semantics"] =
  "enable_cache maps to automatic prompt caching; new_items_start_index ignored; no transport delta"
metadata["reasoning_transport"] = "thinking"
metadata["reasoning_effort_transport"] = "output_config.effort"
metadata["reasoning_manual_budget_model_dependent"] = True
metadata["structured_output_transport"] = "output_config.format"
metadata["structured_output_parse_helper"] = "pydantic_output"
metadata["structured_output_message_prefill_compatible"] = False
```

Tool capability：

```text
user_function_tools=True
custom_tools=False
parallel_tool_calls=True
tool_choice=True
```

Model capability 默认 unknown，支持用户 overrides。

## Error Mapping

Anthropic SDK 调用异常映射为 `ProviderRequestError`：

- `provider="anthropic"`
- `operation="messages.create"`
- `status_code`
- `request_id`
- `error_type`
- `error_code`
- `error_param`
- `raw`
- `cause`

错误 body 解析应沿用 OpenAI/Volcengine helper 风格，兼容 dict 与 SDK error object。

Anthropic 不使用 response-style `previous_response_id`，所以不需要 `_should_refresh_remote_context` 或 remote context refresh。

## 测试策略

默认单元测试不调用真实 Anthropic API。

建议新增：

- `test_anthropic_generation_mapper.py`
  - text message mapping。
  - initial system/developer mapping。
  - image URL/base64 mapping。
  - `RemoteContextHint(enable_cache=True)` maps to top-level `cache_control`。
  - `new_items_start_index` ignored and full messages retained。
  - function tool mapping。
  - explicit `cache_control` in request/remote/tool provider options is rejected。
  - `ResponseFormat` maps to `output_config.format` JSON Schema。
  - explicit `output_config` / `output_format` in provider options is rejected。
  - structured output with assistant prefill is rejected。
  - function call / function result replay mapping。
  - unsupported custom tool、audio/video/file part。
  - usage cache token normalization。
- `test_anthropic_stream_mapper.py`
  - text delta。
  - tool_use start/input_json_delta/stop。
  - thinking delta if supported。
  - message_delta usage。
  - message_stop completed。
  - unknown passthrough。
- `test_anthropic_client.py`
  - sync/async client injected fake SDK。
  - `generate_parsed()` / `agenerate_parsed()` build `output_config.format` and parse assistant JSON text。
  - credential validation。
  - ProviderRequestError mapping。
  - no response-style remote context refresh。
- `test_capabilities.py`
  - Anthropic adapter capability。

可选 costly tests：

- real text generation。
- real image understanding。
- real reasoning generation；reasoning 开启时 `max_output_tokens` 使用 2048。
- real tool use。
- real automatic prompt caching usage observation。

## 实现步骤

1. 已修改 `python/pyproject.toml`，新增 `anthropic` extra。
2. 已新增 provider package 与 lazy SDK import。
3. 已实现 `capabilities.py`。
4. 已实现 `mapper.py`，覆盖 text/image/tool/cache/usage/structured output。
5. 已实现 `client.py` sync/async generation。
6. 已实现 `stream.py` 与 stream client。
7. 已实现 `generate_parsed()` / `agenerate_parsed()`。
8. 已新增 Anthropic `ReasoningConfig` 请求映射、usage reasoning token 映射与 capability。
9. 已添加单元测试。
9. 已同步 [STATUS.md](STATUS.md)、用户 quickstart/API reference 和总索引。

## FAQ

### 为什么 Anthropic mapper 不实现 `use_remote_context=False`？

因为 Anthropic adapter 不使用 response-style `previous_response_id` 进行第一次优化请求，也不存在 remote-context invalid 后的 refresh 请求。它每次都从完整 `items` 构造 full messages。

### 为什么 `RemoteContextHint.enable_cache=True` 能映射为 prompt caching？

在 `vatbrain` 的通用语义里，`enable_cache` 表达 provider-side state/cache/store 的优化意图。Anthropic 没有 Responses previous response 差分语义，但 automatic prefix caching 正好是 provider-side 前缀复用优化。

### 为什么不支持 `FunctionToolType.CUSTOM`？

`FunctionToolType.CUSTOM` 当前表示 OpenAI custom tool 的 freeform input。Anthropic client tools 使用 JSON schema input。MVP 支持用户自定义 function tools，但不把 OpenAI-style custom tool 降级模拟为 Anthropic JSON object。

### 为什么不调用 Anthropic SDK `messages.parse()`？

`messages.parse()` 是 Anthropic Python SDK 的便捷层，会把输出格式转换为 `output_config.format`。`vatbrain` 需要保持 provider-neutral 的 `ResponseFormat`、response mapping、snapshot、streaming 和 Pydantic helper 行为，所以直接调用 `messages.create` 并在 mapper 中显式构造 `output_config.format`。

## 参考资料

- [anthropic-provider-support.CN.md](../../design/anthropic-provider-support.CN.md)
- [provider-native-replay.CN.md](../../design/provider-native-replay.CN.md)
- [v0.3-core-api-family-expansion.CN.md](v0.3-core-api-family-expansion.CN.md)
- Anthropic Messages API：https://docs.anthropic.com/en/api/messages
- Anthropic Python SDK：https://docs.anthropic.com/en/api/sdks/python
- Anthropic structured outputs：https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs
- Anthropic extended thinking：https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
- Anthropic effort：https://platform.claude.com/docs/en/build-with-claude/effort
- Anthropic prompt caching：https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
- Anthropic streaming：https://docs.anthropic.com/en/docs/build-with-claude/streaming
- Anthropic tool use：https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
- Anthropic vision：https://docs.anthropic.com/en/docs/build-with-claude/vision
