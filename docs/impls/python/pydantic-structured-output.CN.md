# Python Pydantic Structured Output 便捷层方案

文档类型：实现方案与实现记录
日期：2026-05-11  
最近更新：2026-05-11
引入需求：[REQ-2026-05-python-pydantic-structured-output.CN.md](../../requirements/REQ-2026-05-python-pydantic-structured-output.CN.md)

## 背景

`aiflect` 已将 `ResponseFormat` 收敛为 JSON Schema structured output 专用模型，不兼容 JSON mode / `json_object`。这保证了 core 抽象清晰，但 Python 用户在编写 schema 与解析返回值时仍需要手写 JSON Schema 和手动解析 JSON。

OpenAI Python SDK 已提供类似体验：用户可以把 Pydantic model 传给 `client.responses.parse(..., text_format=Model)`，SDK 会生成 structured output schema，并在响应上提供 `output_parsed`。`aiflect` 应参考这种编程体验，但不能绕过现有 provider-neutral request mapping、provider-native replay、snapshot 和 fallback 机制。

本方案补充 [v0.2-responses-contract-hardening.CN.md](v0.2-responses-contract-hardening.CN.md) 与 [v0.3-core-api-family-expansion.CN.md](v0.3-core-api-family-expansion.CN.md) 中的 structured output 设计，定位为 Python 语言层便捷能力，而不是新的 provider core 抽象。

## 设计目标

### 保持 core JSON Schema-only

`ResponseFormat` 仍是唯一进入 generation request 的 structured output 抽象。Pydantic 只用于 Python 侧生成 `ResponseFormat` 与解析最终文本，不新增 JSON mode、format selector 或 provider-specific parse path。

### 学习 OpenAI SDK 的体验，而不依赖其私有实现

用户应能用 Pydantic model 定义输出类型，并在调用后获得类型化结果。实现上不调用 OpenAI SDK 的 `responses.parse()`，也不依赖 `openai.lib._pydantic` 等私有 helper；OpenAI adapter 仍通过 `generate()` / `agenerate()` 走 aiflect 自己的 mapper。

### 可选依赖

Pydantic 不应成为 core 包的硬依赖。建议增加 optional extra：

```text
whero-aiflect[pydantic]
```

对应依赖范围：

```text
pydantic>=2,<3
```

### 最终响应优先

第一版只解析非流式最终 `GenerationResponse`，以及用户从 stream accumulator 重建出的最终 response。流式 partial JSON 增量解析暂不进入第一版。

## 非目标

- 不恢复 JSON mode / `json_object` 兼容。
- 不把 Pydantic model 直接放进 `GenerationRequest.response_format`。
- 不调用 provider SDK 的 parse shortcut。
- 不自动 retry 或修复不合法 JSON。
- 不在第一版支持 streaming partial parse。
- 不支持 Pydantic v1。

## 用户编程模型

### 显式 helper

推荐第一层 API 放在 `whero.aiflect.structured`，避免 `whero.aiflect` 顶层 import 强制加载 Pydantic。

```python
from pydantic import BaseModel

from whero.aiflect import MessageItem
from whero.aiflect.providers.openai import OpenAIClient
from whero.aiflect.structured import pydantic_output


class Contact(BaseModel):
    name: str
    email: str


client = OpenAIClient(api_key="...")
contact_output = pydantic_output(Contact, name="contact")

response = client.generate(
    model="gpt-5.1",
    items=[MessageItem.user("Extract a contact.")],
    response_format=contact_output.response_format,
)

parsed = contact_output.parse_response(response)
contact = parsed.output_parsed
```

`pydantic_output()` 返回一个可复用 spec：

```text
PydanticOutputSpec[T]
- output_type: Any
- response_format: ResponseFormat
- parse_text(text: str) -> T
- parse_response(response: GenerationResponse) -> ParsedGenerationResponse[T]
```

`ParsedGenerationResponse[T]`：

```text
- response: GenerationResponse
- output_text: str
- output_parsed: T
```

### Client convenience

为了贴近 OpenAI SDK 的 `output_parsed` 体验，provider client 可以增加薄封装方法：

```python
parsed = client.generate_parsed(
    model="gpt-5.1",
    items=[MessageItem.user("Extract a contact.")],
    output_type=Contact,
)

contact = parsed.output_parsed
raw_response = parsed.response
```

