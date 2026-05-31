# Python Pydantic Structured Output 编程模型

状态：已实现
日期：2026-05-11
最近更新：2026-05-13

## 定位

当前 structured output 使用 `ResponseFormat` 传入 JSON Schema。Pydantic 便捷层提供 Python 侧的 schema 定义与解析 helper，但不会改变 `vatbrain` 的 JSON Schema-only 原则，也不会兼容 JSON mode / `json_object`。

## 安装

通过 optional extra 安装：

```bash
pip install "whero-vatbrain[pydantic]"
```

仓库开发环境中对应：

```bash
cd python
.venv/bin/python -m pip install -e ".[test,pydantic]"
```

## 显式 helper 用法

```python
from pydantic import BaseModel

from whero.vatbrain import MessageItem
from whero.vatbrain.providers.openai import OpenAIClient
from whero.vatbrain.structured import pydantic_output


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

`contact_output.response_format` 是普通 `ResponseFormat`，因此现有 generation、remote context、ReplayPolicy、provider-native snapshot 行为都保持不变。

## Client convenience

OpenAI client 提供更接近 OpenAI SDK `output_parsed` 体验的薄封装：

```python
parsed = client.generate_parsed(
    model="gpt-5.1",
    items=[MessageItem.user("Extract a contact.")],
    output_type=Contact,
)

contact = parsed.output_parsed
raw_response = parsed.response
```

异步调用：

```python
parsed = await client.agenerate_parsed(
    model="gpt-5.1",
    items=[MessageItem.user("Extract a contact.")],
    output_type=Contact,
)
```

如果需要自定义 schema name、description 或 strict 行为，使用显式 `pydantic_output()` helper，并把生成的 `response_format` 传给 `generate()`。

## ResponseFormat 默认行为

`pydantic_output(Contact)` 会生成普通 `ResponseFormat`，字段默认值如下：

- `json_schema`：来自 Pydantic v2 `TypeAdapter(Contact).json_schema(mode="validation")`。默认 strict 模式下会做一次兼容 structured output 的 schema 调整。
- `json_schema_name`：默认使用 Pydantic type 的 `__name__`，例如 `Contact`；若不是具名类型则使用 `response`。显式传入 `name="contact"` 时优先使用该值，并会清理为只包含字母、数字、下划线和连字符的安全名称。
- `json_schema_description`：默认来自 Pydantic type 的 docstring；没有 docstring 时为 `None`。显式传入 `description="..."` 时优先使用该值。
- `json_schema_strict`：默认是 `True`。显式传入 `strict=False` 时为 `False`，并保留 Pydantic 原始 JSON Schema。

例如：

```python
class Contact(BaseModel):
    """Extracted contact information."""

    name: str
    email: str


contact_output = pydantic_output(Contact)
response_format = contact_output.response_format

assert response_format.json_schema_name == "Contact"
assert response_format.json_schema_description == "Extracted contact information."
assert response_format.json_schema_strict is True
```

如果要控制 provider 看到的 schema name 或 description：

```python
contact_output = pydantic_output(
    Contact,
    name="contact",
    description="A contact extracted from the input text.",
)
```

## Strict schema

默认使用 strict structured output：

```python
contact_output = pydantic_output(Contact, strict=True)
```

这会生成 `ResponseFormat(json_schema_strict=True)`，并把 Pydantic JSON Schema 调整为 provider 更容易接受的 strict 形态，例如 object 禁止额外字段、properties 全部 required。

如果字段语义上可以为空，推荐在 Pydantic model 中显式写成 nullable 类型：

```python
class Contact(BaseModel):
    name: str
    email: str | None
```

不要依赖“字段可省略”来表达可选输出；不同 provider 对 strict schema 的 required/default 支持可能不同。

## 错误处理

解析错误类型是 `StructuredOutputParseError`：

```python
from whero.vatbrain.structured import StructuredOutputParseError

try:
    parsed = contact_output.parse_response(response)
except StructuredOutputParseError as exc:
    print(exc.output_text)
    print(exc.cause)
```

常见失败原因：

- provider 返回了 refusal 或普通文本，而不是 JSON。
- 输出被截断。
- JSON 不满足 Pydantic model 校验。
- response 中没有 assistant text。

## 流式调用

当前不做 partial JSON 流式解析。需要流式展示时，可以照常消费 stream event，并在 accumulator 得到最终 response 后解析：

```python
from whero.vatbrain import GenerationStreamAccumulator

accumulator = GenerationStreamAccumulator(provider="openai")

for event in client.stream_generate(
    model="gpt-5.1",
    items=[MessageItem.user("Extract a contact.")],
    response_format=contact_output.response_format,
):
    accumulator.add(event)

response = accumulator.to_response()
parsed = contact_output.parse_response(response)
```

## 与 OpenAI SDK 的关系

OpenAI Python SDK 支持把 Pydantic model 传给 `client.responses.parse(..., text_format=Model)` 并读取 `response.output_parsed`。`vatbrain` 参考这种体验，但实现上仍调用 `client.generate()` 并使用 `ResponseFormat`，不会绕过 vatbrain adapter。

这样做可以保留 provider-neutral mapping、provider-native replay、remote context fallback 和统一错误模型。

## 当前限制

- 第一版仅支持 Pydantic v2。
- 第一版以非流式最终 response 解析为主。
- schema 是否被具体 provider 接受，仍以 provider 实际能力为准。

## 相关文档

- [user/python/api-reference.CN.md](user/python/api-reference.CN.md)
- [impls/python/pydantic-structured-output.CN.md](impls/python/pydantic-structured-output.CN.md)
- [user/python/quickstart.CN.md](user/python/quickstart.CN.md)
