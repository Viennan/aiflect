# REQ-2026-07-package-rename-aiflect

状态：Completed
创建日期：2026-07-06
最近更新：2026-07-06

## 背景

项目包名重命名为 `aiflect`。本次变更属于公开编程模型与仓库结构调整，需要同步 Python 包路径、分发名、测试、脚本、配置和知识库文档。

## 目标

统一使用 `aiflect` 作为项目与 Python package name，避免代码、文档、测试和脚本继续暴露旧名称。

## 范围

- Python import 路径统一为 `whero.aiflect`。
- Python 源码目录统一为 `python/whero/aiflect`。
- Python distribution name 统一为 `whero-aiflect`。
- 错误基类统一为 `AiflectError`。
- 环境变量、测试标记、脚本内部名称和文档示例使用 `AIFLECT` / `aiflect`。
- AGENTS、TEST、知识库、测试代码、辅助测试脚本和相关配置同步更新。

## 非范围

- 不保留旧 import 路径兼容 shim。
- 不改变 provider adapter 的行为、调用协议或能力边界。
- 不调整版本号发布策略。

## 当前进度

### 已完成子目标

- 代码目录、import、测试、脚本和 `pyproject.toml` 已完成重命名。
- 文档中的旧项目名、包名、路径、环境变量前缀和示例已同步为新名称。
- 单元测试已用于验证新 import 路径和 provider adapter 行为。

### 剩余子目标

暂无。

## 相关知识库文档

- 实现文档：[package-rename-aiflect.CN.md](../impls/python/package-rename-aiflect.CN.md)
- 用户文档：[quickstart.CN.md](../user/python/quickstart.CN.md)、[api-reference.CN.md](../user/python/api-reference.CN.md)
- 状态入口：[STATUS.md](STATUS.md)

## 开放问题

暂无。