异步对应：

```python
parsed = await client.agenerate_parsed(
    model="gpt-5.1",
    items=[MessageItem.user("Extract a contact.")],
    output_type=Contact,
)
```

`generate_parsed()` 只做三件事：

1. 调用 `pydantic_output(output_type)` 生成 `ResponseFormat`。
2. 调用现有 `generate()`，保持 remote context、replay policy、tools、provider options 等行为不变。
3. 用同一个 spec 解析最终 `GenerationResponse`。

`generate_parsed()` 不接收 `response_format`。需要自定义 name/description/strict 时，用户应使用 `pydantic_output()` 显式 helper，并调用 `generate(..., response_format=spec.response_format)`。

## Schema 生成策略

### TypeAdapter

实现应基于 Pydantic v2 `TypeAdapter`：

```text
TypeAdapter(output_type).json_schema(mode="validation")
TypeAdapter(output_type).validate_json(output_text)
```

这样不仅支持 `BaseModel`，也为 Pydantic dataclass、`list[Model]` 等类型留下空间。但第一版文档和测试应以 `BaseModel` root object 为主，因为 provider 对非 object root schema 的支持可能不同。

### 默认 strict schema

`pydantic_output(..., strict=True)` 是推荐默认值，并应同时影响两件事：

- `ResponseFormat.json_schema_strict=True`。
- 对 Pydantic 生成的 JSON Schema 做 provider-compatible strict normalization。

strict normalization 建议规则：

- object schema 默认补 `additionalProperties: false`。
- object schema 的 properties 全部进入 `required`。
- 递归处理 `$defs`、`definitions`、`properties`、`items`、`anyOf`、`allOf`。
- 移除 `default: null`，避免 provider strict schema 接受度下降。
- 保留 Pydantic 生成的 title、description、enum、format 等可用 metadata。

这组规则参考 OpenAI SDK strict structured output 的实际行为，但由 `aiflect` 自行实现一个窄版本，不依赖 OpenAI SDK 私有 helper。

如果用户设置 `strict=False`，helper 应保留 Pydantic 原始 JSON Schema，并把 `ResponseFormat.json_schema_strict` 设置为 `False`。这不代表所有 provider 都会接受该 schema；provider 不支持时仍由 provider request error 暴露。

### Name 与 description

默认 `name` 规则：

- `BaseModel` class 使用 class name 的安全化版本。
- 其他类型使用 `response`。

默认 `description` 可以来自 Pydantic model docstring；用户显式传入时优先。

## 解析策略

### 输出文本提取

第一版从 `GenerationResponse.output_items` 中提取 assistant message 的 `TextPart`：

- 收集 assistant message 中的 text part。
- 按 output item 顺序拼接。
- 若没有可解析文本，抛出 `StructuredOutputParseError`。

该策略保持 provider-neutral。后续如 core 增加 `GenerationResponse.output_text` helper，可迁移到共享 helper。

### 错误模型

新增错误类型：

```text
StructuredOutputParseError(AiflectError)
- output_text: str | None
- response: GenerationResponse | None
- cause: BaseException | None
```

解析失败场景包括：

- response 中没有 assistant text。
- assistant text 不是合法 JSON。
- JSON 不满足 Pydantic model 校验。

错误不应吞掉原始 `GenerationResponse`，方便用户排查 provider refusal、截断或 schema 不匹配。

## 模块与文件

建议新增：

```text
python/whero/aiflect/structured.py
python/tests/unit/test_pydantic_structured_output.py
```

修改：

```text
python/pyproject.toml
python/whero/aiflect/providers/openai/client.py
docs/user/python/pydantic-structured-output.CN.md
docs/user/python/STATUS.md
docs/impls/python/STATUS.md
docs/INDEX.md
```

顶层 `whero.aiflect.__init__` 第一版可以不导出 Pydantic helper，推荐用户从 `whero.aiflect.structured` 导入。若后续要顶层导出，应使用 lazy import，避免未安装 Pydantic 时破坏基础 import。

## 测试方案

