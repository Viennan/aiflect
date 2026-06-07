# REQ-2026-06-python-anthropic-reasoning

状态：Completed
创建日期：2026-06-07
最近更新：2026-06-07

## 背景

Python Anthropic adapter 已完成 Messages API generation、streaming、图片理解、structured output、function tools 和 automatic prefix caching。此前 adapter 能映射 provider 返回的 `thinking` / `redacted_thinking` content block，但请求侧 `ReasoningConfig` 会被拒绝。

Anthropic Messages API 当前通过 `thinking` 开启 extended thinking，通过 `output_config.effort` 表达 effort。`vatbrain` 已有通用 `ReasoningConfig`，因此本需求不新增 core 字段，只在 Anthropic provider-local mapper 中补齐请求映射。

## 目标

- 支持 Anthropic adapter 请求侧 `ReasoningConfig`。
- 保持 `ResponseFormat` structured output 与 reasoning effort 共用 `output_config` 时的安全合并。
- 保持 response / stream reasoning output 映射路径不变。
- 更新 capability、用户文档、实现文档和测试。
- 在 costly test 中为 Anthropic reasoning smoke 使用更大的 `max_output_tokens` 基线。

## 范围

- `ReasoningConfig.mode="disabled"/"none"` -> `thinking={"type": "disabled"}`。
- `ReasoningConfig.budget_tokens` -> `thinking={"type": "enabled", "budget_tokens": ...}`。
- `ReasoningConfig.mode="auto"/"enabled"/"adaptive"` -> `thinking={"type": "adaptive"}`。
- `ReasoningConfig.effort` -> `output_config.effort`，adapter 接收 `low`、`medium`、`high`、`max`、`xhigh`。
- `ReasoningConfig.summary` -> Anthropic `thinking.display` 的 summarized / omitted 控制。
- usage 中可用的 thinking token 明细映射到 `Usage.reasoning_tokens`。

## 非范围

- 不新增 core 字段。
- 不暴露 Anthropic explicit `thinking` 或 `output_config` 作为正式 provider option 编程模型。
- 不维护完整、动态的 Anthropic 模型能力真值表；模型能力仍可由用户通过 overrides 补充。
- 不支持 `ReasoningConfig.include_trace` 或 `reasoning.provider_options`。

## 当前进度

### 已完成子目标

- 已实现 Anthropic `ReasoningConfig` request mapping。
- 已实现 `output_config.format` 与 `output_config.effort` 合并。
- 已实现 active thinking 与 assistant prefill、temperature、top_k、forced tool choice 的本地不兼容检查。
- 已实现 manual `budget_tokens < max_tokens` 等基础校验。
- 已更新 Anthropic capability。
- 已补充 Anthropic mapper、capability 和 costly reasoning smoke 测试。
- 已同步设计、实现和用户文档。

### 剩余子目标

- 暂无。

## 相关知识库文档

- 设计文档：[anthropic-provider-support.CN.md](../design/anthropic-provider-support.CN.md)
- 实现文档：[anthropic-adapter.CN.md](../impls/python/anthropic-adapter.CN.md)
- 用户文档：[anthropic-quickstart.CN.md](../user/python/anthropic-quickstart.CN.md)
- API 参考：[api-reference.CN.md](../user/python/api-reference.CN.md)
- 第三方资料：
  - Anthropic extended thinking：https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
  - Anthropic effort：https://platform.claude.com/docs/en/build-with-claude/effort
  - Anthropic Messages API：https://docs.anthropic.com/en/api/messages

## 开放问题

- 是否维护 Anthropic 模型级 reasoning capability 真值表延后处理；当前 model capability 默认 unknown，用户可通过 overrides 显式补充。
