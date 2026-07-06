# DeepSeek Provider 支持设计

状态：已落地
最近更新：2026-06-07

## 背景

DeepSeek 提供 Anthropic 兼容接口和 OpenAI completion 兼容接口。`aiflect` 当前以 provider adapter 隐藏不同厂商的调用差异，DeepSeek provider 应把两种兼容形态纳入同一个 client 初始化模型，但首期只实现 Anthropic 兼容接口，避免一次性引入两个 transport family。

相关需求记录见 [REQ-2026-06-python-deepseek-provider.CN.md](../requirements/REQ-2026-06-python-deepseek-provider.CN.md)，Python 实现记录见 [deepseek-adapter.CN.md](../impls/python/deepseek-adapter.CN.md)。

## Design Philosophy

DeepSeek adapter 的设计优先级是：保留 `aiflect` 的 Full-context First 编程模型，复用已验证的 Messages API 映射经验，显式暴露 DeepSeek 兼容接口的能力边界。DeepSeek 官方兼容层对 Anthropic 参数不是完全等价，因此 adapter 不能简单复制 Anthropic provider；凡是 DeepSeek 会忽略且用户可能误以为生效的控制项，应在通用字段层提前拒绝或降级为无 transport effect 的兼容 hint。

## Module Responsibilities

### Core

Core 不为 DeepSeek 新增数据结构。现有模型已经足够表达本期能力：

- `GenerationRequest` / `GenerationResponse`：完整上下文 generation。
- `ResponseFormat`：保留通用 structured output 语义，但 DeepSeek adapter 明确不支持。
- `ReasoningConfig`：表达 mode 与 effort。
- `RemoteContextHint`：兼容 cache hint 形状，不改变 DeepSeek transport。
- `ToolSpec` / `FunctionCallItem` / `FunctionResultItem`：表达 user-executed function tools。
- `ProviderItemSnapshot`：保存 DeepSeek Anthropic-compatible content block 以便 same-provider replay。

### DeepSeek Provider Adapter

DeepSeek provider adapter 负责：

- 将 `GenerationRequest` 映射到 DeepSeek Anthropic-compatible `messages.create` 参数。
- 将 DeepSeek response content blocks 映射为 normalized items。
- 将 DeepSeek stream events 映射为 `GenerationStreamEvent`。
- 将 usage token 映射为 `Usage`。
- 将 `ReasoningConfig.mode` 映射为 `thinking`，将 `ReasoningConfig.effort` 映射为 `output_config.effort`。
- 声明 adapter capability，包括 text-only input、不支持 structured output、不支持 remote context transport。

DeepSeek provider adapter 不负责：

- 自动工具执行。
- provider-hosted tools、MCP 或 agent loop。
- OpenAI completion 兼容接口的首期实现。
- embedding、Files API 或 media generation。
- 模型级能力真值表。

## Client 初始化模型

`DeepSeekClient` 使用独立 provider identity：`provider="deepseek"`。

初始化参数包括：

- `api_key` / `ClientConfig.api_key`
- `base_url` / `ClientConfig.base_url`
- `timeout`
- `max_retries`
- `client` / `async_client`
- `api_format`
- `model_capability_overrides`
- `**deepseek_client_options`

`api_format` 支持：

- `"anthropic"`：已实现，默认值。
- `"openai_completion"`：预留值，当前初始化时抛 `ValueError`。

Anthropic 兼容模式默认 `base_url` 为：

```text
https://api.deepseek.com/anthropic
```

显式 `base_url` 优先级高于 `ClientConfig.base_url`，二者都缺失时使用默认值。

## Generation 映射

DeepSeek Anthropic 兼容接口使用 Messages API 形状：

- 初始 `MessageItem.system` / `MessageItem.developer` 合并到 top-level `system`。
- `MessageItem.user` / `MessageItem.assistant` 映射为 `messages`。
- 仅支持 `TextPart`。
- `FunctionToolSpec(type="function")` 映射为 Anthropic-compatible tool。
- `FunctionCallItem` 映射为 `tool_use`。
- `FunctionResultItem` 映射为 `tool_result`，不映射 `is_error`。
- `GenerationConfig.max_output_tokens` 映射为 `max_tokens`，缺失时要求用户通过 provider options 明确传入。

