# Python 快速开始

状态：v0.4
日期：2026-05-05
最近更新：2026-05-28

## 读者路径

本文用由简入繁的方式介绍 Python 版 `vatbrain` 的常用编程模型。完整 API 字段、枚举和当前 OpenAI / Volcengine adapter 支持范围见 [user/python/api-reference.CN.md](user/python/api-reference.CN.md)。Volcengine provider 细节见 [user/python/volcengine-quickstart.CN.md](user/python/volcengine-quickstart.CN.md)。Pydantic structured output 的细节见 [user/python/pydantic-structured-output.CN.md](user/python/pydantic-structured-output.CN.md)。

`vatbrain` 是 provider-neutral 的推理调用抽象层，不是 agent runtime。它不会自动选择 provider、自动选择 model、自动 fallback、自动执行工具或自动维护远端会话。用户代码始终掌控 provider、model、上下文、工具执行和下一轮调用。

## 安装与环境

仓库开发环境：

```bash
cd python
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pytest
```

OpenAI adapter 使用 `ENV_VATBRAIN_OPENAI_API_KEY`：

```bash
export ENV_VATBRAIN_OPENAI_API_KEY="..."
```

Volcengine adapter 使用 optional extra 与 `ENV_VATBRAIN_VOLCENGINE_API_KEY`：

```bash
.venv/bin/python -m pip install -e ".[volcengine,test]"
export ENV_VATBRAIN_VOLCENGINE_API_KEY="..."
```

初始化 client：

```python
from whero.vatbrain.providers.openai import OpenAIClient
from whero.vatbrain.providers.volcengine import VolcengineClient

openai_client = OpenAIClient()
volcengine_client = VolcengineClient()
```

也可以显式传入 provider client 参数：

```python
client = OpenAIClient(
    api_key="...",
    base_url="...",
    timeout=30.0,
    max_retries=2,
)
```

后文示例默认使用变量名 `client`；它可以是具体 provider client。不同 provider/model 对字段支持不同，应以 capability 和 provider-specific 文档为准。

## 最小生成

```python
from whero.vatbrain import MessageItem
from whero.vatbrain.providers.openai import OpenAIClient

client = OpenAIClient()

response = client.generate(
    model="gpt-5.1",
    items=[
        MessageItem.system("You are a concise assistant."),
        MessageItem.user("Hello"),
    ],
)

for item in response.output_items:
    print(item)
```

`items` 是完整语义上下文。每次 generation 调用都应传入本轮推理所需的全部上下文，而不是依赖 provider 侧隐式 conversation。

异步调用：

```python
response = await client.agenerate(
    model="gpt-5.1",
    items=[MessageItem.user("Hello")],
)
```

## 常用生成配置

```python
from whero.vatbrain import GenerationConfig, MessageItem, ReasoningConfig, ToolCallConfig

response = client.generate(
    model="gpt-5.1",
    items=[MessageItem.user("Explain vatbrain in one paragraph.")],
    generation_config=GenerationConfig(
        temperature=0.2,
        max_output_tokens=300,
    ),
    reasoning=ReasoningConfig(
        effort="low",
    ),
    tool_call_config=ToolCallConfig(
        parallel_tool_calls=False,
    ),
)
```

`GenerationConfig`、`ReasoningConfig`、`ToolCallConfig` 表达通用 generation 语义。不同 provider/model 可能只支持其中一部分字段；支持情况可通过 capability 查询。

少量尚未归一化的厂商参数可放入 `provider_options`：

```python
response = client.generate(
    model="gpt-5.1",
    items=[MessageItem.user("Hello")],
    provider_options={"metadata": {"trace_id": "demo"}},
)
```

## Remote Context 与 Replay

`RemoteContextHint` 用于表达 provider-side previous response 和 store hint。它是优化提示，不是 vatbrain 的会话状态模型。

