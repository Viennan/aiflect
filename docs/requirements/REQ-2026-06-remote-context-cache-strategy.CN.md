# RemoteContextHint 与缓存策略升级

状态：Completed  
日期：2026-06-06  
最近更新：2026-06-06

## 背景

OpenAI/Volcengine Responses API 使用 stored response 与 `previous_response_id` 做链式增量传输；Anthropic Messages API 每次发送完整 messages，并通过 automatic prompt caching 复用重复前缀。旧版 `RemoteContextHint(previous_response_id, covered_item_count, store)` 直接暴露了 Responses API 的字段形状，使 Anthropic adapter 只能兼容接收并忽略部分字段，语义不够自然。

本需求在未发布阶段重塑通用 cache hint，使用户只表达完整上下文中的新增边界和是否启用 provider-side cache，由 provider adapter 自行处理 response id、suffix 传输、全量 messages 和 cache control。

## 目标

- 从 `RemoteContextHint` 移除用户可见的 `previous_response_id`。
- 将 `covered_item_count` 替换为 `new_items_start_index`，表达完整 `items` 中新增 item 的起始位置。
- 将 `store` 替换为 `enable_cache`，统一表达 provider-side cache/stored-response 优化意图。
- response-style provider 自动从边界前一个 item 的 provider snapshot metadata 中读取 response id。
- response-style provider 在 previous response 失效时自动使用完整 `items` refresh，不再要求用户配置 retry/fallback policy。
- Anthropic adapter 忽略 `new_items_start_index`，继续全量发送 messages，并在 `enable_cache=True` 时启用 automatic prompt caching。
- provider 输出 item 的 `ProviderItemSnapshot.metadata["response_id"]` 保存 parent response id，snapshot payload 保持 provider 原始 item/block 格式。

## 实现结果

- `RemoteContextHint` 现在为 `enable_cache/new_items_start_index/provider_options`。
- 新增 `provider_response_id_for()` helper，用于从匹配 provider/API family 的 snapshot metadata 读取 response id。
- OpenAI 与 Volcengine generation mapper 根据 `new_items_start_index` 查找 anchor item；找到 response id 时发送 suffix，否则发送完整 `items`。
- OpenAI 与 Volcengine client 在确认本次请求实际携带 `previous_response_id` 且 provider 报 previous response/context invalid 时，自动移除 remote context 并用完整 `items` 重建请求。
- OpenAI 与 Volcengine 非流式 generation response 通过 `metadata["remote_context"]` 暴露 response-style remote context 路径，用于区分 previous response 直接成功与自动 full-context refresh。
- Anthropic adapter 使用 `RemoteContextHint.enable_cache=True` 映射 `cache_control={"type": "ephemeral"}`，不暴露 explicit cache control。
- 删除 `RemoteContextInvalidBehavior` 与 `ReplayPolicy.on_remote_context_invalid`；`ReplayPolicy` 只保留 provider-native snapshot replay 策略。
- costly generation 增加 cached multi-turn 测试：response-style provider 断言第二轮直接使用 previous response 成功且未 refresh；Anthropic provider 覆盖 auto cache 开启后的全量 messages 多轮路径。

## 验证

- `cd python && ../.venv/bin/python -m pytest`
- 结果：186 passed, 9 skipped。
- `scripts/run-costly-tests --yes --all-models`
- 结果：15 passed, 8 skipped。OpenAI premium 使用 full-context cache-enabled 多轮路径，暂不运行 `new_items_start_index` response-id 差分传输；Volcengine response-style cache 与 Anthropic auto-cache 多轮路径完成验证。

## 相关文档

- [../design/high-level-design.CN.md](../design/high-level-design.CN.md)
- [../design/provider-native-replay.CN.md](../design/provider-native-replay.CN.md)
- [../design/anthropic-provider-support.CN.md](../design/anthropic-provider-support.CN.md)
- [../impls/python/remote-context-cache-strategy.CN.md](../impls/python/remote-context-cache-strategy.CN.md)
- [../user/python/api-reference.CN.md](../user/python/api-reference.CN.md)
