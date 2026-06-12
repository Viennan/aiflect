# Anthropic Provider 快速开始

状态：v0.8
日期：2026-06-06
最近更新：2026-06-12

## 定位

本文说明 Python 版 `vatbrain` 的 Anthropic provider 用法。完整 API 字段见 [api-reference.CN.md](api-reference.CN.md)，实现边界见 [anthropic-adapter.CN.md](../../impls/python/anthropic-adapter.CN.md)。

Anthropic adapter 使用官方 Anthropic Python SDK 的 Messages API。它支持文本生成、图片理解、JSON Schema structured output、ReasoningConfig extended thinking、同步/异步、streaming、user-executed function tools 和 automatic prefix caching；不支持 Anthropic Files API、embedding、media generation、provider-hosted/server tools 或 SDK Tool Runner 自动工具循环。

## 安装与环境

```bash
cd python
../.venv/bin/python -m pip install -e ".[anthropic,test]"
```

初始化 client：

```python
from whero.vatbrain.providers.anthropic import AnthropicClient

client = AnthropicClient(api_key="...")
```

也可以显式传入 Anthropic SDK client 参数：

```python
client = AnthropicClient(
    api_key="...",
    base_url="https://api.anthropic.com",
    timeout=30.0,
    max_retries=2,
)
```

Anthropic API key 必须显式传入，或通过 `ClientConfig(api_key=...)` 提供；adapter 不从环境变量自动读取。

## 文本与图片理解

Anthropic Messages API 要求 `max_tokens`。使用 `vatbrain` 时应通过 `GenerationConfig.max_output_tokens` 提供：

```python
from whero.vatbrain import GenerationConfig, ImagePart, MessageItem, TextPart
from whero.vatbrain.providers.anthropic import AnthropicClient

client = AnthropicClient(api_key="...")

response = client.generate(
    model="claude-sonnet-4-5",
    items=[
        MessageItem.system("You are concise."),
        MessageItem.user([
            TextPart("Describe this image."),
            ImagePart(url="https://example.test/image.png"),
        ]),
    ],
    generation_config=GenerationConfig(max_output_tokens=300),
)

for item in response.output_items:
    print(item)
```

`ImagePart` 支持 URL 或 base64/data URL。Anthropic adapter 不支持 `AudioPart`、`VideoPart` 或 `FilePart`；不会调用 Anthropic Files API，也不会隐式读取或上传本地文件。

## Automatic Prefix Cache

Anthropic adapter 将 `RemoteContextHint.enable_cache=True` 映射为 Anthropic automatic prompt caching。`session_key` 可以复用通用 session cache 调用形状，但当前不会下发给 Anthropic；`new_items_start_index` 可以复用 response-style provider 的调用形状，但 adapter 会忽略它；每次请求仍从完整 `items` 构造 full Messages API 输入。

```python
from whero.vatbrain import GenerationConfig, MessageItem, RemoteContextHint

first_items = [MessageItem.user("Summarize this long context...")]

first_response = client.generate(
    model="claude-sonnet-4-5",
    items=first_items,
    generation_config=GenerationConfig(max_output_tokens=300),
    remote_context=RemoteContextHint(enable_cache=True),
)

history_items = [*first_items, *first_response.output_items]
next_items = [*history_items, MessageItem.user("Now extract the risks.")]

response = client.generate(
    model="claude-sonnet-4-5",
    items=next_items,
    generation_config=GenerationConfig(max_output_tokens=300),
    remote_context=RemoteContextHint(
        enable_cache=True,
        session_key="risk-review-thread",
        new_items_start_index=len(history_items),
    ),
)
```

要点：

- 用户侧仍传入完整 `items`。
- `enable_cache=True` 开启 automatic prompt caching。
- `session_key` 当前兼容接收但不下发，仅用于保持跨 provider 调用形状。
- `new_items_start_index` 只用于兼容 response-style provider 的新增边界形状，Anthropic adapter 不使用它做差分传输。
- 不支持显式传入 Anthropic `cache_control`；如在 request、remote context 或 tool `provider_options` 中设置 `cache_control`，adapter 会抛出 `UnsupportedCapabilityError`。

Cache usage 会映射到 `Usage`：

- `usage.input_tokens` 表示 provider raw input、cache creation 和 cache read token 的总和。
- `usage.cached_tokens` 来自 Anthropic `cache_read_input_tokens`。
- `usage.metadata` 保留 provider raw input、cache creation 和 cache read 明细。

## Streaming

```python
for event in client.stream_generate(
    model="claude-sonnet-4-5",
    items=[MessageItem.user("Write a short poem.")],
    generation_config=GenerationConfig(max_output_tokens=120),
):
    if event.type == "text.delta":
        print(event.delta, end="")
```

Anthropic streaming 会映射 text delta、tool input JSON delta、usage update、completed/error 和 unknown passthrough 事件。可用 `GenerationStreamAccumulator(provider="anthropic")` 从标准化事件重建最小 `GenerationResponse`。

异步入口为 `agenerate()` 与 `astream_generate()`。

## Structured Output

Anthropic adapter 支持 `ResponseFormat` JSON Schema structured output，并把它映射为 Anthropic Messages API 的 `output_config.format`。不兼容 JSON mode / `json_object`，也不调用 Anthropic SDK `messages.parse()`。

