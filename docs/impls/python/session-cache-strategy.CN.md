# Python Session Cache 策略实现记录

状态：Completed
日期：2026-06-12
最近更新：2026-06-12
引入需求：[REQ-2026-06-session-cache-strategy.CN.md](../../requirements/REQ-2026-06-session-cache-strategy.CN.md)

## 定位

本文记录 Python 参考实现中 `RemoteContextHint.session_key` 的落地方式。高层语义见 [session-cache-strategy.CN.md](../../design/session-cache-strategy.CN.md)，既有 remote context 基线见 [remote-context-cache-strategy.CN.md](remote-context-cache-strategy.CN.md)。

## 当前基线

当前 `RemoteContextHint` 包含：

```text
enable_cache: bool = False
new_items_start_index: int | None = None
provider_options: dict[str, Any]
```

OpenAI 与 Volcengine mapper 根据 `new_items_start_index` 查找 anchor item snapshot 中的 response id，找到时发送 `previous_response_id + suffix input`，找不到时发送完整 input。Anthropic mapper 忽略 `new_items_start_index`，仅在 `enable_cache=True` 时发送 top-level `cache_control={"type": "ephemeral"}`。

## Core 改动

在 [generation.py](../../../python/whero/aiflect/core/generation.py) 中扩展：

```python
@dataclass(frozen=True, slots=True)
class RemoteContextHint:
    enable_cache: bool = False
    session_key: str | None = None
    new_items_start_index: int | None = None
    provider_options: dict[str, Any] = field(default_factory=dict)
```

校验：

- `new_items_start_index >= 0` 的既有校验不变。
- `session_key is None or session_key.strip()`；空字符串抛 `ValueError`。
- `provider_options` 继续复制为普通 `dict`，保持 dataclass frozen 语义下的浅不可变。

导出：

- `whero.aiflect.core.__init__` 和 `whero.aiflect.__init__` 无需新增导出名，因为字段属于既有 class。

## OpenAI Adapter

### Mapper

在 `to_openai_generation_params()` 中：

- 扩展保留字段集合：`previous_response_id`、`store`、`prompt_cache_key`。
- 如果 `remote_context.session_key` 存在，写入 `params["prompt_cache_key"]`。
- 如果用户通过 `GenerationRequest.provider_options` 或 `RemoteContextHint.provider_options` 显式设置 `prompt_cache_key`，抛 `UnsupportedCapabilityError`，提示使用 `RemoteContextHint.session_key`。

既有行为保持：

- `enable_cache=True -> store=True`。
- anchor response id 存在时发送 `previous_response_id` 与 suffix input。
- invalid/expired fallback 时移除 `previous_response_id`，但保留 `prompt_cache_key` 和 `store=True`。

### 测试

- `session_key` 映射为 `prompt_cache_key`。
- `provider_options["prompt_cache_key"]` 冲突报错。
- fallback retry 保留 `prompt_cache_key`。
- metadata 记录 `session_key_present=True`，不记录原始 key。

## Volcengine Adapter

### 参数所有权

Volcengine session 模式下 adapter 拥有以下 generation 字段：

```text
previous_response_id
store
caching
expire_at
```

保留字段集合应扩展为：

```text
previous_response_id
store
caching
expire_at
```

这些字段不能通过 `GenerationRequest.provider_options` 或 `RemoteContextHint.provider_options` 设置。用户如需关闭 cache，应使用 `RemoteContextHint(enable_cache=False)`。

### Session 模式判定

```text
session_mode = remote_context is not None
    and remote_context.enable_cache is True
    and remote_context.session_key is not None
```

`session_key` 不下发为 `session` 字段；首期仅用于表达“采用 Session cache 策略”，以及 metadata 中的 presence。

### 参数映射

session mode 请求：

```text
store=True
caching={"type": "enabled"}
expire_at=int(time.time()) + 3600
```

如果 `new_items_start_index` 和 anchor response id 可用，且 anchor 未接近过期：

```text
previous_response_id=<anchor response id>
input=<items[new_items_start_index:]>
```

否则：

```text
input=<full request.items>
```

`use_remote_context=False` 的 retry 仍使用 full input，并保留 `store=True`、`caching={"type": "enabled"}`、新的 `expire_at`。

### 即将过期判断

Volcengine output item snapshot metadata 中记录：

```text
response_id
response_created_at
response_expire_at
response_caching
response_store
```

mapper/client 查找 anchor response id 时同时读取 `response_expire_at`。当前实现使用 safety window：

```text
_VOLCENGINE_SESSION_CACHE_TTL_SECONDS = 3600
_VOLCENGINE_PREVIOUS_RESPONSE_EXPIRY_SAFETY_SECONDS = 300
```

当 `response_expire_at - now <= 300` 时，不发送 `previous_response_id`，直接 full input。metadata 标记：

