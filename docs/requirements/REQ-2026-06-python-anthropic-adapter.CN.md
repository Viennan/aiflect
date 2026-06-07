# REQ-2026-06-python-anthropic-adapter

状态：Completed
创建日期：2026-06-05
最近更新：2026-06-07

## 背景

`vatbrain` 当前 Python 参考实现已支持 OpenAI 与 Volcengine provider。Anthropic Claude Messages API 与 `vatbrain` 的 full-context generation、user-executed tools、streaming event 和 cache/usage 抽象存在较高契合度，但它没有 OpenAI/Volcengine Responses API 的 `previous_response_id` 差分上下文语义。

本需求记录 Anthropic provider adapter 的范围、状态和后续落地入口。详细设计见 [anthropic-provider-support.CN.md](../design/anthropic-provider-support.CN.md)，Python 实现计划见 [anthropic-adapter.CN.md](../impls/python/anthropic-adapter.CN.md)。

## 目标

- 在 Python 参考实现中新增 Anthropic provider adapter。
- 支持 Claude Messages API generation、streaming、async generation、图片理解和 user-executed function tools。
- 通过 `RemoteContextHint.enable_cache=True` 启用 Anthropic automatic prefix caching，同时保持 Full-context First。
- 保持与 response-style provider 的编程模型兼容：用户仍传完整上下文，Anthropic adapter 返回 provider response id，但不使用 response id 做差分传输。

## 范围

- 新增 `whero.vatbrain.providers.anthropic` provider package。
- 新增 optional dependency：`whero-vatbrain[anthropic]`。
- 使用官方 Anthropic Python SDK 的 `Anthropic` / `AsyncAnthropic` 与 `messages.create`。
- 支持文本与图片输入、多轮消息、function tool、tool use / tool result 回填、streaming event 映射、usage/cache token 映射和 adapter/model capability。
- 保留 provider-native snapshot，用于同 provider/API family 下的高保真重放。

## 非范围

- 不支持 Anthropic Files API。
- 不支持 embedding。
- 不支持 media generation。
- 不支持 provider-hosted/server tools、web search、code execution、MCP 或 SDK Tool Runner 自动工具循环。
- 暂不暴露 Anthropic explicit cache control；不在 `Item`、content part 或 tool spec 上新增 cache 字段。
- 不通过 `previous_response_id` 进行差分传输，不实现 Anthropic 版 remote context fallback。
- 不维护内部 Anthropic model capability 真值表。

## 当前进度

### 已完成子目标

- 明确 Anthropic provider MVP 范围与非范围。
- 明确 cache control 语义：`RemoteContextHint.enable_cache=True` 映射为 top-level automatic prompt caching；`new_items_start_index` 在 Anthropic adapter 中忽略。
- 明确 Python mapper、client、capability、streaming 和测试设计。
- 已将设计与实现方案落入知识库。
- 已实现 Python provider package、optional dependency、request/response mapper、stream mapper、client、capability 和单元测试。
- 已同步用户文档、API reference、quickstart 与实现状态。

### 剩余子目标

- 可选真实 Anthropic API integration tests 后续按 costly test 方式补充。

## 相关知识库文档

- 设计文档：[anthropic-provider-support.CN.md](../design/anthropic-provider-support.CN.md)
- 实现文档：[anthropic-adapter.CN.md](../impls/python/anthropic-adapter.CN.md)
- Structured output 需求：[REQ-2026-06-python-anthropic-structured-output.CN.md](REQ-2026-06-python-anthropic-structured-output.CN.md)
- 高层设计：[high-level-design.CN.md](../design/high-level-design.CN.md)
- Provider 能力整合：[provider-capability-integration.CN.md](../design/provider-capability-integration.CN.md)
- Provider 原生重放：[provider-native-replay.CN.md](../design/provider-native-replay.CN.md)
- 第三方资料：
  - Anthropic Messages API：https://docs.anthropic.com/en/api/messages
  - Anthropic Python SDK：https://docs.anthropic.com/en/api/sdks/python
  - Anthropic structured outputs：https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs
  - Anthropic prompt caching：https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
  - Anthropic tool use：https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
  - Anthropic vision：https://docs.anthropic.com/en/docs/build-with-claude/vision

## 开放问题

- `ResponseFormat` 已由 [REQ-2026-06-python-anthropic-structured-output.CN.md](REQ-2026-06-python-anthropic-structured-output.CN.md) 完成支持。
- 初始 `MessageItem.developer` 映射到 top-level `system` 是否需要提供严格模式以便用户拒绝有损 authority 映射。
