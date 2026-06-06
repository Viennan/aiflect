# Python 快速开始

状态：v0.6
日期：2026-05-05
最近更新：2026-06-06

## 读者路径

本文用由简入繁的方式介绍 Python 版 `vatbrain` 的常用编程模型。完整 API 字段、枚举和当前 OpenAI / Volcengine / Anthropic adapter 支持范围见 [api-reference.CN.md](api-reference.CN.md)。Volcengine provider 细节见 [volcengine-quickstart.CN.md](volcengine-quickstart.CN.md)。Anthropic provider 细节见 [anthropic-quickstart.CN.md](anthropic-quickstart.CN.md)。Pydantic structured output 的细节见 [user/python/pydantic-structured-output.CN.md](pydantic-structured-output.CN.md)。

`vatbrain` 是 provider-neutral 的推理调用抽象层，不是 agent runtime。它不会自动选择 provider、自动选择 model、自动 fallback、自动执行工具或自动维护远端会话。用户代码始终掌控 provider、model、上下文、工具执行和下一轮调用。

## 安装与环境

仓库开发环境：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e "python[test]"
cd python
../.venv/bin/python -m pytest
```

OpenAI adapter 初始化时必须显式传入 `api_key`，或通过 `ClientConfig(api_key=...)` 提供。Volcengine 与 Anthropic adapter 使用 optional extra，初始化时同样必须显式传入 LLM API key，即 `api_key` / `ClientConfig.api_key`。

```bash
.venv/bin/python -m pip install -e "python[volcengine,test]"
.venv/bin/python -m pip install -e "python[anthropic,test]"
```

初始化 client：

```python
from whero.vatbrain.providers.openai import OpenAIClient
from whero.vatbrain.providers.volcengine import VolcengineClient
from whero.vatbrain.providers.anthropic import AnthropicClient

openai_client = OpenAIClient(api_key="...")
volcengine_client = VolcengineClient(api_key="...")
anthropic_client = AnthropicClient(api_key="...")
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

client = OpenAIClient(api_key="...")

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

`RemoteContextHint` 用于表达 provider-side cache 和新增边界 hint。它是优化提示，不是 vatbrain 的会话状态模型。

```python
from whero.vatbrain import MessageItem, RemoteContextHint

first_items = [MessageItem.user("Summarize the contract.")]

first_response = client.generate(
    model="gpt-5.1",
    items=first_items,
    remote_context=RemoteContextHint(enable_cache=True),
)

history_items = [*first_items, *first_response.output_items]
items = [*history_items, MessageItem.user("Now extract the termination clause.")]

response = client.generate(
    model="gpt-5.1",
    items=items,
    remote_context=RemoteContextHint(
        enable_cache=True,
        new_items_start_index=len(history_items),
    ),
)
```

要点：

- 用户侧仍传入完整 `items`。
- `new_items_start_index` 表示完整 `items` 中从哪里开始是本轮新增 item。
- OpenAI/Volcengine adapter 会从边界前一个 item 的 provider snapshot metadata 中读取 response id；找到时只向 provider 发送追加 suffix，找不到时发送完整 `items`。
- 如果通过路由商、网关或 OpenAI-compatible 服务间接调用 OpenAI Responses API，应先验证其支持 `previous_response_id` / stored response 链接能力，再使用 `new_items_start_index`；未验证前可以只启用 `enable_cache=True` 或不传 `remote_context`，保持完整 `items` 请求。
- Anthropic adapter 忽略 `new_items_start_index`；`RemoteContextHint.enable_cache=True` 会开启 automatic prompt caching，且仍发送完整上下文。
- response id 由 adapter 写入 provider snapshot metadata，用户不需要保存或传回。

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

当 response-style provider 返回明确的 previous response/context invalid 或 expired 错误时，OpenAI/Volcengine client 会自动移除失效 response id，并用完整 `items` refresh 一次。该行为只针对明确的 remote context 失效错误，不是通用网络重试。

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

## 图片与视频生成

图片生成是独立入口，不并入 `generate()`。OpenAI adapter 使用直接 Images API；Volcengine adapter 使用 Ark SDK 原生 Images API。

```python
response = client.generate_image(
    model="gpt-image-1",
    prompt="A clean product photo on a walnut desk.",
    output_format="png",
    response_format="b64_json",
)

for artifact in response.artifacts:
    print(artifact.url or artifact.data)
```

参考图生成仍使用同一个 `generate_image()` 入口。OpenAI adapter 会根据 `input_items` 中是否存在参考图自动选择 `images.generate` 或 `images.edit`；Volcengine adapter 统一映射到 Ark `images.generate`。

```python
from whero.vatbrain import ImagePart, MessageItem

response = client.generate_image(
    model="gpt-image-1",
    prompt="Restyle this image as a studio product photo.",
    input_items=[
        MessageItem.user([
            ImagePart(data="data:image/png;base64,..."),
        ])
    ],
)
```

`ImageGenerationRequest` 不包含 `tools`。Provider 原生媒体生成开关通过 `provider_options` 传递；v0.5 不使用 OpenAI Responses API hosted image generation tool，也不暴露 provider-hosted tools 的稳定 helper。OpenAI edit 路径不会隐式下载 `ImagePart(url=...)`，需要参考图时应传入显式图片内容。

