# aiflect 知识库索引

状态：持续维护
最近更新：2026-07-06

## Requirements

- [requirements/STATUS.md](requirements/STATUS.md)：需求状态总览，作为了解当前需求、状态和粗粒度实现进度的启发式入口。
- [requirement-template.CN.md](requirements/requirement-template.CN.md)：单需求管理文档模板，提供可调整的轻量结构，用于记录需求目标、范围、进度、相关文档和开放问题。
- [REQ-2026-05-python-reference-implementation-roadmap.CN.md](requirements/REQ-2026-05-python-reference-implementation-roadmap.CN.md)：Python 参考实现路线图大需求，记录 v0.2 到 v0.5 的阶段目标、完成状态和后续关注项。
- [REQ-2026-05-python-openai-adapter.CN.md](requirements/REQ-2026-05-python-openai-adapter.CN.md)：Python OpenAI adapter 需求记录，说明首个 provider adapter 与基础 core 能力落地目标和完成进度。
- [REQ-2026-05-python-pydantic-structured-output.CN.md](requirements/REQ-2026-05-python-pydantic-structured-output.CN.md)：Python Pydantic structured output 需求记录，跟踪 Pydantic helper、strict schema 和 parsed response convenience。
- [REQ-2026-06-python-anthropic-adapter.CN.md](requirements/REQ-2026-06-python-anthropic-adapter.CN.md)：Python Anthropic adapter 需求记录，记录 Messages API generation/streaming、图片理解、user-executed function tools 和 automatic prefix caching 支持的完成状态。
- [REQ-2026-06-python-anthropic-structured-output.CN.md](requirements/REQ-2026-06-python-anthropic-structured-output.CN.md)：Python Anthropic structured output 需求记录，说明 `ResponseFormat -> output_config.format`、parsed helpers、capability 与测试完成状态。
- [REQ-2026-06-python-anthropic-reasoning.CN.md](requirements/REQ-2026-06-python-anthropic-reasoning.CN.md)：Python Anthropic reasoning 需求记录，说明 `ReasoningConfig -> thinking/output_config.effort`、capability、测试与文档完成状态。
- [REQ-2026-06-remote-context-cache-strategy.CN.md](requirements/REQ-2026-06-remote-context-cache-strategy.CN.md)：RemoteContextHint 与缓存策略升级记录，说明 `enable_cache/new_items_start_index`、response-style 自动 response id 管理、失效 refresh 和 Anthropic automatic cache 的新语义。
- [REQ-2026-06-session-cache-strategy.CN.md](requirements/REQ-2026-06-session-cache-strategy.CN.md)：Session cache 策略需求记录，说明 `RemoteContextHint.session_key`、OpenAI `prompt_cache_key`、Volcengine Responses API Session 缓存与 1h 生命周期管理的实现状态。
- [REQ-2026-06-python-deepseek-provider.CN.md](requirements/REQ-2026-06-python-deepseek-provider.CN.md)：Python DeepSeek provider 需求记录，说明 Anthropic 兼容接口、`api_format` 初始化参数、reasoning、工具、cache hint 兼容和 OpenAI completion 预留状态。
- [REQ-2026-07-package-rename-aiflect.CN.md](requirements/REQ-2026-07-package-rename-aiflect.CN.md)：Package rename 需求记录，说明旧项目名迁移到 `aiflect` 后的公开包名、导入路径、目录、错误基类、环境变量前缀和文档同步范围。
- [REQ-2026-07-openai-response-delta-adapter-options.CN.md](requirements/REQ-2026-07-openai-response-delta-adapter-options.CN.md)：OpenAI response delta adapter options 需求记录，说明 `ClientConfig.adapter_options` 的 wrapper 行为配置定位、OpenAI `response_delta=False` 禁用 previous-response 差分传输和文档/测试同步范围。

## Design

