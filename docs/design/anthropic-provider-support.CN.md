# Anthropic Provider 支持设计

状态：设计稿
日期：2026-06-05
最近更新：2026-06-07

## 背景

Anthropic Claude Messages API 是无状态 messages 调用面，支持文本、图片理解、工具调用、streaming、extended thinking、structured output 与 prompt caching。`vatbrain` 的核心 generation 模型已经具备 full-context `Item` 序列、user-executed function tools、stream event、usage、capability、provider-native snapshot 和 `RemoteContextHint`。

本设计将 Anthropic provider 纳入 `vatbrain` provider adapter 体系，同时避免把 Anthropic cache 或 Messages API 的 provider-specific 细节提升为通用 core 字段。

相关需求记录见 [REQ-2026-06-python-anthropic-adapter.CN.md](../requirements/REQ-2026-06-python-anthropic-adapter.CN.md)，Python 实现计划见 [anthropic-adapter.CN.md](../impls/python/anthropic-adapter.CN.md)。

## Design Philosophy

### Full-context First 不变

Anthropic adapter 必须继续要求用户传入完整 `items` 序列。Anthropic prompt cache 只降低重复前缀成本，不成为 `vatbrain` 的上下文事实来源。

对 Anthropic 而言，`RemoteContextHint.new_items_start_index` 不代表 provider-side continuation handle。即使用户传入该字段，adapter 也不裁剪 `items`，不发送 suffix，不依赖 response id 恢复上下文。

### Cache as Enable Hint

为了兼容 OpenAI/Volcengine Responses API 风格的用户代码，Anthropic adapter 将 `RemoteContextHint.enable_cache=True` 解释为“请求 provider 复用上下文前缀的优化意图”，并在 provider 请求中启用 Anthropic automatic prefix caching。

该映射是 provider-local 解释：

```text
RemoteContextHint.enable_cache=True
  -> Anthropic messages.create(cache_control={"type": "ephemeral"})
```

`RemoteContextHint.new_items_start_index` 在 Anthropic adapter 中被忽略。这样同一段用户代码可以在 response-style provider 中表达新增边界，在 Anthropic 中仍保持 full messages 输入。

### No Explicit Anthropic Cache Surface

MVP 不暴露 Anthropic explicit cache control：

- 不在 `Item` 上增加 cache 字段。
- 不在 `TextPart`、`ImagePart` 或其他 content part 上增加 cache 字段。
- 不在 `ToolSpec` 上增加通用 cache 字段。
- 不通过 provider-specific `provider_options` 公开 explicit block-level cache API 作为正式编程模型。
- `cache_control` 是 Anthropic adapter 保留字段，只能由 `RemoteContextHint.enable_cache=True` 生成；用户在 request、remote context 或 tool 的 `provider_options` 中显式传入 `cache_control` 时，adapter 应抛出不支持错误，而不是静默当作 explicit cache control。

短期只支持 automatic prefix caching，避免在 core 里过早固化 provider-specific cache breakpoint 语义。

### Tool Ownership Remains User-executed

Anthropic 支持 client tools、server tools、MCP、web search、code execution 和 SDK Tool Runner。`vatbrain` 当前通用 core 只抽象 user-executed function tools，且不自动执行工具。因此 Anthropic MVP 只支持 client-side function tools：

- `FunctionToolSpec(type="function")` 映射为 Anthropic tool。
- Anthropic `tool_use` 映射为 `FunctionCallItem`。
- 用户执行工具后以 `FunctionResultItem` 回填，映射为 Anthropic `tool_result`。

Provider-hosted/server tools 和 SDK Tool Runner 暂不进入范围。

### Structured Output Uses Existing ResponseFormat

Anthropic structured outputs 不引入新的 core 字段。`vatbrain` 继续使用既有 `ResponseFormat` 表达 JSON Schema structured output，由 Anthropic adapter 在 provider-local mapper 中转换为 Messages API 的 `output_config.format`：

```text
ResponseFormat.json_schema
  -> messages.create(output_config={"format": {"type": "json_schema", "schema": ...}})
```

Anthropic Python SDK 的 `messages.parse()` 可作为体验参考，但 adapter 不调用该 helper。这样 request mapping、response mapping、streaming、provider-native snapshot 与 Python Pydantic helper 都仍走 `vatbrain` 的统一路径。

`ResponseFormat.json_schema_name`、`json_schema_description` 与 `json_schema_strict` 保留通用语义，不提升为 Anthropic-specific core 字段，也不映射到 Anthropic payload 中未明确支持的字段。Strict schema 的主要作用来自 `pydantic_output(..., strict=True)` 对 JSON Schema body 的 normalization。

Anthropic 的 JSON outputs 与 assistant message prefilling 不兼容，因此 adapter 应在请求携带 `ResponseFormat` 且最后一条 Anthropic message 为 assistant 时提前拒绝。

## Module Responsibilities

### Core

Core 不为 Anthropic adapter 增加新字段。现有模型已经足够表达 MVP：

- `GenerationRequest.items`：完整语义上下文。
- `RemoteContextHint.enable_cache`：作为 provider-side cache 优化意图。
- `RemoteContextHint.new_items_start_index`：兼容 response-style provider 的新增边界，但 Anthropic adapter 忽略。
- `ToolSpec` / `FunctionToolSpec`：user-executed function tool schema。
- `ResponseFormat`：JSON Schema structured output。
- `FunctionCallItem` / `FunctionResultItem`：tool use 和 tool result 协议。
- `Usage.cached_tokens` 与 `Usage.metadata`：cache 命中与写入统计。
- `ProviderItemSnapshot`：保存 Anthropic content block 或 message payload，用于同 provider replay。

