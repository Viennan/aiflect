# Python OpenAI Adapter 实现方案

状态：实现计划  
日期：2026-05-05

## 背景

Python 版本是 `vatbrain` 的参考实现。第一阶段选择 OpenAI SDK 作为首个 provider adapter，用于验证 `vatbrain` 的核心抽象是否能够落地到真实厂商 API。

该实现应遵循高层设计中的边界：

- provider client 按厂商初始化，而不是按 model 初始化。
- 用户每次调用时显式指定 model。
- client 初始化支持通用 `api_key`、`base_url`、`timeout`、`max_retries`。
- OpenAI API key 必须在初始化时显式传入，或通过 `ClientConfig.api_key` 提供；adapter 内部以 `SecretString` 保存。
- 不提供自动 routing、fallback 或模型选择。
- 不内建 ReAct loop，不自动执行工具。
- capability 不维护内部权威模型能力表，未知信息以 unknown 表达。
- reasoning 与 parallel tool calls 属于通用 generation 配置，不作为 OpenAI 专有选项。

## 实现目标

第一版 OpenAI adapter 应支持以下能力：

- Python 包脚手架与测试环境。
- `whero.vatbrain` 核心模型。
- OpenAI provider client。
- 非流式 generation。
- 流式 generation。
- function tool 声明、tool call 输出、tool result 回填协议。
- text embedding。
- usage 标准化。
- adapter capability 与 model capability 基础表达。
- 单元测试，不依赖真实 OpenAI API。

第一版不支持：

- 多 provider。
- 自动工具执行。
- 自动多轮 agent loop。
- 内部模型能力表。
- 多模态 embedding。
- OpenAI hosted tools 的完整高级封装。

## 目录结构

建议初始结构如下：

```text
python/
  pyproject.toml
  tests/
    unit/
      test_items.py
      test_openai_client.py
      test_openai_generation_mapper.py
      test_openai_stream_mapper.py
      test_openai_embeddings.py
      test_capabilities.py
  whero/
    __init__.py
    vatbrain/
      __init__.py
      core/
        __init__.py
        capabilities.py
        embeddings.py
        errors.py
        generation.py
        items.py
        tools.py
        usage.py
      providers/
        __init__.py
        openai/
          __init__.py
          capabilities.py
          client.py
          mapper.py
          stream.py
```

## 包与依赖

`python/pyproject.toml` 应声明：

- Python 版本：`>=3.12`。
- runtime dependency：`openai`。
- test dependency：`pytest`。
- 可选 lint/type dependency 可后续引入。

所有开发与测试命令应使用 `python/.venv`。

## Core 模型

### Item

第一版只实现 OpenAI adapter 所需的最小稳定子集：

- `MessageItem`：表达 system/developer/user/assistant/tool 等消息型上下文。
- `TextPart`：文本内容。
- `ImagePart`：generation 输入图片，支持 URL 或 base64/data URL。
- `FunctionCallItem`：模型请求调用工具的结构化输出。
- `FunctionResultItem`：用户执行工具后回填的结果。

`Item` 需要保留 `kind`、`role`、`purpose` 等语义维度，但第一版可以对 `purpose` 使用较小枚举或可选字段，以避免过早复杂化。

### Generation

`GenerationRequest` 应包含：

```text
model
items
tools
generation_config
response_format
reasoning
tool_call_config
stream_options
provider_options
```

其中：

- `generation_config` 承载 temperature、top_p、max_output_tokens 等通用生成参数。
- `reasoning` 承载 reasoning effort、budget tokens、summary、include trace 等通用推理配置。
- `tool_call_config` 承载 parallel tool calls、tool choice 等通用工具调用行为配置。
- `provider_options` 只承载 OpenAI 专有或暂时未归一化的参数。

`GenerationResponse` 应包含：

```text
id
provider
model
output_items
stop_reason
usage
metadata
raw
```

### Tools

`ToolSpec` 应表达 function tool 的通用结构：

```text
name
description
parameters_schema
strict
```

工具调用输出和工具结果回填通过 `FunctionCallItem` 与 `FunctionResultItem` 表达。`vatbrain` 不执行工具。

### Embeddings

`EmbeddingRequest` 应与 generation 平行存在：

```text
model
inputs
dimensions
encoding_format
provider_options
```

第一版 OpenAI adapter 仅支持 text embedding。`EmbeddingInput` 可以复用 embedding-compatible `Item`，但 OpenAI 映射阶段应只接受可转换为文本的输入。对于图片、音频、视频等输入，应在 adapter capability 或校验中表达不支持或 unknown。

### Usage

`Usage` 应覆盖：

```text
input_tokens
output_tokens
total_tokens
cached_tokens
reasoning_tokens
raw
```

不存在或无法映射的字段为 `None`。

### Capability

capability 拆分为：

