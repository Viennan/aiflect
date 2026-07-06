# REQ-2026-07-openai-response-delta-adapter-options

状态：Completed
创建日期：2026-07-06
最近更新：2026-07-06

## 背景

部分 OpenAI-compatible API provider 或网关虽然暴露 Responses API 形态，但对 `previous_response_id` 差分传输支持不稳定，可能返回不可预测且难以规则识别的错误。`aiflect` 当前在 `RemoteContextHint.enable_cache=True`、`new_items_start_index` 明确且 anchor item 有 response id 时，会自动使用 `previous_response_id + suffix input` 作为 OpenAI adapter 的最优传输路径。

由于这类兼容性问题无法逐个 provider 适配，需要一个不改变业务主逻辑的 wrapper 行为配置，让用户保留完整 `RemoteContextHint` 调用形状，同时要求 OpenAI adapter 发送完整上下文。

## 目标

- 在 `ClientConfig` 中提供 `adapter_options` 字典，用于控制 aiflect provider wrapper 自身行为。
- Core 只保存该字典，不解析字段语义。
- OpenAI adapter 支持通过自身 `adapter_options` 关闭 response-id 差分传输。
- 关闭差分传输时仍保持 Full-context First：用户继续传完整 `items`，adapter 发送完整 input，不发送 `previous_response_id`。
- 保留 OpenAI cache/session 相关映射，例如 `store=True` 与 `prompt_cache_key`。

## 范围

- Python `ClientConfig.adapter_options`。
- Python OpenAI client generation / streaming 的 response delta 开关。
- OpenAI non-stream generation metadata 的可观测性字段。
- 默认 unit tests。
- 用户文档和实现记录同步。

## 非范围

- 不在 core 中定义或解析 `adapter_options` 的内部 schema。
- 不要求不同 provider 复用同一组 `adapter_options` key。
- 不修改 Volcengine、Anthropic 或 DeepSeek provider wrapper 行为。
- 不扩展 provider error 识别规则。
- 不运行 live provider、network、credentialed 或 billable tests。

## 当前进度

### 已完成子目标

- `ClientConfig` 已新增 `adapter_options` 字典字段，并保持 `provider_options` 位置参数兼容。
- OpenAI client 已支持 `adapter_options={"remote_context": {"response_delta": False}}`。
- OpenAI response delta 被禁用时，不发送 `previous_response_id`，使用完整 `items` 构造 input。
- OpenAI response delta 被禁用时，仍保留 `store=True` 与 `prompt_cache_key`。
- Volcengine adapter 不读取该配置。
- 已补充默认 unit tests 与文档。

### 剩余子目标

- 暂无。

## 相关知识库文档

- 实现文档：[remote-context-cache-strategy.CN.md](../impls/python/remote-context-cache-strategy.CN.md)
- 用户文档：[api-reference.CN.md](../user/python/api-reference.CN.md), [quickstart.CN.md](../user/python/quickstart.CN.md)

## 开放问题

- 未来如果其他 provider 也需要 wrapper 行为配置，应由对应 provider wrapper 自行定义并记录自己的 `adapter_options` key。