### Anthropic Provider Adapter

Provider adapter 负责：

- 将 `GenerationRequest` 映射到 Anthropic `messages.create` 参数。
- 将 Anthropic response content blocks 映射为 `MessageItem`、`FunctionCallItem`、`ReasoningItem` 等 normalized items。
- 将 Anthropic streaming events 映射为 `GenerationStreamEvent`。
- 将 Anthropic usage 中的 cache read/create token 归一化为 `Usage`。
- 将 `ResponseFormat` 映射为 Anthropic `output_config.format` JSON Schema。
- 声明 adapter capability 和 model capability。

Anthropic adapter 不负责：

- 自动执行工具。
- 维护对话状态。
- 基于 response id 做远端上下文恢复。
- 暴露 File API、embedding 或 media generation。

## Core Semantics

### RemoteContextHint 语义

Anthropic adapter 对 `RemoteContextHint` 的解释如下：

```text
enable_cache=True
  -> enable automatic prompt caching

enable_cache=False
  -> do not send cache_control

new_items_start_index
  -> ignored by Anthropic adapter
```

因此 Anthropic generation 永远是：

```text
semantic input: full GenerationRequest.items
transport input: full Anthropic messages
optional optimization: automatic prefix cache
```

它与 OpenAI/Volcengine 的差异是：

- OpenAI/Volcengine 可以在 `enable_cache=True` 且 `new_items_start_index` 的 anchor item 上存在 response id 时发送 suffix。
- Anthropic 不发送 suffix，只启用 automatic prefix cache。

### Cache Usage 归一化

Anthropic usage 包含：

- `input_tokens`
- `output_tokens`
- `cache_creation_input_tokens`
- `cache_read_input_tokens`

归一化建议：

```text
Usage.input_tokens = input_tokens + cache_creation_input_tokens + cache_read_input_tokens
Usage.output_tokens = output_tokens
Usage.cached_tokens = cache_read_input_tokens
Usage.total_tokens = Usage.input_tokens + output_tokens
Usage.raw = provider raw usage
Usage.metadata["provider_input_tokens"] = input_tokens
Usage.metadata["cache_creation_input_tokens"] = cache_creation_input_tokens
Usage.metadata["cache_read_input_tokens"] = cache_read_input_tokens
```

这样 `Usage.input_tokens` 表达完整 input token 规模，而 `cached_tokens` 表达其中由 cache 命中的部分。

## Capability Guidance

Anthropic adapter capability 建议声明：

```text
supports_generation=True
supports_stream_generation=True
supports_async=True
supports_text_embedding=False
supports_multimodal_embedding=False
supports_function_tools=True
supports_usage_mapping=True
```

Generation capability：

```text
input_modalities=("text", "image")
output_modalities=("text",)
structured_output=True
reasoning_config=False
reasoning_output=True if thinking blocks mapped
remote_context=True
function_tools=True
```

`remote_context=True` 的含义需要在 metadata 中明确：

```text
metadata["remote_context_semantics"] =
  "enable_cache maps to Anthropic automatic prompt caching; new_items_start_index is ignored; no transport delta"
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

其中 `custom_tools=False` 指 vatbrain 的 `FunctionToolType.CUSTOM`，不是指用户自定义 function tool。

## FAQ

### 为什么不把 Anthropic cache control 做成 core 字段？

因为本阶段只需要 automatic prefix caching。Explicit cache breakpoint 涉及 system、tools、message content block 等 provider-specific 标记位置，过早提升为 core 字段会污染通用 `Item` 模型。

### 为什么 `RemoteContextHint.new_items_start_index` 要忽略？

这是为了兼容 response-style provider 的用户代码形状。用户可以用同一种 hint 表达“启用 cache + 新增边界”；Anthropic adapter 用 `enable_cache=True` 开 cache，忽略新增边界，仍发送完整上下文。

### 忽略 `new_items_start_index` 会不会破坏 Full-context First？

不会。Full-context First 要求用户传入完整 `items` 作为语义事实来源。Anthropic adapter 不裁剪 items，反而是最直接地遵守该原则。

### 为什么不使用 Anthropic SDK Tool Runner？

`vatbrain` 明确不自动执行工具。SDK Tool Runner 会运行工具并继续提交结果，属于 agent loop 行为，不属于 provider adapter 的职责。

### 为什么不使用 Anthropic SDK `messages.parse()`？

`messages.parse()` 是 Python SDK 的便捷层，而 `vatbrain` 已有 provider-neutral `ResponseFormat` 与 Pydantic structured output helper。adapter 直接构造 `output_config.format`，可以保持 request/response/stream/snapshot 路径统一，也避免把 Anthropic SDK 的 parse shortcut 变成新的 provider-specific 编程模型。

## 参考资料

- [high-level-design.CN.md](high-level-design.CN.md)
- [provider-capability-integration.CN.md](provider-capability-integration.CN.md)
- [provider-native-replay.CN.md](provider-native-replay.CN.md)
- Anthropic Messages API：https://docs.anthropic.com/en/api/messages
- Anthropic Python SDK：https://docs.anthropic.com/en/api/sdks/python
- Anthropic structured outputs：https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs
- Anthropic prompt caching：https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
- Anthropic tool use：https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
- Anthropic vision：https://docs.anthropic.com/en/docs/build-with-claude/vision
