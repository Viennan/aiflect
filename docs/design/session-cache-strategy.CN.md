# Session Cache 策略设计

状态：已落地
日期：2026-06-12
最近更新：2026-06-12
引入需求：[REQ-2026-06-session-cache-strategy.CN.md](../requirements/REQ-2026-06-session-cache-strategy.CN.md)

## 背景

`vatbrain` 已经把 provider-side state/cache 归入 `RemoteContextHint`。现有模型要求用户传入完整 `GenerationRequest.items`，同时允许 OpenAI 与 Volcengine 这类 response-style provider 在新增边界明确时使用 `previous_response_id` 和 suffix input 做传输优化；Anthropic 则在完整 Messages API 输入上启用 automatic prompt caching。

多轮对话的缓存命中率还可以进一步提高。OpenAI 提供 `prompt_cache_key` 改善同类请求的 cache pool 命中；Volcengine Responses API 提供显式 Session 缓存；Anthropic automatic cache 会随多轮上下文增长动态维护缓存点。这些能力都指向同一个用户意图：一组请求属于同一个多轮 session，希望 provider 尽可能复用历史上下文计算。

## 设计哲学

### Full-context First

`GenerationRequest.items` 仍是每次 generation 的完整语义事实来源。`session_key` 不代表 `vatbrain` 持有的 conversation，也不允许 adapter 只凭 session key 省略用户没有传入的历史语义上下文。

即使 provider-side session/cache 已过期、被删除或命中失败，adapter 也必须能够基于完整 `items` 发起语义等价请求。

### Session Key as Optimization

`session_key` 是 provider-side cache pool / session cache 的稳定标识，而不是 provider response id、context id 或持久状态句柄。用户提供的是业务层会话标识，provider adapter 再映射为该 provider 的缓存优化参数。

推荐用户传入不可逆、稳定、低基数的字符串，例如业务 session id 的 hash，避免把真实用户身份、邮箱、手机号或内部敏感标识直接下发给 provider。

### Provider Difference Is Visible

不同 provider 的 session/cache 能力差异不应被伪装成完全一致：

- OpenAI 的 `prompt_cache_key` 改善缓存路由和命中率，但不显式创建缓存对象。
- Volcengine Responses API Session 缓存需要 `caching={"type": "enabled"}`、`store=True`、`previous_response_id` 与生命周期管理共同工作。
- Anthropic automatic cache 没有 response-style 差分传输，`session_key` 首期只兼容接收。

能力差异应写入 adapter capability metadata、实现文档和 response metadata，而不是用隐式 fallback 掩盖。

## 目标模型

扩展 `RemoteContextHint`：

```text
RemoteContextHint
- enable_cache: bool = False
- session_key: str | None = None
- new_items_start_index: int | None = None
- provider_options: dict[str, Any]
```

字段语义：

- `enable_cache`：是否启用 provider-side cache/stored response 优化。
- `session_key`：多轮 session/cache pool 的稳定标识；仅在 `enable_cache=True` 时有 provider 映射意义。
- `new_items_start_index`：完整 `items` 中新增 item 的起始 index，用于 response-style adapter 查找 anchor response id 并发送 suffix。
- `provider_options`：provider-specific 逃生口，但不能覆盖 adapter-owned cache/session 参数。

当前校验与冲突处理：

- `session_key` 为 `None` 或非空字符串。
- 若 `session_key` 存在但 `enable_cache=False`，core 可兼容接收，但 adapter 不下发 session/cache 参数，并在 metadata 中体现 `cache_enabled=False`。
- provider-owned 字段冲突时抛 `UnsupportedCapabilityError`，例如 OpenAI `prompt_cache_key` 与通用 `session_key` 同时出现。

## Provider 映射

### OpenAI Responses

OpenAI adapter 将 `RemoteContextHint.session_key` 映射为 Responses API `prompt_cache_key`。

OpenAI response-style 差分传输继续沿用现有规则：

- `enable_cache=True` 且 anchor item 有 OpenAI Responses response id：发送 `previous_response_id` 与 suffix input。
- 找不到 anchor response id：发送完整 input。
- previous response invalid/expired：自动移除 `previous_response_id` 并 full-context refresh 一次。

`store=True` 仍由 `enable_cache=True` 控制。`prompt_cache_retention` 首期不进入通用 core，用户如需尝试 provider 原生 retention，可在后续单独设计其 provider-specific 入口。

### Volcengine Responses

Volcengine adapter 将 `session_key` 映射为 Responses API Session 缓存策略，而不是下发为 provider 的 `session` 字段。

Session 模式参数组合：