- [draft.CN.md](design/draft.CN.md)：项目冷启动草稿，记录 `aiflect` 的初始目标和早期设计构想。
- [high-level-design.CN.md](design/high-level-design.CN.md)：高层次设计方案，定义设计哲学、模块职责、核心抽象、capability 来源与可靠性、非目标、演进路线和 FAQ。
- [provider-capability-integration.CN.md](design/provider-capability-integration.CN.md)：Provider 能力整合设计，基于火山方舟资料完善 provider-side state、文件资源、多模态 embedding、media generation 和异步任务等跨厂商抽象；provider-hosted/remote tools 暂缓进入通用 core。
- [provider-native-replay.CN.md](design/provider-native-replay.CN.md)：Provider 原生重放设计，规划 provider item snapshot、显式 replay policy、强制 replay、remote context 覆盖范围、OpenAI 差分传输、OpenAI `phase` 语义评估与跨 provider replay 长期 TODO。
- [session-cache-strategy.CN.md](design/session-cache-strategy.CN.md)：Session cache 策略设计，定义 `RemoteContextHint.session_key` 的 Full-context First 语义、provider 映射、Volcengine 生命周期策略、模块职责和 FAQ。
- [anthropic-provider-support.CN.md](design/anthropic-provider-support.CN.md)：Anthropic provider 支持设计，定义 Messages API provider adapter 范围、structured output、cache hint 映射、response id 兼容、工具执行责任和 capability 语义。
- [deepseek-provider-support.CN.md](design/deepseek-provider-support.CN.md)：DeepSeek provider 支持设计，定义 Anthropic 兼容接口首期范围、`api_format`、reasoning、cache hint 兼容、tool control 与 capability 语义。

## Third-party References

- [3rds/INDEX.md](3rds/INDEX.md)：第三方资料总索引，说明外部厂商资料在知识库中的定位。
- [deepseek/INDEX.md](3rds/deepseek/INDEX.md)：DeepSeek 第三方资料索引，记录 Anthropic 兼容接口支持范围和实现约束摘录。
- [volengine/INDEX.md](3rds/volengine/INDEX.md)：火山方舟资料索引，归纳 Responses、Responses API 上下文缓存与专题教程、详细参数 reference、Chat、Files 与 file object reference、多模态 embedding API reference、图片/视频理解、图片/视频生成及 API reference、结构化输出、函数调用、reasoning 与 streaming。

## Impls

