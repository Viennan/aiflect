# Provider 原生重放设计

状态：设计草案  
日期：2026-05-10  
最近更新：2026-06-06

## 背景

`vatbrain` 坚持 Full-context First：一次 generation 调用的语义事实来源应是用户传入的完整 `Item` 序列。provider 的 `previous_response_id`、cache、stored response 或 conversation state 只能作为优化提示，不能成为唯一上下文来源。`RemoteContextHint` 表达是否启用 provider-side cache、可选的多轮 session/cache pool 标识，以及完整 `items` 中新增 item 的起始位置。

但不同 provider 的 Responses 风格 API 往往会在 input/output item 上携带对重放很关键的原生字段。OpenAI Responses API 的 assistant message `phase` 就是一个典型例子。它区分 `commentary` 与 `final_answer` 阶段；在 follow-up/replay 时丢失该字段，可能导致模型错误判断历史消息阶段，甚至提前终止。

如果为每个 provider-specific 字段都扩展通用 mapper，core 会逐渐被厂商细节污染；如果完全丢弃原生字段，又无法保证同 provider 下的高保真重放。因此需要一个 provider-native replay 机制。

## 设计哲学

### Full-context First 不变

provider-native replay 不改变 `vatbrain` 的语义模型。用户仍应传入完整上下文；provider response id 失效时，完整上下文仍是 refresh 的事实来源。

provider-native replay 只解决“同 provider 同 API family 下如何尽量保留原生 item 信息”的问题。它不是 provider conversation，也不意味着 `vatbrain` 持有远端会话真值。

### Semantic Full Context, Transport Delta

Full-context First 约束的是用户编程模型和语义事实来源，不要求 adapter 在所有情况下都把完整 `items` 原样传给 provider。

当用户显式提供 `RemoteContextHint(enable_cache=True, new_items_start_index=...)`，且 adapter 能在边界前一个 item 的 provider snapshot metadata 中找到 response id 时，adapter 可以把本次 provider 请求优化为：

- provider 侧远端上下文：`previous_response_id`
- 本地传输 input：完整 `items` 中未被覆盖的追加 suffix

这类优化必须有明确新增边界，不能由 adapter 猜测。若边界缺失或 anchor item 缺少 response id，adapter 应发送完整 `items`。

### Lossless Before Normalized

normalized `Item` 用于跨 provider 的通用编程模型；provider-native snapshot 用于同 provider 的高保真重放。

当 adapter 从 provider response 或 provider input items 映射出 `Item` 时，应尽量保留原始 item payload。后续调用同一 provider/API family 时，adapter 可以优先使用该 snapshot 重建 provider 原生 input item，避免丢失 `phase`、status、item type 细节或未来 provider 新增字段。

### Explicit Replay Policy

重放策略必须显式。这里的“重放”只描述 provider-native snapshot 如何参与同 provider 高保真 input 构造，不再控制 remote context invalid 后是否 refresh。

用户应能选择：

- 只使用 normalized mapper。
- 同 provider 时优先使用 provider-native snapshot。
- 强制使用 provider-native snapshot，缺失即报错。

## 核心抽象

### ProviderItemSnapshot

已新增结构化快照模型：

```text
ProviderItemSnapshot
- provider: str
- api_family: str
- item_type: str
- payload: dict[str, Any]
- replayable: bool
- captured_from: "request" | "response" | "input_items" | provider-specific string
- schema_version: str | None
- metadata: dict[str, Any]
```

其中：

- `provider` 用于限制 snapshot 只在同 provider 使用，例如 `openai`。
- `api_family` 用于限制同 API family 使用，例如 `responses`。
- `payload` 保存 provider 原始 item 结构，不做过度归一化。
- `replayable` 表达该 payload 是否允许作为后续 input 重放。
- `captured_from` 帮助诊断 snapshot 来源。
- `schema_version` 可记录 provider SDK/API 版本或 adapter snapshot 格式版本。

### Snapshot 挂载位置

`Item` 上提供结构化字段：

```text
Item.provider_snapshots: tuple[ProviderItemSnapshot, ...]
```

查找时使用 `"{provider}.{api_family}"` 作为逻辑 key，例如 `openai.responses`。实现层可通过 helper 按 provider/API family 取得匹配 snapshot，避免用户直接遍历内部结构。

不再将 replay snapshot 隐藏在 metadata 中。metadata 只适合保存非结构化诊断信息，不承担 replay 语义。

response-style provider 返回的 parent response id 不是 provider item payload 的一部分，因此不写入 `ProviderItemSnapshot.payload`。adapter 应将它保存在匹配 snapshot 的 metadata 中，例如：

```text
ProviderItemSnapshot.metadata["response_id"] = "resp_..."
```

实现层通过 `provider_response_id_for(item, provider, api_family)` 查找该 id。

### ReplayPolicy