不支持 `ImagePart`、`AudioPart`、`VideoPart`、`FilePart`；遇到这些 part 时抛 `InvalidItemError`。

## Reasoning

DeepSeek 的 reasoning 控制与 Anthropic 不完全一致，adapter 提供有限映射：

- `ReasoningConfig.mode in {"enabled", "auto"}` -> `thinking={"type": "enabled"}`。
- `ReasoningConfig.mode in {"disabled", "none"}` -> `thinking={"type": "disabled"}`。
- `ReasoningConfig.effort in {"high", "max"}` -> `output_config={"effort": ...}`。

以下配置不支持：

- `budget_tokens`
- `summary`
- `include_trace`
- `reasoning.provider_options`
- disabled mode 与 effort 同用

如果用户同时通过 `provider_options` 设置 `thinking` 或 `output_config`，并且又传入 `ReasoningConfig`，adapter 抛 `UnsupportedCapabilityError`，避免双来源冲突。

## Structured Output

DeepSeek Anthropic 兼容接口当前不支持 Anthropic `output_config.format`。因此：

- `ResponseFormat` 直接抛 `UnsupportedCapabilityError`。
- 不提供 `generate_parsed()` / `agenerate_parsed()` convenience。
- `provider_options["output_format"]` 与 `provider_options["output_config"]["format"]` 会被拒绝。
- `provider_options["output_config"]["effort"]` 可作为 provider-native reasoning effort 透传，但推荐使用 `ReasoningConfig.effort`。

## Cache 与 Remote Context

DeepSeek 官方兼容接口会忽略 Anthropic `cache_control`。因此 DeepSeek adapter 的语义是：

- `RemoteContextHint.enable_cache=True`：兼容接收，不改变 transport。
- `RemoteContextHint.new_items_start_index`：兼容接收，忽略。
- `RemoteContextHint.session_key`：兼容接收，不下发。
- 不发送 `cache_control`。
- 不做 previous response 差分传输。
- 用户显式传入 `cache_control` 会抛 `UnsupportedCapabilityError`。

这保持了 response-style provider 的调用形状兼容，但不会向用户暗示 DeepSeek 有可控 prompt cache transport。

## Tools

只支持 user-executed function tools：

- `ToolSpec(type="function")` -> DeepSeek Anthropic-compatible tool。
- `tool_use` -> `FunctionCallItem`。
- `FunctionResultItem` -> `tool_result`。

DeepSeek 会忽略 Anthropic `disable_parallel_tool_use`，因此 `ToolCallConfig.parallel_tool_calls=False` 不能可靠表达禁用并行工具调用，adapter 提前抛 `UnsupportedCapabilityError`。

## Capability

Adapter capability 声明：

- generation：支持。
- streaming：支持。
- async：支持。
- input modalities：`("text",)`。
- output modalities：`("text",)`。
- structured output：不支持。
- reasoning config：支持。
- supported reasoning efforts：`("high", "max")`。
- remote context：不支持 transport。
- function tools：支持。
- custom tools：不支持。
- parallel tool calls control：不支持。
- files / embedding / media generation：不支持。

Model capability 默认 unknown，允许用户通过 `model_capability_overrides` 覆写。

## FAQ

### 为什么不是直接复用 AnthropicClient？

DeepSeek 兼容接口不是 Anthropic API 的完全等价实现。特别是 image/document、cache control、structured output、parallel tool control 和 reasoning effort 的语义不同。独立 `DeepSeekClient` 能让 provider identity、capability 和错误信息都保持准确。

### 为什么保留 `api_format`，但只实现 Anthropic？

这是为了给 DeepSeek 的 OpenAI completion 兼容形态预留稳定初始化面。首期只实现 Anthropic 兼容模式，可以先把 DeepSeek 的主要 generation/tool/reasoning 能力接入，后续再单独设计 OpenAI completion mapper。

### `RemoteContextHint.enable_cache=True` 在 DeepSeek 上有什么效果？

当前没有 transport effect。它只是为了让用户代码可以用同一种 remote hint 形状调用不同 response-style 或 Anthropic-compatible provider；DeepSeek adapter 不下发 `cache_control`。

## 参考

- DeepSeek Anthropic API：https://api-docs.deepseek.com/guides/anthropic_api
- 本地摘录：[anthropic_api.CN.md](../3rds/deepseek/anthropic_api.CN.md)
