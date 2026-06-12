# REQ-2026-06-session-cache-strategy

状态：Completed
创建日期：2026-06-12
最近更新：2026-06-12

## 背景

本需求提出前，`vatbrain` 已经通过 `RemoteContextHint(enable_cache, new_items_start_index)` 建立了 provider-side cache 与 response-style 差分传输的通用入口。既有实现依赖各 provider 的默认缓存策略，OpenAI 与 Volcengine 可以通过 `previous_response_id` 减少传输，Anthropic 通过 automatic prompt caching 复用完整上下文前缀。

在多轮对话、工具调用、角色扮演和长上下文问答中，仅依赖默认缓存策略仍可能造成缓存命中率不稳定。OpenAI Responses API 提供 `prompt_cache_key`，Volcengine Responses API 提供显式 Session 缓存，Anthropic automatic cache 会随对话增长自动更新缓存点。需要在 `vatbrain` 中增加一个 provider-neutral 的 session 标识，让用户可以表达“这些请求属于同一个多轮会话缓存池”，并由各 provider adapter 映射到合适的原生参数组合。

Volcengine 还存在特殊生命周期约束：Responses API 的 `expire_at` 同时影响 response 存储和 token cache 存储，且是绝对过期时刻，不会随使用续期。因此 adapter 需要在 previous response 即将到期时主动退回 full-context 请求，而不是等 provider 报错。

## 目标

- 在 `RemoteContextHint` 中新增 `session_key`，作为多轮对话 session/cache pool 的稳定标识。
- 保持 Full-context First：`GenerationRequest.items` 仍是完整语义上下文，`session_key` 只作为 provider-side cache 优化 hint。
- 为 OpenAI、Volcengine、Anthropic 和兼容 provider 定义清晰映射语义。
- 在 Volcengine adapter 中封装 Session 缓存参数组合，不向用户暴露 `expire_at`，固定内部生命周期为 1 小时。
- 在 Volcengine previous response 即将过期时自动 full-context refresh，避免使用即将失效的 `previous_response_id`。
- 保留现有 `enable_cache/new_items_start_index` 编程模型与 response-style invalid fallback。

## 范围

- Python 参考实现的 core generation 模型。
- OpenAI Responses API adapter 的 `prompt_cache_key` 映射。
- Volcengine Responses API adapter 的 Session 缓存参数映射、生命周期管理和 metadata enrichment。
- Anthropic Messages API adapter 对 `session_key` 的兼容接收。
- DeepSeek 等暂不使用该参数的 provider 对 `session_key` 的兼容接收。
- 单元测试、costly 多轮测试和相关知识库文档。

## 非范围

- 不引入 `vatbrain` 自己的持久化 conversation/session runtime。
- 不让用户直接传入 provider response id、context id 或 `expire_at`。
- 不实现 Volcengine Context API；本需求仅覆盖 Responses API Session 缓存。
- 不暴露 OpenAI `prompt_cache_retention` 为通用 core 字段；可继续通过 provider-specific 机制后续讨论。
- 不改变跨 provider replay 的不支持状态。
- 不自动执行工具，也不引入 agent loop。

## 当前进度

### 已完成子目标

- 已完成需求分析与设计方案讨论。
- 已新增高层设计文档与 Python 实现设计文档。
- 已扩展 `RemoteContextHint.session_key` 与空字符串校验。
- OpenAI adapter 已将 `session_key` 映射为 `prompt_cache_key`，并拒绝显式 `prompt_cache_key` 覆盖。
- Volcengine adapter 已实现 adapter-managed Responses API Session cache，自动设置 `caching={"type":"enabled"}` 与 1 小时 `expire_at`，并在 anchor response 接近过期时 full-context refresh。
- Anthropic 与 DeepSeek adapter 已兼容接收 `session_key`，首期不下发。
- 已更新单元测试、capability metadata、用户文档和实现状态。
- 已纳入用户补充的 Volcengine 第三方资料：
  - [context_cache.md](../3rds/volengine/context_cache.md)
  - [response_api_context_cache.md](../3rds/volengine/response_api_context_cache.md)

### 剩余子目标

- 可选：补充真实 provider costly 测试，观察 OpenAI `prompt_cache_key` 与 Volcengine Session cache 的 live usage/cached token 行为。

## 相关知识库文档

- 设计文档：[session-cache-strategy.CN.md](../design/session-cache-strategy.CN.md)
- 实现文档：[session-cache-strategy.CN.md](../impls/python/session-cache-strategy.CN.md)
- 相关既有实现记录：[remote-context-cache-strategy.CN.md](../impls/python/remote-context-cache-strategy.CN.md)
- 高层设计：[high-level-design.CN.md](../design/high-level-design.CN.md)
- 第三方资料：
  - [context_cache.md](../3rds/volengine/context_cache.md)
  - [response_api_context_cache.md](../3rds/volengine/response_api_context_cache.md)
  - [response_api_detail_ref.md](../3rds/volengine/response_api_detail_ref.md)

## 开放问题

- OpenAI `prompt_cache_retention` 是否需要独立进入通用 core，还是继续保留为 provider-specific 参数。
- Volcengine session 模式下，`tools`、`thinking`、`response_format` 等跨轮一致性冲突应全部提前拒绝，还是仅触发 full-context refresh 并在 metadata 中记录原因。
- Costly 测试是否需要分别覆盖 OpenAI `prompt_cache_key`、Volcengine Session cache 命中与即将过期 refresh。
