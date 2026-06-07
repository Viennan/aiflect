# Python 实现文档索引

状态：持续维护
最近更新：2026-06-07

## 定位

本目录记录 Python 参考实现的实现方案、实现基线和 provider adapter 细节。需求生命周期、需求状态和需求级进度不在本目录维护；相关信息见 [requirements/STATUS.md](../../requirements/STATUS.md)。

## 当前实现基线

- [impls/python/STATUS.md](STATUS.md)：Python 当前实现能力基线，记录已实现能力、暂不实现项、后续规划和验证方式。

## 实现文档

### Core 与 API Family

- [v0.2-responses-contract-hardening.CN.md](v0.2-responses-contract-hardening.CN.md)：OpenAI Responses API 合约加固实现方案，覆盖参数映射、structured output、streaming event、stream accumulator 和错误映射。
- [v0.3-core-api-family-expansion.CN.md](v0.3-core-api-family-expansion.CN.md)：Python v0.3 core/API family 实现基线，记录 items、generation、embedding、resources、media、tools、capabilities、OpenAI adapter、Pydantic helper 与 replay 边界。
- [remote-context-cache-strategy.CN.md](remote-context-cache-strategy.CN.md)：Remote Context 与 Cache 策略实现记录，覆盖 `RemoteContextHint.enable_cache/new_items_start_index`、snapshot response id、response-style suffix/refresh 与 Anthropic automatic cache。
- [v0.5-media-generation.CN.md](v0.5-media-generation.CN.md)：Media generation 实现方案与实现记录，覆盖 OpenAI Images API、Volcengine Ark Images API 和 Volcengine Content Generation 视频任务。

### Provider Adapters

- [openai-adapter.CN.md](openai-adapter.CN.md)：Python OpenAI adapter 实现方案，描述首个 provider adapter 的范围、核心模型、OpenAI 映射、测试策略和实现步骤。
- [volcengine-adapter.CN.md](volcengine-adapter.CN.md)：Python Volcengine adapter MVP 实现方案与实现记录，覆盖 Ark SDK-only 调用边界、Responses generation/streaming、Files API、多模态 embedding、capability 和 replay。
- [anthropic-adapter.CN.md](anthropic-adapter.CN.md)：Python Anthropic adapter 实现方案与实现记录，覆盖 Messages API generation/streaming、图片理解、JSON Schema structured output、user-executed function tools、automatic prefix caching、usage/capability 和测试边界。

### Python Convenience

- [impls/python/pydantic-structured-output.CN.md](pydantic-structured-output.CN.md)：Python Pydantic structured output 便捷层方案与实现记录，覆盖 Pydantic helper、strict schema、最终响应解析、client convenience 和测试策略。

## 相关需求

- [REQ-2026-05-python-reference-implementation-roadmap.CN.md](../../requirements/REQ-2026-05-python-reference-implementation-roadmap.CN.md)：Python 参考实现路线图大需求。
- [REQ-2026-05-python-openai-adapter.CN.md](../../requirements/REQ-2026-05-python-openai-adapter.CN.md)：Python OpenAI adapter 需求记录。
- [REQ-2026-05-python-pydantic-structured-output.CN.md](../../requirements/REQ-2026-05-python-pydantic-structured-output.CN.md)：Python Pydantic structured output 需求记录。
- [REQ-2026-06-python-anthropic-adapter.CN.md](../../requirements/REQ-2026-06-python-anthropic-adapter.CN.md)：Python Anthropic adapter 需求记录。
- [REQ-2026-06-python-anthropic-structured-output.CN.md](../../requirements/REQ-2026-06-python-anthropic-structured-output.CN.md)：Python Anthropic structured output 需求记录。
- [REQ-2026-06-remote-context-cache-strategy.CN.md](../../requirements/REQ-2026-06-remote-context-cache-strategy.CN.md)：RemoteContextHint 与缓存策略升级需求记录。
