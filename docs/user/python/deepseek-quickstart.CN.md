# DeepSeek Provider 快速开始

状态：v0.8 session cache 兼容说明已补充
日期：2026-06-07
最近更新：2026-06-12

## 定位

本文说明 Python 版 `aiflect` 的 DeepSeek provider 用法。完整 API 字段见 [api-reference.CN.md](api-reference.CN.md)，实现边界见 [deepseek-adapter.CN.md](../../impls/python/deepseek-adapter.CN.md)。

DeepSeek adapter 当前使用 DeepSeek Anthropic-compatible Messages API。它支持文本生成、同步/异步、streaming、user-executed function tools、reasoning config 和 usage 映射；不支持图片/文件/音频/视频输入、structured output、Files API、embedding、media generation 或 explicit cache control。

## 安装与环境

```bash
cd python
../.venv/bin/python -m pip install -e ".[deepseek,test]"
```

初始化 client：

```python
from whero.aiflect.providers.deepseek import DeepSeekClient

client = DeepSeekClient(api_key="...")
```

`api_key` 必须显式传入，或通过 `ClientConfig(api_key=...)` 提供；adapter 不从环境变量自动读取。

默认使用 Anthropic 兼容形态：

```python
client = DeepSeekClient(
    api_key="...",
    api_format="anthropic",
)
```

默认 base URL 为：

```text
https://api.deepseek.com/anthropic
```

也可以显式覆盖：

```python
client = DeepSeekClient(
    api_key="...",
    base_url="https://api.deepseek.com/anthropic",
    timeout=30.0,
    max_retries=2,
)
```

`api_format="openai_completion"` 是预留值，当前会在初始化时抛 `ValueError`。

## 文本生成

DeepSeek Anthropic-compatible Messages API 要求 `max_tokens`。使用 `aiflect` 时应通过 `GenerationConfig.max_output_tokens` 提供：

```python
from whero.aiflect import GenerationConfig, MessageItem
from whero.aiflect.providers.deepseek import DeepSeekClient

client = DeepSeekClient(api_key="...")

response = client.generate(
    model="deepseek-chat",
    items=[
        MessageItem.system("You are concise."),
        MessageItem.user("Say hello in one short sentence."),
    ],
    generation_config=GenerationConfig(max_output_tokens=128),
)

for item in response.output_items:
    print(item)
```

异步入口为 `agenerate()`。

## Streaming

```python
for event in client.stream_generate(
    model="deepseek-chat",
    items=[MessageItem.user("Stream one short sentence.")],
    generation_config=GenerationConfig(max_output_tokens=128),
):
    if event.type == "text.delta":
        print(event.delta, end="")
```

可用 `GenerationStreamAccumulator(provider="deepseek")` 从标准化事件重建最小 `GenerationResponse`。异步入口为 `astream_generate()`。

## Reasoning

DeepSeek reasoning 可通过 `ReasoningConfig` 控制：

```python
from whero.aiflect import GenerationConfig, MessageItem, ReasoningConfig

response = client.generate(
    model="deepseek-reasoner",
    items=[MessageItem.user("Think carefully, then answer briefly.")],
    generation_config=GenerationConfig(max_output_tokens=512),
    reasoning=ReasoningConfig(
        mode="enabled",
        effort="high",
    ),
)
```

映射规则：

- `mode="enabled"` 或 `"auto"` -> `thinking={"type": "enabled"}`。
- `mode="disabled"` 或 `"none"` -> `thinking={"type": "disabled"}`。
- `effort="high"` 或 `"max"` -> `output_config.effort`。

不支持 `budget_tokens`、`summary`、`include_trace` 或 `reasoning.provider_options`。

## Function Tools

DeepSeek adapter 只支持 user-executed function tools，不自动执行工具：

```python
from whero.aiflect import GenerationConfig, MessageItem, ToolChoice, ToolCallConfig, ToolSpec

tool = ToolSpec(
    name="lookup",
    description="Lookup a short fact.",
    parameters_schema={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)

response = client.generate(
    model="deepseek-chat",
    items=[MessageItem.user("Look up aiflect.")],
    tools=[tool],
    tool_call_config=ToolCallConfig(tool_choice=ToolChoice.AUTO),
    generation_config=GenerationConfig(max_output_tokens=256),
)
```

模型返回的 `tool_use` 会映射为 `FunctionCallItem`。用户执行工具后，将结果作为 `FunctionResultItem` 加入下一轮完整 `items`。

`ToolCallConfig.parallel_tool_calls=False` 当前不支持，因为 DeepSeek Anthropic 兼容接口会忽略 Anthropic 的禁用并行工具参数。

## Cache Hint 兼容

DeepSeek 会忽略 Anthropic `cache_control`。因此 DeepSeek adapter 接收 `RemoteContextHint` 只是为了兼容通用调用形状；`session_key` 也会被兼容接收但不下发。adapter 不会下发 cache control，也不会做 response id 差分传输：

```python
from whero.aiflect import RemoteContextHint

response = client.generate(
    model="deepseek-chat",
    items=[MessageItem.user("Hello")],
    generation_config=GenerationConfig(max_output_tokens=64),
    remote_context=RemoteContextHint(enable_cache=True),
)
```

显式传入 `cache_control` 会抛 `UnsupportedCapabilityError`。

## Structured Output

DeepSeek Anthropic-compatible endpoint 当前不支持 Anthropic `output_config.format`。因此：

- `ResponseFormat` 会抛 `UnsupportedCapabilityError`。
- `DeepSeekClient` 不提供 `generate_parsed()` / `agenerate_parsed()`。
- 如需结构化 JSON，可在 prompt 中要求 JSON，并由用户代码自行解析。

## Capability

```python
capability = client.get_adapter_capability()

assert capability.provider == "deepseek"
assert capability.generation.input_modalities.value == ("text",)
assert capability.generation.structured_output.value is False
assert capability.generation.supported_reasoning_efforts.value == ("high", "max")
```

Model capability 默认 unknown，可通过 `model_capability_overrides` 提供项目内配置。

## 限制

- 仅实现 `api_format="anthropic"`。
- `api_format="openai_completion"` 预留但未实现。
- 不支持 image/document/file/audio/video input。
- 不支持 structured output / Pydantic parsed convenience。
- 不支持 Files API、embedding、media generation。
- 不支持 explicit `cache_control`。
- 不支持 custom tools。
- 不支持可靠禁用 parallel tool calls。

## 参考

- [deepseek-adapter.CN.md](../../impls/python/deepseek-adapter.CN.md)
- [deepseek-provider-support.CN.md](../../design/deepseek-provider-support.CN.md)
- DeepSeek Anthropic API：https://api-docs.deepseek.com/guides/anthropic_api