```text
refreshed_before_expiry=True
previous_response_expire_at=<timestamp>
```

如果 provider response 没有返回 `expire_at`，则无法提前判断，保留现有 invalid/expired fallback。

### Response Snapshot Enrichment

`from_volcengine_generation_response(response)` 在 mapper 中读取 response 级字段，并在构造每个 output item 的 provider snapshot 时写入 metadata。client 只负责给最终 `GenerationResponse.metadata["remote_context"]` 补充本次请求路径信息。

需要从 response 读取：

- `response.id`
- `response.created_at`
- `response.expire_at`
- `response.caching`
- `response.store`

并写入每个 output item 的 Volcengine Responses snapshot metadata。

### Session 模式限制

Volcengine 文档说明 cache 与若干字段存在限制。当前实现做以下保守处理：

- `provider_options["instructions"]`：session mode 下抛 `UnsupportedCapabilityError`。
- `ResponseFormat`：session mode 下抛 `UnsupportedCapabilityError`，因为当前通用 `ResponseFormat` 映射为 `json_schema`，而 Volcengine cache 链不支持 `json_schema`。

`tools` 与 `thinking/reasoning` 继续按既有 Volcengine 映射发送；当前实现不记录跨轮 signature，也不主动比较 anchor 与本轮配置。后续如需要更强的一致性保护，可在 snapshot metadata 中记录 normalized signature，并在不一致时 full refresh 或提前抛错。

### Metadata

扩展 `GenerationResponse.metadata["remote_context"]`：

```text
api_family
cache_enabled
session_cache_enabled
session_key_present
attempted_previous_response_id
final_request_used_previous_response_id
refreshed_after_invalid_context
refreshed_before_expiry
new_items_start_index
previous_response_expire_at
```

不记录原始 `session_key`。

### 测试

Mapper 单测：

- session mode full input 请求包含 `store=True`、`caching={"type": "enabled"}`、`expire_at`。
- session mode anchor 可用时发送 `previous_response_id + suffix`。
- `caching`/`expire_at` provider_options 冲突报错。
- session mode 下 `instructions` 和 `ResponseFormat` 报错。

Client 单测：

- anchor 未过期时 optimized attempt。
- anchor 即将过期时 full input，不发 `previous_response_id`。
- invalid previous response fallback 仍 full refresh。
- response snapshot metadata 写入 `response_expire_at`。
- metadata 不泄露 `session_key`。

Costly 测试：

- 长上下文两轮 Volcengine session cache，第二轮 `usage.cached_tokens` 可观察。
- 即将过期行为可用 fake clock 或单元测试覆盖，不建议 costly 测试真实等待。

## Anthropic Adapter

Anthropic mapper 兼容读取 `remote_context.session_key`，但不下发。既有行为保持：

```text
enable_cache=True -> cache_control={"type": "ephemeral"}
new_items_start_index ignored
session_key ignored
```

metadata 可记录 `session_key_present=True`，但不记录原始 key。

## DeepSeek Adapter

DeepSeek adapter 兼容接收 `session_key`，不下发 cache control 或 session 参数。显式 `cache_control` 仍按既有规则拒绝。

## Capability

已在 `GenerationCapability.metadata` 中补充：

OpenAI：

```text
remote_context_semantics: "enable_cache stores responses; session_key maps to prompt_cache_key; new_items_start_index can use previous_response_id"
session_key_transport: "prompt_cache_key"
```

Volcengine：

```text
remote_context_semantics: "session_key enables Responses API Session cache managed by adapter"
session_key_transport: "responses_session_cache"
session_cache_ttl_seconds: 3600
```

Anthropic：

```text
session_key_transport: "ignored"
```

DeepSeek：

```text
session_key_transport: "ignored"
```

## 文档更新

本次实现已同步：

- [quickstart.CN.md](../../user/python/quickstart.CN.md) 的 Remote Context 章节。
- [api-reference.CN.md](../../user/python/api-reference.CN.md) 的 `RemoteContextHint` 字段定义与 provider 支持范围。
- [volcengine-quickstart.CN.md](../../user/python/volcengine-quickstart.CN.md) 的 Session cache、1h TTL 和 full refresh 说明。
- [anthropic-quickstart.CN.md](../../user/python/anthropic-quickstart.CN.md) 的 `session_key` 兼容接收但不下发说明。

## 验收

默认单元测试应覆盖所有 mapper/client 行为：

```bash
cd python
../.venv/bin/python -m pytest
```

真实 provider costly 测试覆盖 OpenAI session key 下发；Volcengine Session cache costly 测试受模型矩阵 `supports_session_cache` 控制，只有在账号/模型已开通缓存服务并显式声明支持时运行。Costly 测试应避免依赖精确命中率断言，优先断言请求路径、metadata 和 `cached_tokens` 字段存在/非负；只有在长上下文可稳定触发缓存时再断言 `cached_tokens > 0`。