图片生成不提供 normalized `size` 参数。不同 provider 和模型的分辨率枚举差异较大，默认让模型从 prompt 中感知目标分辨率、长宽比和构图规格；确实需要 provider-native 控制时，用 `provider_options` 显式传递。

`background` 是 provider capability：OpenAI 支持 `auto`、`transparent`、`opaque`，Volcengine 当前不支持，adapter 会忽略。可通过 `client.get_adapter_capability().media_generation.image_background_control` 检查。

图片与视频生成请求都提供 `watermark` 参数，默认 `True`，用于要求 provider 添加 AI 水印；provider 或模型没有可控水印能力时该参数会被忽略。

图片流式生成：

```python
for event in client.stream_generate_image(
    model="gpt-image-1",
    prompt="A cinematic product photo.",
    provider_options={"partial_images": 2},
):
    if event.artifact:
        print(event.type, event.artifact.url or event.artifact.data)
```

Volcengine adapter 额外支持 Ark Content Generation 视频任务：

```python
from whero.vatbrain import ImagePart, MessageItem, VideoPart

task = volcengine_client.create_video_generation_task(
    model="doubao-seedance-2-0-260128",
    prompt="A short cinematic clip of a product turntable.",
    input_items=[
        MessageItem.user([
            ImagePart(url="https://example.test/product.png"),
            VideoPart(url="https://example.test/motion-reference.mp4", fps=2.0),
        ])
    ],
    duration_seconds=8,
    ratio="16:9",
    watermark=False,
    provider_options={"return_last_frame": True},
)

task = volcengine_client.wait_for_video_generation_task(task.id)
print(task.status, task.artifacts)
```

`input_items` 可携带参考图片、参考视频、参考音频或带 media type 的文件引用，也可额外放入 `TextPart` 补充局部说明。Volcengine adapter 会把这些 part 映射为 Ark Content Generation task 的 reference content；`metadata["role"]` 可用于传递 `first_frame`、`last_frame`、`reference_image` 等 provider-native role。视频任务的 `provider_options` 可传 Ark 原生参数，例如 `return_last_frame`、`seed`、`frames`、`callback_url`、`service_tier`、`execution_expires_after`、`draft`、`priority`、`safety_identifier`。

异步入口分别是 `agenerate_image()`、`astream_generate_image()`、`acreate_video_generation_task()`、`aget_video_generation_task()` 和 `await_video_generation_task()`。

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

当前 OpenAI adapter 只支持 text embedding。Volcengine adapter 支持单样本多模态 embedding、instructions、dense vector；稀疏向量只支持纯文本输入：

```python
from whero.vatbrain import EmbeddingInput, ImagePart

sample = EmbeddingInput(
    [ImagePart(url="https://example.test/image.png")],
    modality="image",
)
```

需要 Volcengine sparse embedding 时，使用纯文本样本并设置 `sparse_embedding=True`。

## Core Models 边界

当前 core 包含音频、视频、文件、reasoning、resource/file 和 media artifact/task 模型。这些模型用于稳定跨 provider 语义，不代表每个 adapter 都已全部支持。

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

- 已实现 OpenAI、Volcengine 与 Anthropic provider。
- OpenAI / Volcengine 文本 generation 都使用 Responses API，不提供 Chat Completions fallback。
- Anthropic 文本 generation 使用官方 Anthropic SDK Messages API；要求 `GenerationConfig.max_output_tokens` 或 provider-native `max_tokens`。
- Volcengine adapter 只使用 Ark SDK 原生 surface，不使用 OpenAI-compatible surface。
- OpenAI embedding 仅支持文本输入；Volcengine embedding 支持单样本多模态输入。
- Anthropic adapter 不支持 embedding、Files API 或 media generation。
- OpenAI 图片生成只覆盖直接 Images API，不覆盖通过 Responses API hosted image generation tool 的间接路径。
- Volcengine 图片生成使用 Ark Images API；视频生成使用 Ark Content Generation task。
- audio/video/file/reasoning/resource/media 模型不代表每个 adapter 都已全部映射。
- Streaming event 已覆盖 OpenAI / Volcengine Responses API 与 Anthropic Messages API 的主要 lifecycle、text、tool call、usage、reasoning 和错误事件；未知事件会 raw passthrough。
- Capability 不维护内部权威模型能力表。
- 不提供 routing、fallback、自动模型选择、自动工具执行或 agent loop。
- 不暴露 provider-hosted tool、remote tool、MCP tool、provider conversation 持久化上下文的通用抽象。

## 参考

- [api-reference.CN.md](api-reference.CN.md)
- [volcengine-quickstart.CN.md](volcengine-quickstart.CN.md)
- [anthropic-quickstart.CN.md](anthropic-quickstart.CN.md)
- [user/python/pydantic-structured-output.CN.md](pydantic-structured-output.CN.md)
- [high-level-design.CN.md](../../design/high-level-design.CN.md)
- [impls/python/STATUS.md](../../impls/python/STATUS.md)