```python
from whero.vatbrain import MessageItem, RemoteContextHint

first_items = [MessageItem.user("Summarize the contract.")]

first_response = client.generate(
    model="gpt-5.1",
    items=first_items,
    remote_context=RemoteContextHint(store=True),
)

history_items = [*first_items, *first_response.output_items]
items = [*history_items, MessageItem.user("Now extract the termination clause.")]

response = client.generate(
    model="gpt-5.1",
    items=items,
    remote_context=RemoteContextHint(
        previous_response_id=first_response.id,
        covered_item_count=len(history_items),
    ),
)
```

要点：

- 用户侧仍传入完整 `items`。
- `covered_item_count` 表示 `previous_response_id` 已覆盖完整 `items` 中的历史前缀。
- OpenAI adapter 在边界明确时只向 provider 发送追加 suffix。
- `store=True` 只影响本轮 response 未来是否便于被引用；不能补救历史 response 未存储的问题。

Provider 返回的 output item 会在 `provider_snapshots` 字段保留原始 payload。OpenAI adapter 默认优先使用 snapshot 做同 provider 高保真重放，以保留 OpenAI `phase` 等原生字段。手工构造 assistant 历史消息时可使用通用 `AssistantMessagePhase`：

```python
from whero.vatbrain import AssistantMessagePhase, MessageItem

history = [
    MessageItem.assistant(
        "Let me inspect that.",
        assistant_phase=AssistantMessagePhase.COMMENTARY,
    ),
    MessageItem.user("Continue."),
]
```

如需控制 replay 策略：

```python
from whero.vatbrain import ReplayPolicy

response = client.generate(
    model="gpt-5.1",
    items=history,
    replay_policy=ReplayPolicy(mode="normalized_only"),
)
```

当 `previous_response_id` 失效时，默认抛错。只有显式启用 fallback 时，OpenAI client 才会移除失效 remote context，用完整 `items` 自动重试一次：

```python
response = client.generate(
    model="gpt-5.1",
    items=history,
    remote_context=RemoteContextHint(
        previous_response_id="resp_previous",
        covered_item_count=1,
    ),
    replay_policy=ReplayPolicy(
        on_remote_context_invalid="replay_without_remote_context",
    ),
)
```

跨 provider replay 暂不支持。

## 流式生成

```python
from whero.vatbrain import MessageItem

for event in client.stream_generate(
    model="gpt-5.1",
    items=[MessageItem.user("Write a short haiku.")],
):
    if event.type == "text.delta":
        print(event.delta, end="")
```

异步流式调用：

```python
async for event in client.astream_generate(
    model="gpt-5.1",
    items=[MessageItem.user("Write a short haiku.")],
):
    ...
```

事件会保留 `raw_event`，用于访问尚未标准化的 provider 原始事件。OpenAI Responses API 的最终 usage 通常随完整 response 返回；`StreamOptions(include_usage=True)` 不会被映射为 OpenAI `stream_options.include_usage`。

从流式事件重建 `GenerationResponse`：

```python
from whero.vatbrain import GenerationStreamAccumulator, MessageItem

accumulator = GenerationStreamAccumulator(provider="openai")

for event in client.stream_generate(
    model="gpt-5.1",
    items=[MessageItem.user("Write a short haiku.")],
):
    accumulator.add(event)
    if event.type == "text.delta":
        print(event.delta, end="")

response = accumulator.to_response()
```

## Structured Output

`vatbrain` 只支持 JSON Schema structured output，不兼容 JSON mode / `json_object`。

```python
from whero.vatbrain import MessageItem, ResponseFormat

response = client.generate(
    model="gpt-5.1",
    items=[MessageItem.user("Extract a contact.")],
    response_format=ResponseFormat(
        json_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["name", "email"],
            "additionalProperties": False,
        },
        json_schema_name="contact",
        json_schema_strict=True,
    ),
)
```

Python 侧可用 Pydantic v2 生成 schema 并解析最终响应：

```python
from pydantic import BaseModel

from whero.vatbrain import MessageItem
from whero.vatbrain.structured import pydantic_output


class Contact(BaseModel):
    name: str
    email: str


contact_output = pydantic_output(Contact, name="contact")

response = client.generate(
    model="gpt-5.1",
    items=[MessageItem.user("Extract a contact.")],
    response_format=contact_output.response_format,
)

contact = contact_output.parse_response(response).output_parsed
```