- `pydantic_output(BaseModel)` 生成 JSON Schema-only `ResponseFormat`。
- strict schema normalization 覆盖嵌套 object、array items、`anyOf`、`$defs`、`default: null`。
- `parse_text()` 成功返回 Pydantic model。
- `parse_response()` 能从 normalized assistant message 提取并解析 text。
- 非 JSON / validation error 抛 `StructuredOutputParseError`，并保留 cause 与 output text。
- `generate_parsed()` 调用现有 `generate()`，传入生成的 `response_format`，返回 `ParsedGenerationResponse[T]`。
- 未安装 Pydantic 时，导入基础 `whero.aiflect` 不失败；调用 Pydantic helper 时给出安装提示。

## 实施步骤

### Step 1: Helper module

- 新增 `whero.aiflect.structured`。
- 定义 `PydanticOutputSpec`、`ParsedGenerationResponse`、`StructuredOutputParseError`、`pydantic_output()`。
- 实现 Pydantic lazy import 与 TypeAdapter schema/validation。

### Step 2: Strict schema normalization

- 实现窄版 recursive normalizer。
- 增加 schema snapshot/unit tests。
- 明确不引入 OpenAI 私有 helper 依赖。

### Step 3: Client convenience

- 在 `OpenAIClient` 增加 `generate_parsed()` / `agenerate_parsed()` 薄封装。
- 复用现有 `generate()` / `agenerate()`，不调用 OpenAI SDK parse shortcut。
- 保持 remote context、provider-native replay、snapshot、fallback 行为一致。

### Step 4: 文档

- 用户文档加入安装 extra、显式 helper、client convenience、错误处理示例。
- 实现状态文档标记 Pydantic structured output helper 已完成。

## 实现结果

- 新增 `whero.aiflect.structured`，提供 `pydantic_output()`、`PydanticOutputSpec`、`ParsedGenerationResponse` 与 `StructuredOutputParseError`。
- 新增 optional extra `whero-aiflect[pydantic]`，测试 extra 同步包含 Pydantic v2。
- `OpenAIClient` 新增 `generate_parsed()` / `agenerate_parsed()`，内部仍复用 `generate()` / `agenerate()`。
- 新增单元测试覆盖 schema 生成、strict normalization、响应解析、解析错误与 OpenAI parsed convenience。

验证：

```bash
cd python
../.venv/bin/python -m pytest
```

## 风险与决策点

### Strict normalization 会改变 Pydantic 默认语义

Pydantic 的 optional/default 字段在 JSON Schema 中通常不是 required。provider strict structured output 往往要求 object properties 全部 required；此时可通过 nullable 类型表达“可为空”，而不是通过缺省字段表达“可省略”。文档应明确推荐用户把可选字段写成 `str | None` 等 nullable 类型。

### Provider schema 子集差异

不同 provider 对 JSON Schema 子集支持不完全一致。Pydantic helper 只负责生成通用 JSON Schema 与解析结果；provider 是否接受某些关键字仍由 adapter/provider error 暴露。后续可按 provider 增加 schema compatibility diagnostics，但不应把 provider-specific schema 分支塞进 core `ResponseFormat`。

### 多文本输出的解析边界

Structured output 的理想响应应是单个 JSON 文本。若 provider 返回多个 assistant text part，第一版按顺序拼接；如果拼接后不是合法 JSON，则抛解析错误。后续可增加更显式的 `output_text` 归一化 helper。

### Streaming partial parse

OpenAI SDK 已展示 structured output streaming parse 的方向，但 aiflect 第一版不做 partial parse。用户如需流式 UI，可先消费 text delta，再用 accumulator 得到最终 response 后解析。

## 参考资料

- [OpenAI Structured Outputs guide](https://platform.openai.com/docs/guides/structured-outputs?api-mode=responses&lang=python)
- [OpenAI Python SDK helpers](https://github.com/openai/openai-python/blob/main/helpers.md)
- [Pydantic TypeAdapter docs](https://docs.pydantic.dev/latest/api/type_adapter/)
- [Pydantic JSON Schema docs](https://docs.pydantic.dev/latest/concepts/json_schema/)
- [v0.2-responses-contract-hardening.CN.md](v0.2-responses-contract-hardening.CN.md)
- [v0.3-core-api-family-expansion.CN.md](v0.3-core-api-family-expansion.CN.md)
