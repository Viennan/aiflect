# REQ-2026-06-python-anthropic-structured-output

状态：Completed
创建日期：2026-06-07
最近更新：2026-06-07

## 背景

Python Anthropic adapter 已完成 Messages API generation、streaming、图片理解、user-executed function tools 和 automatic prefix caching，但 `ResponseFormat` 在首版实现中暂不支持。Anthropic Messages API 当前支持 structured outputs，主路径是 `output_config.format` 的 JSON Schema 形态；Python SDK 的 `messages.parse()` 是便捷层，不应绕过 `vatbrain` 自身的 request mapping、response mapping、snapshot 和 Pydantic helper。

本需求记录为 Anthropic provider 引入 `ResponseFormat` structured output 的范围和完成状态。详细设计见 [anthropic-provider-support.CN.md](../design/anthropic-provider-support.CN.md)，Python 实现记录见 [anthropic-adapter.CN.md](../impls/python/anthropic-adapter.CN.md)。

## 目标

- 在 Anthropic adapter 中支持 `ResponseFormat` JSON Schema structured output。
- 复用既有 `ResponseFormat` core 模型，不新增 Anthropic-specific core 字段。
- 复用既有 Python Pydantic helper 与最终响应解析模型。
- 在 Anthropic client 中提供 `generate_parsed()` / `agenerate_parsed()`，与 OpenAI/Volcengine provider 体验保持一致。
- 更新 capability 与用户文档，使用户能够通过能力查询识别 Anthropic structured output 支持。

## 范围

- 将 `GenerationRequest.response_format` 映射为 Anthropic `output_config.format`：

```text
ResponseFormat.json_schema
  -> output_config.format.schema

output_config.format.type = "json_schema"
```

- 保留 `json_schema_name`、`json_schema_description` 与 `json_schema_strict` 的 vatbrain 侧语义，不把它们映射到 Anthropic payload 中未明确支持的字段。
- 拒绝用户通过 `provider_options["output_config"]` 或 `provider_options["output_format"]` 绕过 adapter-owned structured output 映射。
- structured output 与 assistant message prefill 同用时提前抛出 `UnsupportedCapabilityError`。
- 支持 sync/async parsed helper。
- 更新 Anthropic adapter capability：`generation.structured_output=True`。

## 非范围

- 不支持 JSON mode / `json_object`。
- 不调用 Anthropic SDK `messages.parse()`。
- 不暴露旧 beta `output_format` 作为正式编程模型。
- 不实现 streaming partial JSON 增量解析；streaming 仍输出 text delta，用户可在最终响应上解析。
- 不引入 Anthropic-specific schema 字段到 core。

## 当前进度

### 已完成子目标

- 已实现 `ResponseFormat -> output_config.format` request mapping。
- 已拒绝 `output_config` / `output_format` provider option 隐式入口。
- 已实现 structured output 与 assistant prefill 的不兼容检查。
- 已实现 `AnthropicClient.generate_parsed()` / `agenerate_parsed()`。
- 已更新 Anthropic capability。
- 已补充 mapper、client 和 capability 单元测试。
- 已补充 structured output costly smoke test，按 `supports_structured_output` 模型能力声明选择是否执行。
- 已同步设计、实现、用户文档和索引。

### 剩余子目标

- 暂无。

## 相关知识库文档

- 设计文档：[anthropic-provider-support.CN.md](../design/anthropic-provider-support.CN.md)
- 实现文档：[anthropic-adapter.CN.md](../impls/python/anthropic-adapter.CN.md)
- Anthropic 用户指南：[anthropic-quickstart.CN.md](../user/python/anthropic-quickstart.CN.md)
- Pydantic structured output：[pydantic-structured-output.CN.md](../user/python/pydantic-structured-output.CN.md)
- 第三方资料：
  - Anthropic structured outputs：https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs
  - Anthropic Messages API：https://docs.anthropic.com/en/api/messages
  - Anthropic Python SDK：https://docs.anthropic.com/en/api/sdks/python

## 开放问题

- 是否为 Anthropic structured output 维护模型级 capability 真值表仍延后；当前 model capability 默认 unknown，用户可通过 overrides 显式补充。