OpenAI client 也提供薄封装：

```python
parsed = client.generate_parsed(
    model="gpt-5.1",
    items=[MessageItem.user("Extract a contact.")],
    output_type=Contact,
)

contact = parsed.output_parsed
```

`generate_parsed()` 使用默认 Pydantic helper 行为。需要自定义 schema name、description 或 strict 时，使用 `pydantic_output()` + `generate()`。默认 schema name 来自类型名，description 来自类型 docstring，strict 为 `True`。

## 工具调用

`vatbrain` 只定义工具协议，不执行工具。用户代码需要：

1. 声明工具。
2. 读取 `FunctionCallItem`。
3. 执行本地工具函数。
4. 将 `FunctionResultItem` 加入完整上下文。
5. 发起下一轮 generation。

### Function Tool

默认 `ToolSpec` 是 function tool。模型输出 JSON string `arguments`，用户代码负责解析：

```python
import json

from whero.vatbrain import FunctionCallItem, FunctionResultItem, MessageItem, ToolSpec


def get_weather(*, city: str) -> dict[str, object]:
    return {
        "city": city,
        "temperature_c": 22,
        "condition": "cloudy",
    }


tools = [
    ToolSpec(
        name="get_weather",
        description="Get weather by city.",
        parameters_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        strict=True,
    )
]

items = [MessageItem.user("What is the weather in Shanghai?")]

response = client.generate(
    model="gpt-5.1",
    items=items,
    tools=tools,
)

for output_item in response.output_items:
    if isinstance(output_item, FunctionCallItem):
        arguments = json.loads(output_item.arguments)
        if output_item.name != "get_weather":
            raise ValueError(f"Unknown tool call: {output_item.name}")

        result = get_weather(city=arguments["city"])
        items.append(output_item)
        items.append(
            FunctionResultItem(
                call_id=output_item.call_id,
                output=json.dumps(result, ensure_ascii=False),
            )
        )

followup = client.generate(
    model="gpt-5.1",
    items=items,
    tools=tools,
)
```

### Custom Tool

如果工具需要直接接收自然语言、代码或其他任意字符串输入，可以使用 custom tool。OpenAI adapter 会把 `ToolSpec(type="custom")` 映射为 OpenAI custom tool；custom tool 不使用 `parameters_schema`，模型输出保存在 `FunctionCallItem.input`：

```python
from whero.vatbrain import FunctionCallItem, FunctionResultItem, MessageItem, ToolSpec


def run_code(source: str) -> str:
    return "hello\n"


tools = [
    ToolSpec(
        name="run_code",
        description="Run Python code.",
        type="custom",
    )
]

items = [MessageItem.user("Use run_code to print hello.")]

response = client.generate(
    model="gpt-5.1",
    items=items,
    tools=tools,
)

for output_item in response.output_items:
    if isinstance(output_item, FunctionCallItem) and output_item.type == "custom":
        result = run_code(output_item.input or "")
        items.append(output_item)
        items.append(
            FunctionResultItem(
                call_id=output_item.call_id,
                output=result,
                tool_type=output_item.type,
            )
        )

followup = client.generate(
    model="gpt-5.1",
    items=items,
    tools=tools,
)
```

空 `parameters_schema` 不等于 custom tool。想让模型直接输出 raw string input 时，应显式设置 `type="custom"`。

## Embedding

Embedding 是独立入口，不并入 generation request。

```python
embedding = client.embed(
    model="text-embedding-3-small",
    inputs=[
        "first document",
        "second document",
    ],
)

for vector in embedding.vectors:
    print(vector.index, vector.embedding)
```

异步：

```python
embedding = await client.aembed(
    model="text-embedding-3-small",
    inputs=["first document"],
)
```

当前 OpenAI adapter 只支持 text embedding。v0.3 core 已能表达多模态 embedding、instructions 和 sparse vectors，主要服务后续 provider adapter：

```python
from whero.vatbrain import EmbeddingInput, ImagePart

sample = EmbeddingInput(
    [ImagePart(url="https://example.test/image.png")],
    modality="image",
)
```

## Core Models 边界