- [impls/python/INDEX.md](impls/python/INDEX.md)：Python 实现文档局部索引，按当前实现基线、Core/API family、provider adapters、Python convenience 和相关需求组织 `docs/impls/python` 文档。
- [openai-adapter.CN.md](impls/python/openai-adapter.CN.md)：Python OpenAI adapter 实现方案，描述首个 provider adapter 的范围、核心模型、OpenAI 映射、测试策略与实现步骤。
- [v0.5-media-generation.CN.md](impls/python/v0.5-media-generation.CN.md)：Python v0.5 Media Generation 方案与实现记录，明确 hosted tools 暂不进入范围，基于 OpenAI Images API 与 Volcengine Ark Images/Content Generation 完成通用图片生成、参考图生成、图片流式生成、视频异步任务和图片/视频 AI 水印控制。
- [volcengine-adapter.CN.md](impls/python/volcengine-adapter.CN.md)：Python v0.4 Volcengine adapter MVP 详细方案与实现记录，定义 provider identity、Ark SDK-only 调用边界、Responses generation/streaming、Files API、多模态 embedding、capability、replay、测试与验收结果。
- [anthropic-adapter.CN.md](impls/python/anthropic-adapter.CN.md)：Python Anthropic adapter 实现方案与实现记录，覆盖官方 Anthropic SDK Messages API、generation/streaming、图片理解、JSON Schema structured output、function tools、automatic prefix caching、usage/capability 和测试策略。
- [deepseek-adapter.CN.md](impls/python/deepseek-adapter.CN.md)：Python DeepSeek adapter 实现记录，覆盖 Anthropic 兼容 Messages API、`api_format`、text generation/streaming、function tools、reasoning、cache hint 兼容、usage/capability 和测试策略。
- [remote-context-cache-strategy.CN.md](impls/python/remote-context-cache-strategy.CN.md)：Python Remote Context 与 Cache 策略实现记录，说明新 `RemoteContextHint`、snapshot response id、response-style suffix/refresh 和 Anthropic full messages cache 行为。
- [session-cache-strategy.CN.md](impls/python/session-cache-strategy.CN.md)：Python Session Cache 策略实现记录，说明 `RemoteContextHint.session_key`、OpenAI `prompt_cache_key` 映射、Volcengine Session cache 参数所有权、过期前 refresh 与测试验收。
- [v0.2-responses-contract-hardening.CN.md](impls/python/v0.2-responses-contract-hardening.CN.md)：Python v0.2 Responses Contract Hardening 设计方案，细化 OpenAI Responses API 参数映射、structured output、streaming event、stream accumulator、错误映射与验收测试。
- [v0.3-core-api-family-expansion.CN.md](impls/python/v0.3-core-api-family-expansion.CN.md)：Python v0.3 Core API Family Expansion 实现基线，系统说明 items、generation、embedding、resources、media、function/custom tools、capabilities、OpenAI adapter、Pydantic helper 与 replay 的已实现边界。
- [impls/python/pydantic-structured-output.CN.md](impls/python/pydantic-structured-output.CN.md)：Python Pydantic Structured Output 便捷层方案与实现记录，说明可选 Pydantic v2 helper、strict schema 生成、最终响应解析、client convenience 与测试策略。
- [package-rename-aiflect.CN.md](impls/python/package-rename-aiflect.CN.md)：Python package rename 实现记录，说明源码目录、import 路径、distribution name、错误基类和环境变量前缀的重命名影响面。
- [impls/python/STATUS.md](impls/python/STATUS.md)：Python 实现状态，记录当前基线、OpenAI/Volcengine/Anthropic/DeepSeek adapter 已实现范围、暂不实现项、后续阶段和验证方式。

## User Docs

- [quickstart.CN.md](user/python/quickstart.CN.md)：Python 快速开始，按渐进路径说明 OpenAI/Volcengine client、generation、remote context/replay、streaming、图片/视频生成、structured output、工具调用、embedding、capability 和错误处理。
- [api-reference.CN.md](user/python/api-reference.CN.md)：Python API 参考，完整覆盖当前暴露给用户的 core 数据结构、枚举、provider client、structured output helper、capability、usage、错误类型、媒体生成水印控制和 OpenAI/Volcengine/Anthropic adapter 支持范围。
- [volcengine-quickstart.CN.md](user/python/volcengine-quickstart.CN.md)：Volcengine / 火山方舟 provider 快速开始，说明 Ark SDK-only 安装、generation、streaming、图片生成、视频任务、Files API、多模态 embedding、function tools、remote context 和限制。
- [anthropic-quickstart.CN.md](user/python/anthropic-quickstart.CN.md)：Anthropic provider 快速开始，说明官方 Anthropic SDK Messages API 安装、generation、图片理解、JSON Schema structured output、ReasoningConfig、automatic prefix caching、streaming、function tools、capability 和限制。
- [deepseek-quickstart.CN.md](user/python/deepseek-quickstart.CN.md)：DeepSeek provider 快速开始，说明 Anthropic 兼容接口安装、`api_format`、文本生成、streaming、reasoning、function tools、cache hint 兼容、capability 和限制。
- [user/python/pydantic-structured-output.CN.md](user/python/pydantic-structured-output.CN.md)：Python Pydantic Structured Output 编程模型，说明 Pydantic helper、client convenience、strict schema、错误处理与流式限制。
- [user/python/STATUS.md](user/python/STATUS.md)：Python 用户文档状态，记录当前文档结构、已覆盖 public surface、后续维护规则和待完善项。
