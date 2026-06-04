# vatbrain 知识库索引

状态：持续维护
最近更新：2026-06-04

## Requirements

- [requirements/STATUS.md](requirements/STATUS.md)：需求状态总览，作为了解当前需求、状态和粗粒度实现进度的启发式入口。
- [requirement-template.CN.md](requirements/requirement-template.CN.md)：单需求管理文档模板，提供可调整的轻量结构，用于记录需求目标、范围、进度、相关文档和开放问题。
- [REQ-2026-05-python-reference-implementation-roadmap.CN.md](requirements/REQ-2026-05-python-reference-implementation-roadmap.CN.md)：Python 参考实现路线图大需求，记录 v0.2 到 v0.5 的阶段目标、完成状态和后续关注项。
- [REQ-2026-05-python-openai-adapter.CN.md](requirements/REQ-2026-05-python-openai-adapter.CN.md)：Python OpenAI adapter 需求记录，说明首个 provider adapter 与基础 core 能力落地目标和完成进度。
- [REQ-2026-05-python-pydantic-structured-output.CN.md](requirements/REQ-2026-05-python-pydantic-structured-output.CN.md)：Python Pydantic structured output 需求记录，跟踪 Pydantic helper、strict schema 和 parsed response convenience。

## Design

- [draft.CN.md](design/draft.CN.md)：项目冷启动草稿，记录 `vatbrain` 的初始目标和早期设计构想。
- [high-level-design.CN.md](design/high-level-design.CN.md)：高层次设计方案，定义设计哲学、模块职责、核心抽象、capability 来源与可靠性、非目标、演进路线和 FAQ。
- [provider-capability-integration.CN.md](design/provider-capability-integration.CN.md)：Provider 能力整合设计，基于火山方舟资料完善 provider-side state、文件资源、多模态 embedding、media generation 和异步任务等跨厂商抽象；provider-hosted/remote tools 暂缓进入通用 core。
- [provider-native-replay.CN.md](design/provider-native-replay.CN.md)：Provider 原生重放设计，规划 provider item snapshot、显式 replay policy、强制 replay、remote context 覆盖范围、OpenAI 差分传输、OpenAI `phase` 语义评估与跨 provider replay 长期 TODO。

## Third-party References

- [3rds/INDEX.md](3rds/INDEX.md)：第三方资料总索引，说明外部厂商资料在知识库中的定位。
- [volengine/INDEX.md](3rds/volengine/INDEX.md)：火山方舟资料索引，归纳 Responses、Responses API 专题教程与详细参数 reference、Chat、Files 与 file object reference、多模态 embedding API reference、图片/视频理解、图片/视频生成及 API reference、结构化输出、函数调用、reasoning 与 streaming。

## Impls

- [impls/python/INDEX.md](impls/python/INDEX.md)：Python 实现文档局部索引，按当前实现基线、Core/API family、provider adapters、Python convenience 和相关需求组织 `docs/impls/python` 文档。
- [openai-adapter.CN.md](impls/python/openai-adapter.CN.md)：Python OpenAI adapter 实现方案，描述首个 provider adapter 的范围、核心模型、OpenAI 映射、测试策略与实现步骤。
- [v0.5-media-generation.CN.md](impls/python/v0.5-media-generation.CN.md)：Python v0.5 Media Generation 方案与实现记录，明确 hosted tools 暂不进入范围，基于 OpenAI Images API 与 Volcengine Ark Images/Content Generation 完成通用图片生成、参考图生成、图片流式生成、视频异步任务和图片/视频 AI 水印控制。
- [volcengine-adapter.CN.md](impls/python/volcengine-adapter.CN.md)：Python v0.4 Volcengine adapter MVP 详细方案与实现记录，定义 provider identity、Ark SDK-only 调用边界、Responses generation/streaming、Files API、多模态 embedding、capability、replay、测试与验收结果。
- [v0.2-responses-contract-hardening.CN.md](impls/python/v0.2-responses-contract-hardening.CN.md)：Python v0.2 Responses Contract Hardening 设计方案，细化 OpenAI Responses API 参数映射、structured output、streaming event、stream accumulator、错误映射与验收测试。
- [v0.3-core-api-family-expansion.CN.md](impls/python/v0.3-core-api-family-expansion.CN.md)：Python v0.3 Core API Family Expansion 实现基线，系统说明 items、generation、embedding、resources、media、function/custom tools、capabilities、OpenAI adapter、Pydantic helper 与 replay 的已实现边界。
- [impls/python/pydantic-structured-output.CN.md](impls/python/pydantic-structured-output.CN.md)：Python Pydantic Structured Output 便捷层方案与实现记录，说明可选 Pydantic v2 helper、strict schema 生成、最终响应解析、client convenience 与测试策略。
- [impls/python/STATUS.md](impls/python/STATUS.md)：Python 实现状态，记录 v0.5 当前基线、OpenAI/Volcengine adapter 已实现范围、暂不实现项、后续阶段和验证方式。

## User Docs

- [quickstart.CN.md](user/python/quickstart.CN.md)：Python 快速开始，按渐进路径说明 OpenAI/Volcengine client、generation、remote context/replay、streaming、图片/视频生成、structured output、工具调用、embedding、capability 和错误处理。
- [api-reference.CN.md](user/python/api-reference.CN.md)：Python API 参考，完整覆盖当前暴露给用户的 core 数据结构、枚举、provider client、structured output helper、capability、usage、错误类型、媒体生成水印控制和 OpenAI/Volcengine adapter 支持范围。
- [volcengine-quickstart.CN.md](user/python/volcengine-quickstart.CN.md)：Volcengine / 火山方舟 provider 快速开始，说明 Ark SDK-only 安装、generation、streaming、图片生成、视频任务、Files API、多模态 embedding、function tools、remote context 和限制。
- [user/python/pydantic-structured-output.CN.md](user/python/pydantic-structured-output.CN.md)：Python Pydantic Structured Output 编程模型，说明 Pydantic helper、client convenience、strict schema、错误处理与流式限制。
- [user/python/STATUS.md](user/python/STATUS.md)：Python 用户文档状态，记录当前文档结构、已覆盖 public surface、后续维护规则和待完善项。
