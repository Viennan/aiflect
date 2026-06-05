# 需求状态总览

状态：持续维护
最近更新：2026-06-06

## 定位

本文件是需求管理入口，用于帮助新会话了解当前需求、需求状态和粗粒度实现进度。它不替代 `docs/design`、`docs/impls` 或 `docs/user` 中的系统设计、实现设计和用户文档。

编码 AI 可以把本文件作为了解当前迭代状态的启发式入口，再根据用户请求、相关链接和代码现状自主选择需要继续阅读的文档。

本目录仅维护涉及项目非测试代码改动的需求。仅文档、仅测试、工作流调整或仓库 housekeeping 不纳入需求管理。

## 状态约定

- `Discussing`：需求讨论中。
- `Accepted`：需求已接受，但设计或实现边界仍在收敛。
- `Ready`：关键设计与实现边界已足够明确，可以进入实现。
- `Implementing`：实现中，可记录已经完成的需求级子目标。
- `Verifying`：主要实现已完成，正在测试、文档同步或验收。
- `Completed`：已完成并同步相关知识库文档。
- `Deferred`：延后处理。
- `Discarded`：废弃。

## Active Requirements

暂无。

## Recently Completed

| Requirement | Status | Progress | Requirement Doc | Key Docs | Updated |
| --- | --- | --- | --- | --- | --- |
| Python Anthropic adapter | `Completed` | Anthropic Messages API generation/streaming、图片理解、function tools、automatic prefix caching 和 capability 已落地 | [REQ-2026-06-python-anthropic-adapter.CN.md](REQ-2026-06-python-anthropic-adapter.CN.md) | [anthropic-provider-support.CN.md](../design/anthropic-provider-support.CN.md), [anthropic-adapter.CN.md](../impls/python/anthropic-adapter.CN.md), [anthropic-quickstart.CN.md](../user/python/anthropic-quickstart.CN.md) | 2026-06-06 |
| Python reference implementation roadmap | `Completed` | v0.2 到 v0.5 阶段目标已完成，后续关注项保留在需求文档中 | [REQ-2026-05-python-reference-implementation-roadmap.CN.md](REQ-2026-05-python-reference-implementation-roadmap.CN.md) | [impls/python/STATUS.md](../impls/python/STATUS.md) | 2026-06-04 |
| Python OpenAI adapter | `Completed` | 首个 provider adapter 与基础 core 能力已落地 | [REQ-2026-05-python-openai-adapter.CN.md](REQ-2026-05-python-openai-adapter.CN.md) | [openai-adapter.CN.md](../impls/python/openai-adapter.CN.md) | 2026-06-04 |
| Python Pydantic structured output | `Completed` | Pydantic helper、strict schema 和 parsed response convenience 已落地 | [REQ-2026-05-python-pydantic-structured-output.CN.md](REQ-2026-05-python-pydantic-structured-output.CN.md) | [impls/python/pydantic-structured-output.CN.md](../impls/python/pydantic-structured-output.CN.md), [user/python/pydantic-structured-output.CN.md](../user/python/pydantic-structured-output.CN.md) | 2026-06-04 |

## Deferred / Discarded

暂无。

## 模板

可参考 [requirement-template.CN.md](requirement-template.CN.md) 创建单个需求管理文档。模板只提供起点，具体字段和结构可以根据需求规模调整。
