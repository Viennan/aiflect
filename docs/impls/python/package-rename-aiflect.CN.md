# Python package rename to aiflect

状态：已完成
日期：2026-07-06
最近更新：2026-07-06

## 背景

本记录说明 Python 参考实现重命名为 `aiflect` 的实现影响面。需求记录见 [REQ-2026-07-package-rename-aiflect.CN.md](../../requirements/REQ-2026-07-package-rename-aiflect.CN.md)。

## 实现影响面

- 源码目录：`python/whero/aiflect`。
- Python import 路径：`whero.aiflect`。
- Python distribution name：`whero-aiflect`。
- Optional extras 示例：`whero-aiflect[pydantic]`、`whero-aiflect[volcengine]`、`whero-aiflect[anthropic]`、`whero-aiflect[deepseek]`。
- 错误基类：`AiflectError`。
- 项目环境变量前缀：`AIFLECT` / `ENV_AIFLECT_`。

## 兼容性说明

本次重命名不提供旧 import 路径兼容层。用户代码需要从 `whero.aiflect` 导入；依赖声明需要使用 `whero-aiflect`。Provider adapter 的请求/响应映射、capability、remote context、session cache 和 media generation 行为不因本次重命名改变。

## 验证

- 扫描确认仓库中不再保留旧项目名。
- 运行 Python 单元测试确认新包路径可导入，既有 adapter 行为仍通过测试。
