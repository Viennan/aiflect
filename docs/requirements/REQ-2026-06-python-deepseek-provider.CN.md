# REQ-2026-06-python-deepseek-provider

状态：Completed
创建日期：2026-06-07
最近更新：2026-06-07

## 背景

DeepSeek 同时提供 Anthropic 兼容接口与 OpenAI completion 兼容接口。当前 `aiflect` 已有 Anthropic Messages API adapter，实现 DeepSeek Anthropic 兼容接口可以用较低成本补充 DeepSeek provider，并保持与现有 generation、streaming、function tools、reasoning 和 capability 模型一致。

详细设计见 [deepseek-provider-support.CN.md](../design/deepseek-provider-support.CN.md)，Python 实现记录见 [deepseek-adapter.CN.md](../impls/python/deepseek-adapter.CN.md)。

## 目标

- 新增 Python DeepSeek provider adapter。
- 在 client 初始化中新增 `api_format` 参数，支持 `"anthropic"` 与预留 `"openai_completion"` 两种取值。
- 首期仅实现 `api_format="anthropic"`；`"openai_completion"` fail fast。
- 保留 `base_url` 初始化参数，并为 Anthropic 兼容模式提供默认 base URL。
- 支持文本 generation、streaming、async generation/streaming、function tools、reasoning config、usage 和 provider-native snapshot replay。

## 范围

- 新增 `whero.aiflect.providers.deepseek` provider package。
- 新增 optional dependency：`whero-aiflect[deepseek]`，当前复用 `anthropic` SDK。
- 使用 Anthropic Python SDK 的 `Anthropic` / `AsyncAnthropic` 与 `messages.create` 调用 DeepSeek Anthropic 兼容接口。
- 支持 text-only input、system/developer 初始 instruction prefix、function tool、tool use/result、thinking/reasoning、streaming event、usage 和 capability。
- `RemoteContextHint.enable_cache=True` 兼容接收但不下发 `cache_control`。

## 非范围

- 暂不实现 `api_format="openai_completion"`。
- 不支持 DeepSeek OpenAI completion 兼容接口。
- 不支持 image/document/file/audio/video input。
- 不支持 `ResponseFormat` structured output 或 Pydantic parsed convenience。
- 不支持 Files API、embedding、media generation。
- 不支持 explicit Anthropic `cache_control`。
- 不支持可靠禁用 parallel tool calls。
- 不维护内部 DeepSeek model capability 真值表。

## 当前进度

### 已完成子目标

- 已新增 DeepSeek provider package、client、mapper、stream mapper 和 capability。
- 已新增 `deepseek` optional extra。
- 已实现 `api_format` 初始化参数、默认 base URL 和 `openai_completion` fail-fast。
- 已实现 text generation、streaming、async、function tools、reasoning、usage 和 provider-native snapshot replay。
- 已新增 DeepSeek unit tests，并接入 costly test provider 工厂。
- 已同步设计、实现、用户文档、第三方资料摘录、API reference、quickstart、TEST.md 和状态索引。

### 剩余子目标

- 后续单独设计并实现 `api_format="openai_completion"`。
- 可选真实 DeepSeek API costly tests 按凭据配置运行。

## 相关知识库文档

- 设计文档：[deepseek-provider-support.CN.md](../design/deepseek-provider-support.CN.md)
- 实现文档：[deepseek-adapter.CN.md](../impls/python/deepseek-adapter.CN.md)
- 用户指南：[deepseek-quickstart.CN.md](../user/python/deepseek-quickstart.CN.md)
- 第三方资料：[anthropic_api.CN.md](../3rds/deepseek/anthropic_api.CN.md)
- 官方资料：https://api-docs.deepseek.com/guides/anthropic_api

## 开放问题

- OpenAI completion 兼容形态是否复用现有 OpenAI adapter 的 Responses/Chat 抽象，还是新增 DeepSeek-specific completion mapper，后续设计时再确认。
- DeepSeek 官方兼容表如扩展 image/document 或 structured output，需要同步调整 capability 与 mapper。