- `AdapterCapability`：由 OpenAI adapter 可靠声明，例如支持 generation、stream generation、text embedding、function tool 映射、usage 解析。
- `ModelCapability`：具体 model 的能力提示。默认不声称知道上下文窗口、embedding 维度等易变信息，除非用户显式提供 overrides 或后续接入可靠来源。

capability 字段应携带 source 与 reliability，且允许 unknown。

## OpenAI Adapter 设计

### Client 生命周期

`OpenAIClient` 是 provider 级 client。它负责持有 OpenAI sync/async SDK client，复用认证、base URL、timeout、连接池等资源。

通用初始化参数：

```python
OpenAIClient(
    api_key="...",
    base_url="...",
    timeout=30.0,
    max_retries=2,
)
```

若未显式传入 `api_key` / `ClientConfig.api_key`，且未注入已有 SDK client，OpenAI adapter 会在初始化阶段报错；不再读取环境变量作为隐式凭据来源。

概念 API：

```python
client = OpenAIClient(api_key="...")

response = client.generate(model="...", items=[...])
stream = client.stream_generate(model="...", items=[...])
embedding = client.embed(model="...", inputs=[...])
```

异步 API：

```python
response = await client.agenerate(model="...", items=[...])
async for event in client.astream_generate(model="...", items=[...]):
    ...
embedding = await client.aembed(model="...", inputs=[...])
```

### Generation 映射

OpenAI generation 使用 Responses API。

映射原则：

- `GenerationRequest.model` -> OpenAI `model`。
- `MessageItem` / `TextPart` / `ImagePart` -> OpenAI `input` items。
- `FunctionResultItem` -> OpenAI `function_call_output` input item。
- `ToolSpec` -> OpenAI `tools`。
- `GenerationConfig` -> OpenAI 通用生成参数。
- `ReasoningConfig` -> OpenAI `reasoning` 参数。
- `ToolCallConfig.parallel_tool_calls` -> OpenAI `parallel_tool_calls`。
- `ToolCallConfig.tool_choice` -> OpenAI `tool_choice`。
- `provider_options` -> OpenAI request 的补充参数。

OpenAI response 输出映射：

- message output -> `MessageItem(role=assistant, ...)`。
- function call output -> `FunctionCallItem`。
- usage -> `Usage`。
- 原始 response 保留到 `raw`。

adapter 不执行 function call。

### Streaming 映射

OpenAI stream event 应统一转换为 `GenerationStreamEvent`。

第一版事件映射重点覆盖：

- response 生命周期事件。
- output item 创建、增量、完成。
- 文本 delta。
- function call arguments delta。
- usage 更新。
- response completed/failed。

所有事件应保留 `raw_event`，以便 OpenAI 新增事件类型时不丢失信息。对于暂未归一化的事件，可以生成 generic event 或仅透传 raw。

### Embedding 映射

OpenAI embedding 使用 embeddings endpoint。

映射原则：

- `EmbeddingRequest.model` -> OpenAI `model`。
- text `EmbeddingInput` -> OpenAI `input`。
- `dimensions` -> OpenAI `dimensions`。
- `encoding_format` -> OpenAI `encoding_format`。
- response data -> `EmbeddingVector`。
- usage -> `Usage`。
- 原始 response 保留到 `raw`。

第一版只支持 text embedding。多模态 embedding 留给后续 provider 或 OpenAI 未来能力。

## Error 处理

应定义 `VatbrainError` 基类和若干领域错误：

- `UnsupportedCapabilityError`
- `ProviderRequestError`
- `ProviderResponseMappingError`
- `InvalidItemError`

OpenAI SDK 抛出的异常应包装为 `ProviderRequestError`，并保留原始异常引用。

## 测试策略

测试不调用真实 OpenAI API。

重点测试：

- core item 构造和基本校验。
- generation request -> OpenAI request 参数映射。
- OpenAI response -> `GenerationResponse` 映射。
- OpenAI stream event -> `GenerationStreamEvent` 映射。
- function call item 与 function result item 映射。
- embedding request/response 映射。
- capability unknown、source、reliability 的表达。

可使用 fake OpenAI SDK client 捕获调用参数，并用轻量对象模拟 OpenAI response。

## 实现步骤

1. 创建 Python 包脚手架、`pyproject.toml`、基础测试目录。
2. 实现 core enums、dataclass/model、错误类型。
3. 实现 OpenAI mapper 的纯函数层。
4. 实现 `OpenAIClient` sync generation。
5. 实现 async generation。
6. 实现 sync/async streaming。
7. 实现 text embedding。
8. 实现 adapter/model capability。
9. 补充单元测试并更新 [impls/python/STATUS.md](impls/python/STATUS.md)。

## 参考资料

- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)
- [OpenAI streaming responses](https://platform.openai.com/docs/api-reference/streaming)
- [OpenAI function calling](https://platform.openai.com/docs/guides/function-calling)
- [OpenAI embeddings API](https://platform.openai.com/docs/api-reference/embeddings)
