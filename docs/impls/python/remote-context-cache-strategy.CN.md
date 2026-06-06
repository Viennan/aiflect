# Remote Context 与 Cache 策略实现记录

状态：Completed  
日期：2026-06-06  
最近更新：2026-06-06

## 目标模型

`GenerationRequest.items` 仍然是完整语义上下文。`RemoteContextHint` 只表达 provider-side cache 优化意图：

```text
RemoteContextHint
- enable_cache: bool = False
- new_items_start_index: int | None = None
- provider_options: dict[str, Any]
```

`new_items_start_index` 是完整 `items` 中新增 item 的起始 index。它不是 response id 的覆盖计数；用户不再传入 response id。response-style adapter 只检查 `items[new_items_start_index - 1]` 上是否存在匹配 provider/API family 的 response id。

## Core 改动

- 删除 `RemoteContextHint.previous_response_id`、`covered_item_count`、`store`。
- 删除 `RemoteContextInvalidBehavior`。
- 删除 `ReplayPolicy.on_remote_context_invalid`，使 `ReplayPolicy` 只控制 provider-native snapshot 使用策略。
- 新增 `provider_response_id_for(item, provider, api_family)`。

`ProviderItemSnapshot.payload` 保持 provider 原始 item/block 数据；parent response id 存在 `ProviderItemSnapshot.metadata["response_id"]` 中。

## Response-Style Provider

OpenAI 与 Volcengine generation mapper 使用相同策略：

1. `remote_context` 缺失：发送完整 `items`，不显式发送 cache/store 参数。
2. `enable_cache=False`：发送完整 `items`，发送 `store=False`。
3. `enable_cache=True` 且无有效 `new_items_start_index`：发送完整 `items`，发送 `store=True`。
4. `enable_cache=True` 且 anchor item 中存在 response id：发送 `previous_response_id` 与 suffix `items[new_items_start_index:]`。
5. `enable_cache=True` 但 anchor item 缺少 response id：发送完整 `items` 与 `store=True`。

如果 suffix 为空但已经找到 response id，mapper 抛出 `InvalidItemError`，因为 response-style delta 请求需要至少一个新增 item。

Provider options 中的 `previous_response_id` 与 `store` 是保留字段；用户应通过 `RemoteContextHint` 控制这些行为。

## 失效恢复

OpenAI 与 Volcengine client 在第一次请求实际携带 `previous_response_id`，且 provider SDK/服务错误可识别为 previous response/context invalid 或 expired 时，自动构造 full-context refresh attempt：

- 移除 `previous_response_id`。
- 使用完整 `GenerationRequest.items`。
- 保留 `enable_cache=True` 对应的 `store=True`。

该行为不再由用户配置，且只响应明确的 remote context invalid 错误。普通网络错误、参数错误或 streaming 已开始后的错误不扩展为隐藏重试。

## 可观测性

OpenAI 与 Volcengine 的非流式 generation response 会在 `GenerationResponse.metadata["remote_context"]` 中记录 response-style remote context 的请求路径：

- `api_family`: `"responses"`。
- `cache_enabled`: 本次 request 中 `RemoteContextHint.enable_cache` 的值。
- `attempted_previous_response_id`: 初始请求是否携带 `previous_response_id`。
- `final_request_used_previous_response_id`: 最终成功的请求是否携带 `previous_response_id`。
- `refreshed_after_invalid_context`: 是否因为 previous response/context invalid 或 expired 执行了 full-context refresh。
- `new_items_start_index`: 用户提供该 hint 时记录其值。

costly 多轮测试使用该 metadata 确认第二轮 response-style 请求确实通过第一轮 response id 成功完成，而不是被自动 full-context refresh 兜底。

## Anthropic Provider

Anthropic adapter 始终从完整 `items` 构造 full Messages API 请求：

- `enable_cache=True` 映射为 top-level `cache_control={"type": "ephemeral"}`。
- `enable_cache=False` 不发送 `cache_control`。
- `new_items_start_index` 被忽略。
- 显式 `cache_control` 仍是保留字段，在 request、remote context 或 tool provider options 中出现时抛 `UnsupportedCapabilityError`。

## 测试

默认测试覆盖：

- core 字段校验与 `provider_response_id_for()`。
- OpenAI/Volcengine mapper 的 anchor response id 查找、suffix 传输、缺失 anchor 时 full input、失效 refresh full input。
- OpenAI/Volcengine response output item snapshot metadata 写入 response id。
- OpenAI/Volcengine non-stream generation 的 remote context metadata，区分 previous response 成功与自动 refresh。
- Anthropic `enable_cache=True` automatic cache 映射与 full messages 输入。
- `RemoteContextInvalidBehavior` 与旧 fallback policy 删除后的 client 行为。