建议新增 generation 级 replay policy：

```text
ReplayPolicy
- mode:
  - normalized_only
  - prefer_provider_native
  - require_provider_native
- cross_provider:
  - unsupported
```

语义：

- `normalized_only`：始终使用通用 mapper，不读取 provider snapshot。
- `prefer_provider_native`：同 provider/API family 且 snapshot 可重放时优先使用 snapshot；缺失时降级到 normalized mapper。
- `require_provider_native`：强制 replay。只要某个待重放 item 缺少匹配且可重放的 provider snapshot，就抛出错误，不静默降级。
- `cross_provider=unsupported`：跨 provider replay 暂不支持。

“强制 replay”对应 `require_provider_native`。它适用于用户明确要求与 provider 原始上下文严格一致的场景，例如 OpenAI 历史 assistant item 必须保留 `phase`。

### Remote Context 覆盖范围

`RemoteContextHint` 不再让用户传入 provider response id。它表达是否启用 provider-side cache、可选的多轮 session/cache pool 标识，以及完整 `GenerationRequest.items` 中新增 item 的起始位置：

```text
RemoteContextHint
- enable_cache: bool
- session_key: str | None
- new_items_start_index: int | None
- provider_options
```

`new_items_start_index` 表示完整 `GenerationRequest.items` 中从哪个 index 开始是本轮新增 item。例如 `new_items_start_index=6` 表示 `items[:6]` 是历史前缀，本次新增 suffix 是 `items[6:]`。

response-style adapter 只检查边界前一个 item，即 `items[new_items_start_index - 1]`。如果该 item 的 provider snapshot metadata 中存在当前 provider/API family 的 response id，则 adapter 可以发送 `previous_response_id` 与 suffix；如果没有，则发送完整 `items`。

`enable_cache` 表达是否启用 provider-side cache/stored response 优化。对 OpenAI/Volcengine Responses API，它映射为 `store` 并允许 adapter 创建未来可引用的 response；对 Anthropic Messages API，它映射为 automatic prompt caching，且仍发送完整 messages。

`session_key` 表达多轮请求属于同一个 provider-side cache pool 的优化意图。OpenAI adapter 将其映射为 `prompt_cache_key`；Volcengine adapter 将其映射为 adapter-managed Responses API Session cache；Anthropic 与 DeepSeek 首期兼容接收但不下发。

约束：

- `new_items_start_index` 必须位于 `[0, len(items)]`。
- provider adapter 若基于 `previous_response_id` 做差分传输，provider-native snapshot replay 只应用于本次实际发送的 suffix items；已由 previous response 覆盖的 history 不应再要求 snapshot。
- 如果已经找到 response id 但 suffix 为空，response-style adapter 应抛出清晰错误。

### Provider 差分传输责任

是否使用差分传输是 provider adapter 的职责，不作为 core 用户 API 的显式开关。

原因：

- 不同 provider 对 remote context 的调用语义不同。OpenAI Responses API 使用 `previous_response_id` 时，本次 input 应表达新增 items；而其他 provider 可能要求全量 input、缓存标记或不同的上下文恢复协议。
- 用户侧真正需要表达的是“完整上下文中从哪里开始是本轮新增 item”，而不是选择某个 provider 的传输算法或管理 provider response id。
- 将传输策略暴露为通用 `ReplayPolicy` 字段，会让用户误以为所有 provider 都有同构的 full/append 开关。

因此 core 保留 `RemoteContextHint.new_items_start_index` 作为新增边界；各 provider adapter 基于自身 API 语义决定如何使用该边界。

## OpenAI Phase 评估

OpenAI assistant message 的 `phase` 具有通用语义价值：它不只是任意 provider option，而是在 assistant 输出中区分中间说明阶段和最终回答阶段。对于需要 follow-up/replay 的模型，丢失 `phase` 可能影响模型判断历史上下文。

因此已将其纳入通用抽象，并使用更语义化的命名，而不是把 OpenAI 字段名直接提升为 core 字段：

```text
AssistantMessagePhase
- commentary
- final_answer
```

挂载于 message-like item：

```text
MessageItem.assistant_phase: AssistantMessagePhase | str | None
```

约束：

- 仅对 `role=assistant` 有意义。
- provider 不支持该语义时可忽略。
- 它用于表达 normalized 语义，不负责保留 provider 原始 payload。
- OpenAI mapper 可以将 `commentary` / `final_answer` 映射到原生 `phase`。

取舍：

- 已引入 `assistant_phase`，因为它表达的是 assistant 历史输出阶段，具备跨 provider 潜力。
- 仍必须保留 provider-native snapshot，因为 `assistant_phase` 不能覆盖所有 provider-specific replay 细节。

## 同 Provider 重放流程

推荐流程：