```python
from whero.vatbrain import GenerationConfig, MessageItem, ResponseFormat

response = client.generate(
    model="claude-sonnet-4-5",
    items=[MessageItem.user("Extract a contact from this text.")],
    response_format=ResponseFormat(
        json_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["name", "email"],
            "additionalProperties": False,
        },
        json_schema_name="contact",
        json_schema_strict=True,
    ),
    generation_config=GenerationConfig(max_output_tokens=300),
)
```

Python 侧可用 Pydantic helper 生成 schema 并解析最终响应：

```python
from pydantic import BaseModel

from whero.vatbrain import GenerationConfig, MessageItem


class Contact(BaseModel):
    name: str
    email: str


parsed = client.generate_parsed(
    model="claude-sonnet-4-5",
    items=[MessageItem.user("Extract a contact from this text.")],
    output_type=Contact,
    generation_config=GenerationConfig(max_output_tokens=300),
)

contact = parsed.output_parsed
```

如果需要自定义 schema name、description 或 strict 行为，使用 `pydantic_output()` + `generate()`。Anthropic JSON outputs 与 assistant message prefill 不兼容；请求携带 `ResponseFormat` 时，最后一条消息不能是 assistant prefill。用户也不能通过 `provider_options` 显式传入 Anthropic `output_config` 或旧 beta `output_format`。

## Reasoning

Anthropic adapter 支持 `ReasoningConfig`，并映射为 Anthropic Messages API 的 extended thinking 参数：

```python
from whero.vatbrain import GenerationConfig, MessageItem, ReasoningConfig

response = client.generate(
    model="claude-sonnet-4-5",
    items=[MessageItem.user("Think through the tradeoffs, then answer briefly.")],
    generation_config=GenerationConfig(max_output_tokens=2048),
    reasoning=ReasoningConfig(
        mode="auto",
        effort="high",
        summary="omitted",
    ),
)
```

映射规则：

- `mode="disabled"` 或 `"none"` -> `thinking={"type": "disabled"}`。
- `budget_tokens=...` -> `thinking={"type": "enabled", "budget_tokens": ...}`。
- `mode="auto"`、`"enabled"` 或 `"adaptive"` -> `thinking={"type": "adaptive"}`。
- `effort` -> `output_config.effort`，当前 adapter 接收 `low`、`medium`、`high`、`max`、`xhigh`。
- `summary="auto"` / `"summarized"` -> `display="summarized"`；`summary="none"` / `"omitted"` -> `display="omitted"`。

开启 reasoning 时通常需要更大的 `max_output_tokens`；costly smoke 使用 2048 作为基线。Active thinking 与 assistant message prefill、`temperature`、`top_k` 和 forced tool choice 不兼容；manual `budget_tokens` 必须小于 `max_tokens`。不同模型对 manual budget 和 effort 值的支持可能不同，必要时通过 `model_capability_overrides` 补充模型能力。

## Function Tools

Anthropic adapter 支持 user-executed function tools。`vatbrain` 不自动执行工具；模型返回 `FunctionCallItem` 后，由用户代码执行工具，并在下一轮完整上下文中加入 `FunctionResultItem`。

```python
from whero.vatbrain import (
    FunctionCallItem,
    FunctionResultItem,
    GenerationConfig,
    MessageItem,
    ToolSpec,
)

tools = [
    ToolSpec(
        name="get_weather",
        description="Get weather by city.",
        parameters_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )
]

response = client.generate(
    model="claude-sonnet-4-5",
    items=[MessageItem.user("What is the weather in Shanghai?")],
    tools=tools,
    generation_config=GenerationConfig(max_output_tokens=300),
)

tool_calls = [item for item in response.output_items if isinstance(item, FunctionCallItem)]
tool_result = FunctionResultItem(
    call_id=tool_calls[0].call_id,
    output='{"temperature_c":22}',
)

followup = client.generate(
    model="claude-sonnet-4-5",
    items=[
        MessageItem.user("What is the weather in Shanghai?"),
        *response.output_items,
        tool_result,
    ],
    tools=tools,
    generation_config=GenerationConfig(max_output_tokens=300),
)
```

`FunctionToolType.CUSTOM` 暂不支持。这里的“不支持 custom tools”指 OpenAI-style freeform custom tool，不影响用户自定义 function tools。

## Capability

```python
capability = client.get_adapter_capability()

assert capability.supports_generation is True
assert capability.supports_text_embedding is False
assert capability.generation.input_modalities.value == ("text", "image")
assert capability.generation.structured_output.value is True
assert capability.generation.reasoning_config.value is True
```

Anthropic model capability 默认 unknown，可通过 `model_capability_overrides` 或 `get_model_capability(..., overrides=...)` 由用户补充。

## 限制

- 不支持 Files API。
- 不支持 embedding。
- 不支持 media generation。
- 不支持 provider-hosted/server tools、web search、code execution、MCP 或 SDK Tool Runner。
- 不支持 `ReasoningConfig.include_trace` 或 `reasoning.provider_options`。
- 不支持 response-style previous response 差分传输，也没有 response-style remote context refresh。
- 不支持 structured output 与 assistant message prefill 同用。

## 参考

- [api-reference.CN.md](api-reference.CN.md)
- [anthropic-adapter.CN.md](../../impls/python/anthropic-adapter.CN.md)
- [anthropic-provider-support.CN.md](../../design/anthropic-provider-support.CN.md)
