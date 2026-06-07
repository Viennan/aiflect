# DeepSeek Anthropic API 兼容接口摘录

状态：参考资料
最近更新：2026-06-07
来源：https://api-docs.deepseek.com/guides/anthropic_api

## 定位

本文是 DeepSeek 官方 Anthropic API 兼容说明的本地摘录，用于 `vatbrain` DeepSeek adapter 的设计与实现参考。产品语义仍以 [deepseek-provider-support.CN.md](../../design/deepseek-provider-support.CN.md) 和 [deepseek-adapter.CN.md](../../impls/python/deepseek-adapter.CN.md) 为准。

## 关键信息

- Anthropic 兼容 base URL：`https://api.deepseek.com/anthropic`。
- SDK 调用可复用 Anthropic Python SDK 的 `Anthropic` / `AsyncAnthropic` 与 `messages.create`。
- Messages API 支持 text content、streaming、function tools、tool use、tool result、tool choice 和 usage。
- DeepSeek Anthropic 兼容接口不支持 image、document、file、audio、video input。
- `cache_control` 字段会被 DeepSeek 忽略，不产生 Anthropic explicit prompt caching 语义。
- `disable_parallel_tool_use` 会被 DeepSeek 忽略，因此不能可靠表达“禁止并行工具调用”。
- `thinking` 支持启用 reasoning；`budget_tokens` 会被忽略。
- `output_config` 当前只支持 `effort`，可用值以官方文档为准；当前摘录用于实现的值为 `high` 和 `max`。
- Anthropic structured output 的 `output_config.format` 不在 DeepSeek 兼容支持范围内。

## 对 vatbrain 的实现约束

- DeepSeek provider 的首个实现使用 Anthropic 兼容 Messages API。
- `ResponseFormat` 不映射到 `output_config.format`，而是提前抛 `UnsupportedCapabilityError`。
- `RemoteContextHint.enable_cache=True` 只作为兼容 hint 接收，不下发 `cache_control`。
- `ToolCallConfig.parallel_tool_calls=False` 不能下发为可靠语义，提前抛 `UnsupportedCapabilityError`。
- `ReasoningConfig.effort` 映射为 `output_config.effort`；`ReasoningConfig.mode` 映射为 `thinking={"type": "enabled"}` 或禁用时省略。