1. 用户维护完整 `Item` 序列。
2. 首次 provider response 映射为 `GenerationResponse.output_items` 时，adapter 在每个可重放 item 上保存 provider snapshot。
3. 用户将历史 output items 加入下一轮 `GenerationRequest.items`。
4. 如果设置 `ReplayPolicy.mode=prefer_provider_native` 或 `require_provider_native`，adapter 在同 provider/API family 下优先使用 snapshot 构造 input。
5. 如果设置 `RemoteContextHint(enable_cache=True, new_items_start_index=...)`，response-style provider adapter 可在边界前一个 item 中查找 response id，并按自身语义只发送新增 suffix。
6. 如果 provider 返回明确的 previous response/context 失效错误，adapter 移除失效 response id，重新用完整 `items` 构造请求并 refresh 一次。
7. refresh 时若 mode 为 `require_provider_native`，缺失 snapshot 必须报错；若 mode 为 `prefer_provider_native`，缺失 snapshot 可降级到 normalized mapper。

## 跨 Provider 重放

跨 provider replay 暂不支持。

原因：

- provider-native payload 只对原 provider/API family 有意义。
- 不同 provider 对 message phase、reasoning、tool call、file reference、cache/context state 的语义差异很大。
- 盲目转换可能制造错误上下文，比显式失败更危险。

长期 TODO：

- 研究 `AssistantMessagePhase`、reasoning visibility、tool protocol item、file reference 等通用语义能否支持“受限跨 provider replay”。
- 定义跨 provider replay compatibility report，明确哪些 item 可迁移、哪些字段丢失、哪些 item 必须由用户确认。
- 在 capability 中声明 provider 是否支持读取/写入必要 replay 语义。

## 与 RemoteContextHint 的关系

`RemoteContextHint` 是远端 cache/delta 优化 hint。provider-native replay 是本地完整上下文的高保真序列化辅助。二者互补：

- 有效的 provider response id 可以降低 token 成本或延迟，但该 id 由 adapter 从 item snapshot metadata 中读取，不由用户传入。
- 失效时，provider-native replay 帮助用完整上下文恢复请求。
- 即使存在 snapshot，用户仍应传入完整上下文序列。
- 差分传输必须依赖显式新增边界，不能只凭 provider id、role 或 purpose 自动裁剪 `items`。

### 失效 Refresh 构造

当第一次请求使用差分传输时，client 不能简单复用第一次请求参数再移除 `previous_response_id`。第一次请求的 input 只有 suffix；refresh 请求必须重新基于原始 `GenerationRequest.items` 构造完整 input，并移除失效的 provider response id。

因此实现上应区分两类 mapping：

- optimized attempt：`previous_response_id` + uncovered suffix。
- refresh attempt：无失效 `previous_response_id` + full items。

这也意味着 mapper 或 client 需要一个清晰的“本次传输 item 选择”入口，不能把 `GenerationRequest.items` 直接无条件映射为 provider input。

## 非目标

- 不引入 provider conversation 持久化上下文抽象。
- 不支持跨 provider 原生 payload 自动转换。
- 不自动执行工具。
- 不把 remote context refresh 扩大为通用 fallback/retry。
- 不把所有 provider-specific 字段提升为通用字段。

## FAQ

### 为什么不只用 metadata 透传 phase？

`metadata` 可以短期止血，但无法表达 replay policy、provider/API family 匹配、强制 replay 失败条件和 snapshot 来源。`phase` 只是第一个暴露问题的字段，长期需要系统性的 provider-native snapshot。

### 为什么还要考虑 assistant_phase？

因为 OpenAI `phase` 背后有跨 provider 潜力：assistant 历史输出可能确实存在“中间说明”和“最终回答”的阶段语义。通用 `assistant_phase` 可以帮助用户手工构造 normalized 历史消息；provider-native snapshot 则保证同 provider 的原始保真。

### 强制 replay 和 Full-context First 冲突吗？

不冲突。强制 replay 要求每个历史 item 都能用 provider-native snapshot 重建；它仍然基于用户传入的完整 `items`，只是禁止 adapter 静默丢失 provider 原生信息。

### 为什么不把 items 拆成 history_items 和 append_items？

`vatbrain` 的核心编程模型要求用户传入完整语义上下文。如果在 `GenerationRequest` 顶层拆成 history/append，用户很容易误以为 history 可以省略或由 provider 维护。覆盖边界应作为 `RemoteContextHint` 中相对某个 previous response id 的事实表达，由 adapter 从完整 `items` 计算传输 suffix。

## 参考资料

- [high-level-design.CN.md](high-level-design.CN.md)
- [provider-capability-integration.CN.md](provider-capability-integration.CN.md)
- [REQ-2026-05-python-reference-implementation-roadmap.CN.md](../requirements/REQ-2026-05-python-reference-implementation-roadmap.CN.md)
- OpenAI Responses input item 文档：https://platform.openai.com/docs/api-reference/responses/input-items