```text
store=True
caching={"type": "enabled"}
expire_at=now + 3600
previous_response_id=<anchor response id>, when usable
input=<suffix>, when previous_response_id usable
```

Volcengine 的 `expire_at` 同时影响 response 存储和 token cache 生命周期，且是绝对过期时刻，不随使用续期。因此该字段由 adapter 管理：

- 不向用户暴露 generation `expire_at`。
- 固定内部生命周期为 1 小时。
- 在 anchor response 即将过期时不再发送 `previous_response_id`，直接 full-context refresh。
- refresh 后继续写入新的 session cache 链。

Session 模式下还需要尊重 Volcengine cache 限制：

- `instructions` 会导致本轮无法写入和使用缓存，当前 session 模式下拒绝。
- `json_schema` 与 cache 链存在兼容限制，当前 session 模式下拒绝 `ResponseFormat`。
- `thinking/reasoning` 与 `tools` 继续按既有 Volcengine 映射发送；当前不记录跨轮 signature，也不主动比较 anchor 与本轮配置。后续如需要更强的一致性保护，可在 snapshot metadata 中记录 normalized signature，并在不一致时 full refresh 或提前抛错。

### Anthropic Messages

Anthropic adapter 继续将 `enable_cache=True` 映射为 top-level `cache_control={"type": "ephemeral"}`，并始终从完整 `items` 构造 Messages API 输入。

`session_key` 首期不下发。它保留为通用 session 语义占位，以便未来 Anthropic 若提供 cache pool、container 或其他稳定 session 路由能力时可以映射。

### DeepSeek 与其他兼容 Provider

暂不使用 `session_key` 的 provider 应兼容接收该字段，但不下发 cache control 或 session 参数。adapter capability metadata 应说明 `session_key` ignored / no transport mapping。

## 模块职责

### Core

Core 只定义 provider-neutral `session_key` 字段和基础校验，不保存 provider response id，不维护 session 状态，不计算 provider 过期时间。

### Provider Mapper

Mapper 负责把 `RemoteContextHint` 转换为 provider 原生请求参数，并拒绝用户通过 `provider_options` 覆盖 adapter-owned cache/session 字段。

### Provider Client

Client 负责需要运行时信息的策略：

- 当前时间。
- previous response 即将过期判断。
- invalid/expired fallback。
- response metadata 合并。

Volcengine 的 `expire_at=now+3600` 和即将过期 refresh 应放在 client/mapper 协作层，而不是 core。

### Item Snapshot

Provider output item snapshot 继续保存 parent response id。Volcengine session 模式还需要在 snapshot metadata 中补充：

- response `expire_at`。
- response `created_at`，如果 provider 返回。
- response `caching` 与 `store`，如果 provider 返回。

不要默认写入原始 `session_key`，避免日志或对象序列化泄露业务会话标识。

## 可观测性

OpenAI 与 Volcengine 的 `GenerationResponse.metadata["remote_context"]` 继续记录 response-style 请求路径，并扩展 session 相关字段：

```text
api_family: "responses"
cache_enabled: bool
session_cache_enabled: bool
session_key_present: bool
attempted_previous_response_id: bool
final_request_used_previous_response_id: bool
refreshed_after_invalid_context: bool
refreshed_before_expiry: bool
new_items_start_index: int | None
previous_response_expire_at: int | None
```

metadata 不应包含原始 `session_key`。如需要诊断，可记录稳定 hash 或仅记录 presence。

## FAQ

### 为什么不引入 `Session` 对象？

当前问题是 provider-side cache 命中优化，不是 `vatbrain` 自身会话状态管理。引入 `Session` 对象会模糊 Full-context First，并暗示 `vatbrain` 可以代表用户维护完整对话状态。首期只增加 `session_key`，保持模型小而清晰。

### 为什么 Volcengine 不暴露 `expire_at`？

Volcengine Responses API 的 `expire_at` 同时影响 response 存储和 token cache 生命周期。如果让用户随意设置，adapter 很难保证 previous response 还可被引用，也容易产生缓存存储费用和过期行为上的误解。首期固定为 1 小时，并由 adapter 在接近过期时主动 full-context refresh。

### session key 是否改变模型回答？

不应改变。它只影响 provider-side cache 路由、存储和传输方式。语义上下文仍由完整 `items` 决定。

## 参考资料

- [remote-context-cache-strategy.CN.md](../impls/python/remote-context-cache-strategy.CN.md)
- [provider-native-replay.CN.md](provider-native-replay.CN.md)
- [context_cache.md](../3rds/volengine/context_cache.md)
- [response_api_context_cache.md](../3rds/volengine/response_api_context_cache.md)
- [response_api_detail_ref.md](../3rds/volengine/response_api_detail_ref.md)
