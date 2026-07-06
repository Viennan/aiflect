# REQ-2026-05-python-pydantic-structured-output

状态：Completed
创建日期：2026-05-11
最近更新：2026-06-04

## 背景

`aiflect` core 已将 `ResponseFormat` 收敛为 JSON Schema structured output 模型，但 Python 用户仍需要手写 JSON Schema 和手动解析 JSON。

## 目标

提供可选的 Python Pydantic v2 便捷层，在不改变 core JSON Schema-only 原则的前提下，支持从 Pydantic type 生成 schema 并解析最终响应。

## 当前进度

### 已完成子目标

- `pydantic_output()` helper 已实现。
- Strict schema 默认行为与 schema metadata 已明确。
- `generate_parsed()` / `agenerate_parsed()` client convenience 已实现。
- 用户文档和 API reference 已同步。

### 剩余子目标

暂无。

## 相关知识库文档

- [impls/python/pydantic-structured-output.CN.md](../impls/python/pydantic-structured-output.CN.md)
- [user/python/pydantic-structured-output.CN.md](../user/python/pydantic-structured-output.CN.md)
- [api-reference.CN.md](../user/python/api-reference.CN.md)
- [REQ-2026-05-python-reference-implementation-roadmap.CN.md](REQ-2026-05-python-reference-implementation-roadmap.CN.md)

## 开放问题

暂无。