v0.3 新增音频、视频、文件、reasoning、resource/file 和 media artifact/task 的 core 模型。这些模型用于稳定跨 provider 语义，不代表当前 OpenAI adapter 已全部支持。

```python
from whero.vatbrain import FilePart, MessageItem, VideoPart

items = [
    MessageItem.user(
        [
            VideoPart(url="https://example.test/demo.mp4", mime_type="video/mp4"),
            FilePart(file_id="file_provider_123", provider="example"),
        ]
    )
]
```

`FilePart.local_path`、`AudioPart.local_path` 和 `VideoPart.local_path` 只是路径 metadata，不会自动读取文件或上传文件。

工具抽象当前只覆盖用户代码执行的 function/custom tool。provider-hosted tool、remote tool 和 MCP tool 暂不作为通用 core 抽象暴露。

## Capability

Adapter capability 描述当前 adapter 自身实现了什么：

```python
capability = client.get_adapter_capability()
print(capability.supports_generation)
print(capability.generation.structured_output.value)
print(capability.tools.custom_tools.value)
```

Model capability 是对某个 model 的能力描述，但不保证权威。未知字段以 `CapabilityValue(value=None)` 表示：

```python
model_capability = client.get_model_capability("gpt-5.1")
print(model_capability.max_context_tokens.value)
```

不同 provider 对 `ReasoningConfig.effort` 的取值和含义可能不同。adapter/model capability 会在可声明时列出支持的 effort：

```python
adapter_capability = client.get_adapter_capability()
print(adapter_capability.generation.supported_reasoning_efforts.value)

model_capability = client.get_model_capability("gpt-5.1")
print(model_capability.supported_reasoning_efforts.value)
```

用户可以显式提供模型能力覆盖：

```python
client = OpenAIClient(
    model_capability_overrides={
        "gpt-5.1": {
            "supports_streaming": True,
        }
    }
)
```

## 错误处理

Provider 请求失败会抛出 `ProviderRequestError`，其中 `details` 保存 provider、operation、status code、request id、错误 code/param 与 raw body：

```python
from whero.vatbrain.core.errors import ProviderRequestError

try:
    response = client.generate(
        model="gpt-5.1",
        items=[MessageItem.user("Hello")],
    )
except ProviderRequestError as exc:
    print(exc.details.provider)
    print(exc.details.operation)
    print(exc.details.status_code)
    print(exc.details.request_id)
```

其他常见错误包括：

- `InvalidItemError`：item 或 remote context 覆盖范围不合法。
- `UnsupportedCapabilityError`：请求了 adapter 明确不支持的能力。
- `ProviderResponseMappingError`：provider 响应无法映射为 vatbrain 模型。
- `StructuredOutputParseError`：structured output 解析失败。

## 当前限制

- 已实现 OpenAI 与 Volcengine provider。
- OpenAI / Volcengine generation 都使用 Responses API，不提供 Chat Completions fallback。
- Volcengine adapter 只使用 Ark SDK 原生 surface，不使用 OpenAI-compatible surface。
- OpenAI embedding 仅支持文本输入；Volcengine embedding 支持单样本多模态输入。
- v0.3 新增的 audio/video/file/reasoning/resource/media 模型主要是 core 表达层，不代表每个 adapter 都已全部映射。
- Streaming event 已覆盖 OpenAI / Volcengine Responses API 的主要 lifecycle、text、tool call、reasoning summary 与错误事件；未知事件会 raw passthrough。
- Capability 不维护内部权威模型能力表。
- 不提供 routing、fallback、自动模型选择、自动工具执行或 agent loop。
- 不暴露 provider-hosted tool、remote tool、MCP tool、provider conversation 持久化上下文的通用抽象。

## 参考

- [user/python/api-reference.CN.md](user/python/api-reference.CN.md)
- [user/python/volcengine-quickstart.CN.md](user/python/volcengine-quickstart.CN.md)
- [user/python/pydantic-structured-output.CN.md](user/python/pydantic-structured-output.CN.md)
- [design/high-level-design.CN.md](design/high-level-design.CN.md)
- [impls/python/STATUS.md](impls/python/STATUS.md)
