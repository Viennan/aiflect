# Python v0.4 Volcengine Adapter MVP 实现方案

状态：已实现  
日期：2026-05-14  
最近更新：2026-05-28

## 定位

v0.4 已实现 `vatbrain` Python 参考实现的第二个 provider adapter：Volcengine / 火山方舟。该阶段没有继续扩张 core 抽象，而是用火山方舟的 Responses API、Files API 与多模态 embedding 验证 v0.3 core 是否能够承载跨厂商差异。

本方案是 [impls/python/evolution-plan.CN.md](impls/python/evolution-plan.CN.md) 中 v0.4 的详细实施设计。高层语义以 [design/high-level-design.CN.md](design/high-level-design.CN.md)、[design/provider-capability-integration.CN.md](design/provider-capability-integration.CN.md) 与 [design/provider-native-replay.CN.md](design/provider-native-replay.CN.md) 为准；当前 core/API family 基线见 [impls/python/v0.3-core-api-family-expansion.CN.md](impls/python/v0.3-core-api-family-expansion.CN.md)。

## 设计输入

### 当前项目基线

截至 v0.3：

- `core.items` 已支持 text/image/audio/video/file part、function call/result、reasoning item 与 provider-native snapshot。
- `core.generation` 已支持 `RemoteContextHint`、`ReplayPolicy`、JSON Schema structured output、reasoning config、tool call config 与 stream accumulator。
- `core.resources` 已定义文件资源生命周期模型。
- `core.embeddings` 已定义多模态 input、instructions、dense/sparse vector。
- `core.capabilities` 已按 API family 拆分 adapter/model capability。
- OpenAI adapter 已完成 Responses generation/streaming、function/custom tools、structured output、text embedding、provider-native replay 与 remote context fallback。

v0.4 应优先复用这些 core 结构，避免为 Volcengine 临时新增平行模型。

### Volcengine 资料事实

本阶段重点参考：

- [3rds/volengine/response_api_text_gen.md](3rds/volengine/response_api_text_gen.md)：Responses API 文本生成、Ark SDK 调用、`previous_response_id`、`store`、`caching`、streaming event、`instructions` 与上下文管理规则；资料中的 OpenAI-compatible 示例仅作为对照，不作为 v0.4 实现依据。
- [3rds/volengine/response_api_multimodal_understanding.md](3rds/volengine/response_api_multimodal_understanding.md)：Responses API 支持图片、视频、文档输入；文件可通过 Files API 上传后用 `file_id` 引用，也可通过 URL/base64 传入；视频上传支持预处理 `fps`。
- [3rds/volengine/response_api_reasoning.md](3rds/volengine/response_api_reasoning.md)：reasoning 由 `thinking.type` 与 `reasoning.effort` 控制；流式事件包含 reasoning summary；usage 中包含 `output_tokens_details.reasoning_tokens`。
- [3rds/volengine/response_api_tool_calling.md](3rds/volengine/response_api_tool_calling.md)：Responses API function tool 使用 `tools` 声明，模型输出 `function_call`，用户通过 `function_call_output` 和 `call_id` 回填结果；Web Search、Image Process、Knowledge Search、Remote MCP 属于 provider-hosted/remote tools。
- [3rds/volengine/file_api.md](3rds/volengine/file_api.md)：Files API 独立表达上传、检索、列表、删除、状态与过期时间。
- [3rds/volengine/embeding.md](3rds/volengine/embeding.md)：Doubao 多模态 embedding 支持 text/image/video、`instructions`、dense vector、sparse vector 与 usage。

## 设计哲学

### Ark SDK Only

v0.4 仅使用火山方舟自身提供的 Ark SDK，即 Python 侧的 `volcenginesdkarkruntime`、`Ark` / `AsyncArk` 及其原生类型/方法。不使用火山方舟提供的 OpenAI-compatible SDK surface，也不把 OpenAI SDK 配置为火山方舟 base URL。

v0.4 也不引入 direct HTTP fallback。若 Ark SDK 当前版本无法表达某个文档字段，应先通过 Ark SDK 的原生扩展点或 `provider_options` 验证是否可传递；若仍无法表达，则把该字段标记为暂不支持或暂停实现确认，而不是绕到兼容接口。

adapter identity 始终是 `volcengine`。响应中的 `provider`、capability、error details、snapshot key、metadata 都不应伪装成 OpenAI。

### Responses-only Generation

火山方舟同时提供 Chat API 与 Responses API。v0.4 generation 只使用 Responses API；Chat API 资料只作为语义对照，不作为 fallback 或平行调用路径。

### Full-context First, Transport Delta

用户仍传入完整 `GenerationRequest.items`。当用户提供 `RemoteContextHint.previous_response_id` 且明确 `covered_item_count` 时，Volcengine adapter 可以只把未覆盖 suffix 传给 provider，并通过 `previous_response_id` 引用远端上下文。

如果 previous response 失效，adapter 只有在用户显式设置 `ReplayPolicy(on_remote_context_invalid="replay_without_remote_context")` 时，才移除失效 remote context 并用完整 `items` 重试一次。默认行为是抛错。

### API Family Separation

v0.4 同时实现 generation、resources/files、embedding 三个 API family，但它们应保持独立：

- generation 使用 `GenerationRequest` / `GenerationResponse`。
- files 使用 `FileUploadRequest` / `FileResource`。
- embedding 使用 `EmbeddingRequest` / `EmbeddingResponse`。

图片/视频生成属于 media generation，留给 v0.5。

### Explicit Resource I/O

`ImagePart`、`VideoPart`、`FilePart` 中的 `local_path` 只表达本地路径 metadata，不触发隐式上传。需要 provider 文件资源时，用户必须显式调用 `upload_file()`，再在 generation/embedding 中引用 `file_id`。

### Explicit Tool Ownership

v0.4 只把 user-executed function tool 映射为通用 `FunctionToolSpec` / `FunctionCallItem` / `FunctionResultItem`。Volcengine 的 Web Search、Image Process、Knowledge Search、Remote MCP 等 provider-hosted/remote tools 暂不进入通用 core，可通过 `provider_options` 透传原生参数，但不提供稳定 public helper。

## Provider Identity 与包结构

Provider 常量：

```text
provider id: volcengine
api family: responses
snapshot key: volcengine.responses
client: VolcengineClient
credential handling: explicit LLM `api_key` / `ClientConfig.api_key` only; stored as `SecretString` internally
default base URL: https://ark.cn-beijing.volces.com/api/v3
```

新增目录：

```text
python/whero/vatbrain/providers/volcengine/
  __init__.py
  capabilities.py
  client.py
  mapper.py
  stream.py
  files.py
  embeddings.py
```

建议测试文件：

```text
python/tests/unit/test_volcengine_client.py
python/tests/unit/test_volcengine_generation_mapper.py
python/tests/unit/test_volcengine_stream_mapper.py
python/tests/unit/test_volcengine_files.py
python/tests/unit/test_volcengine_embeddings.py
```

## 依赖与调用面选择

### Ark SDK Optional Dependency

Volcengine 依赖应放入 optional extra，避免 core 与 OpenAI adapter 被强制绑定：

```toml
[project.optional-dependencies]
volcengine = [
    "volcengine-python-sdk[ark]>=5.0.30,<6",
]
```

v0.4 不新增 OpenAI-compatible SDK 依赖，也不新增 direct HTTP 专用依赖。实现验证结果：PyPI 安装包名是 `volcengine-python-sdk[ark]`，导入模块是 `volcenginesdkarkruntime`。

### Ark SDK 调用面

固定策略：

- Responses generation/streaming：使用 Ark / AsyncArk SDK 的 `responses.create` 及其原生 request/response/event 类型。
- Files API：使用 Ark / AsyncArk SDK 的 files surface。若 `wait_for_processing` helper 不稳定或不可用，adapter 可以基于 Ark SDK 的 retrieve/list 方法自行轮询。
- Multimodal embedding：使用 Ark SDK 暴露的多模态 embedding surface。
- Provider 原生参数：优先通过 Ark SDK 原生字段或其支持的额外参数传递；不能通过 OpenAI-compatible SDK 或 direct HTTP 绕过。

如果 Ark SDK 尚未覆盖某个 v0.4 目标能力，应在实现记录中明确降级范围，并同步更新 STATUS / 用户文档。

## Client 编程模型

`VolcengineClient` 与 `OpenAIClient` 保持同构风格：

```python
from whero.vatbrain.providers.volcengine import VolcengineClient

client = VolcengineClient(api_key="...")

response = client.generate(model="...", items=[...])
stream = client.stream_generate(model="...", items=[...])
embedding = client.embed(model="...", inputs=[...])
file = client.upload_file(file=..., purpose="user_data")
```

异步方法：

```python
response = await client.agenerate(model="...", items=[...])
async for event in client.astream_generate(model="...", items=[...]):
    ...
embedding = await client.aembed(model="...", inputs=[...])
file = await client.aupload_file(file=..., purpose="user_data")
```

初始化参数与 OpenAI adapter 对齐：

```python
VolcengineClient(
    config=None,
    api_key="...",
    base_url=None,
    timeout=None,
    max_retries=None,
    client=None,
    async_client=None,
    model_capability_overrides=None,
    **provider_client_options,
)
```

解析规则：

- `api_key` 优先级：显式参数 > `ClientConfig.api_key`；不再读取环境变量作为隐式 fallback。
- `base_url` 优先级：显式参数 > `ClientConfig.base_url` > 默认 base URL。
- `timeout`、`max_retries` 与 `provider_client_options` 透传给 Ark SDK backend；LLM 凭据统一使用 `api_key` / `ClientConfig.api_key`，在 adapter 内部以 `SecretString` 保存，创建 Ark SDK client 时才解包。
- 不读取 `ARK_API_KEY` 或 `ENV_VATBRAIN_VOLCENGINE_API_KEY` 作为 public contract；需要兼容时由用户代码显式读取后传入。

## Generation 映射

### 请求参数

`GenerationRequest` 到 Volcengine Responses API：

```text
request.model -> model
request.items -> input
request.tools -> tools
GenerationConfig.temperature -> temperature
GenerationConfig.top_p -> top_p
GenerationConfig.max_output_tokens -> max_output_tokens
ResponseFormat -> text.format
ReasoningConfig.mode -> thinking.type
ReasoningConfig.effort -> reasoning.effort
ToolCallConfig.parallel_tool_calls -> parallel_tool_calls, if supported by Ark SDK surface
ToolCallConfig.tool_choice -> tool_choice, if supported by Ark SDK surface
RemoteContextHint.previous_response_id -> previous_response_id
RemoteContextHint.store -> store
RemoteContextHint.provider_options -> provider-native remote context params
GenerationRequest.provider_options -> Ark SDK params or request-body extra_body
```

停止序列不进入 `GenerationConfig`；如目标 Ark API 支持某个原生扩展字段，应由用户通过 `provider_options` 明确传递。

Ark SDK Python surface 并不是任意 `**kwargs` 请求体透传。adapter 会把 Ark SDK `responses.create` 已显式支持的字段直接作为方法参数传入；对于 Responses API 文档中存在但当前 SDK 签名未直接暴露的请求体字段（例如 `include`、`context_management`、`metadata`），会合并到 SDK `extra_body`。

`provider_options` 的推荐用途：

- `caching`：火山方舟 cache / prefix cache 配置，暂不进入通用 core。
- `instructions`：本轮补充系统提示词。注意资料说明它与 cache 存在互斥/命中限制，adapter 不做自动改写。
- `include`：如请求 `reasoning.encrypted_content`。
- `expire_at`：存储过期时间。
- `service_tier`、`metadata` 或其他 Responses API 原生字段。

### 输入 item

`MessageItem`：

- `role` 映射为 Responses message role。
- `TextPart` 映射为 `input_text`；assistant 历史输出可映射为 `output_text`。
- `ImagePart(url=...)` 映射为 `input_image` + URL 字段。
- `ImagePart(data=...)` 映射为 `input_image` + data URL；若只提供裸 base64，adapter 使用 `mime_type` 或默认图片 MIME 类型补齐 data URL。
- `VideoPart(file_id=...)` 映射为 `input_video` + `file_id`。
- `VideoPart(url=...)` / `VideoPart(data=...)` 映射为 `input_video` 的 URL/data 形式。
- `FilePart(file_id=...)` 映射为 `input_file` + `file_id`。
- `FilePart(url=...)` / `FilePart(data=...)` 映射为 `input_file` 的 URL/data 形式。
- `local_path` 不映射为 provider 上传，不触发 I/O。

`FunctionCallItem`：

- 默认用于同 provider replay 或 full-context fallback。
- 映射为 Volcengine Responses 的 `function_call` item，保留 `name`、`call_id`、`arguments`、`id`、`status`。

`FunctionResultItem`：

- 映射为 `function_call_output`。
- `call_id` 必须与模型输出的 function call 对齐。
- `output` 保持字符串，由用户负责序列化工具结果。
- `metadata["status"]` 可映射为 Ark `function_call_output.status`，用于保留 provider-native replay 状态。

`ReasoningItem`：

- 若存在 provider-native snapshot，replay 时优先使用 snapshot。
- 若缺少 snapshot，可根据 Responses API reference 中的 `type="reasoning"` / `summary=[{"type":"summary_text"}]` 结构构造 normalized reasoning input。
- 加密原文 `reasoning.encrypted_content` 仍属于 provider-native 字段，通过 `provider_options` / snapshot 保真，不提升为 core 字段。

### Remote Context 与差分传输

当 `remote_context.previous_response_id` 存在时：

- 必须提供 `covered_item_count`。
- `covered_item_count` 必须小于等于 `len(items)`。
- provider 请求的 `input` 使用 `items[covered_item_count:]`。
- 若 suffix 为空，adapter 应抛 `InvalidItemError`，避免发出无新增 input 的 Responses 请求。

Fallback 构造：

- optimized attempt：`previous_response_id` + suffix input。
- fallback attempt：移除 `previous_response_id`，用完整 `items` 重新构造 input。
- fallback 只在 `ReplayPolicy.on_remote_context_invalid == replay_without_remote_context` 且错误可判断为 remote context 失效时执行一次。

### Structured Output

`ResponseFormat` 映射为 Responses API `text.format` JSON Schema：

```text
ResponseFormat.json_schema -> schema
ResponseFormat.json_schema_name -> name, default response
ResponseFormat.json_schema_description -> description
ResponseFormat.json_schema_strict -> strict
```

不支持 JSON mode / `json_object`。如果用户在 `provider_options` 里手工传入冲突的 structured output 字段，adapter 应优先抛清晰错误，避免双来源参数互相覆盖。

### Reasoning

`ReasoningConfig` 映射规则：

- `mode` 映射为 `thinking.type`，典型取值为 `enabled`、`disabled`、`auto`。
- `effort` 映射为 `reasoning.effort`，典型取值为 `minimal`、`low`、`medium`、`high`。
- `provider_options` 可透传额外 reasoning 原生字段。
- `summary`、`budget_tokens`、`include_trace` 目前没有稳定 Volcengine 通用映射时，不应强行猜测；可通过 `provider_options` 表达。

校验边界：

- adapter capability 声明 provider 支持 reasoning config，但具体 model 支持的 mode/effort 默认 unknown。
- 不在 mapper 中硬编码所有模型白名单。
- 若用户请求 provider 明确不支持的字段，并且无法透传，抛 `UnsupportedCapabilityError`。

### Tools

`FunctionToolSpec(type="function")` 映射为 Responses API function tool：

```text
type -> "function"
name -> name
description -> description
parameters_schema -> parameters
strict -> strict, if provider surface supports it
```

`FunctionToolSpec(type="custom")`：

- v0.4 暂不承诺 Volcengine 支持 OpenAI custom tool 语义。
- 若 Volcengine Responses API 无等价能力，mapper 应抛 `UnsupportedCapabilityError`。

`ToolCallConfig`：

- `parallel_tool_calls`、`tool_choice` 仅在 Ark SDK 的 Volcengine Responses API surface 支持时映射。
- 支持性应体现在 adapter capability；未知时以 provider_options 作为逃生口。

Provider-hosted tools：

- Web Search、Image Process、Knowledge Search、Remote MCP 不是 v0.4 通用 tool 抽象的一部分。
- 如用户必须使用，可通过 `provider_options["tools"]` 或更明确的 provider-native override 透传，但这类用法不纳入稳定 public helper。

### 响应映射

Volcengine Responses response 到 `GenerationResponse`：

```text
response.id -> GenerationResponse.id
response.model -> GenerationResponse.model
response.status -> GenerationResponse.stop_reason
response.output -> GenerationResponse.output_items
response.usage -> Usage
raw response -> GenerationResponse.raw
```

Output item：

- `message` -> `MessageItem(role=assistant, parts=[TextPart(...)])`
- `function_call` -> `FunctionCallItem`
- `function_call_output` -> `FunctionResultItem`, when returned by provider
- `reasoning` -> `ReasoningItem`
- unknown output item -> 记录到 `metadata["unsupported_output_items"]`，若全是不可映射 item 则抛 `ProviderResponseMappingError`

Snapshot：

- 对可重放 output item 保存 `ProviderItemSnapshot(provider="volcengine", api_family="responses", payload=raw item)`。
- snapshot `item_type` 使用 provider 原生 item type。
- `replayable` 由 item 类型决定；不确定时宁可 `False`，避免强制 replay 误用。

Usage：

```text
usage.input_tokens -> Usage.input_tokens
usage.output_tokens -> Usage.output_tokens
usage.total_tokens -> Usage.total_tokens
usage.input_tokens_details.cached_tokens -> Usage.cached_tokens
usage.output_tokens_details.reasoning_tokens -> Usage.reasoning_tokens
raw usage -> Usage.raw
```

## Streaming 映射

`stream.py` 将 Volcengine Responses stream event 映射为 `GenerationStreamEvent`，并保留 `raw_event`。

必需覆盖事件：

```text
response.created -> RESPONSE_CREATED
response.in_progress -> RESPONSE_STARTED
response.output_item.added -> ITEM_CREATED / REASONING_CREATED / TOOL_CALL_CREATED
response.output_item.done -> ITEM_COMPLETED / REASONING_COMPLETED / TOOL_CALL_COMPLETED
response.content_part.added -> CONTENT_PART_CREATED
response.content_part.done -> CONTENT_PART_COMPLETED
response.output_text.delta -> TEXT_DELTA
response.output_text.done -> TEXT_COMPLETED
response.reasoning_summary_part.added -> REASONING_CREATED
response.reasoning_summary_part.done -> REASONING_COMPLETED
response.reasoning_summary_text.delta -> REASONING_DELTA
response.reasoning_summary_text.done -> REASONING_COMPLETED
response.function_call_arguments.delta -> TOOL_CALL_DELTA
response.function_call_arguments.done -> TOOL_CALL_COMPLETED
response.completed -> RESPONSE_COMPLETED
response.incomplete -> RESPONSE_INCOMPLETE
response.failed -> RESPONSE_FAILED
error events -> RESPONSE_ERROR
unknown events -> UNKNOWN
```

实现要求：

- `sequence` 由 adapter 枚举生成，优先保留 provider `sequence_number` 到 metadata。
- reasoning summary delta 使用 `metadata["reasoning_kind"] = "summary"`。
- function call delta 使用 `metadata` 保留 `output_index`、`item_id`、`call_id` 等定位字段。
- `response.completed` 事件应尽量构造完整 `GenerationResponse`，并映射 usage。
- `GenerationStreamAccumulator` 不需要 provider-specific 改造，除非发现 Volcengine 事件缺少 OpenAI 同构字段。

## Files API

### Client 方法

建议 public 方法：

```python
client.upload_file(file=..., filename=None, purpose=None, mime_type=None, preprocess=None, provider_options=None)
client.retrieve_file(file_id)
client.list_files(purpose=None, limit=None, after=None, provider_options=None)
client.delete_file(file_id)
client.wait_for_file_processing(file_id, timeout=None, poll_interval=1.0)
```

异步对应：

```python
await client.aupload_file(...)
await client.aretrieve_file(...)
await client.alist_files(...)
await client.adelete_file(...)
await client.await_for_file_processing(...)
```

命名可以在实现时微调，但应与 OpenAI adapter 风格一致，并在用户文档中固定。

### Upload 映射

`FileUploadRequest` 到 Volcengine Files API：

```text
file -> file
filename -> filename, if Ark SDK surface needs it
mime_type -> metadata/content type, if supported
preprocess.video_fps -> preprocess_configs.video.fps
preprocess.provider_options -> preprocess_configs/native params
provider_options["purpose"] -> purpose
provider_options -> top-level native params
```

Purpose：

- 火山方舟多模态理解资料使用 `purpose="user_data"`。
- 该字段在 Volcengine 文档中主要用于 Files API 的 provider-side 过滤/分类，当前缺少跨 provider 语义，不能证明为 vatbrain core 的稳定文件资源字段。
- v0.4 删除 core `FilePurpose`，也不在 `FileUploadRequest` / `FileResource` 上保留 normalized purpose。
- Volcengine adapter 可在 `upload_file(..., purpose="user_data")`、`list_files(purpose="user_data")` 或 `provider_options["purpose"]` 中接受原生字符串；未指定时 upload 默认 `user_data`。
- 返回对象仅在 `FileResource.metadata["raw_purpose"]` 保存 provider 原始值。

### FileResource 映射

Volcengine file object 到 `FileResource`：

```text
id -> id
provider -> "volcengine"
filename -> filename
raw purpose -> metadata["raw_purpose"]
bytes -> bytes
status -> FileStatus
created_at -> created_at
expires_at -> expires_at / expire_at
raw -> raw file object
```

状态映射应保守：

- `processed` / `ready` / `success` -> `FileStatus.READY`
- `uploaded` -> `FileStatus.UPLOADED`
- `processing` / `in_progress` -> `FileStatus.PROCESSING`
- `failed` -> `FileStatus.FAILED`
- `deleted` -> `FileStatus.DELETED`
- `expired` -> `FileStatus.EXPIRED`
- unknown -> `FileStatus.UNKNOWN`

`wait_for_file_processing`：

- 若 SDK 提供稳定 helper，可直接使用并映射返回值。
- 否则轮询 `retrieve_file()`，直到状态为 ready/failed/deleted/expired 或超时。
- 超时错误应包装为 `ProviderRequestError` 或后续专门 timeout error；v0.4 可先使用 `ProviderRequestError` 并在 metadata/raw 中保留 file id。

## Embedding 映射

### 请求

`EmbeddingRequest` 到 Volcengine multimodal embedding：

```text
model -> model
inputs[0].parts -> provider input content list
instructions -> extra_body.instructions
dimensions -> dimensions, if provider model supports it
encoding_format -> encoding_format
sparse_embedding -> sparse_embedding.type, text-only
provider_options -> Ark SDK params or request-body extra_body
```

Input 样本：

- `EmbeddingInput("text")` / `TextPart` -> text input。
- `ImagePart(url=...)` / `ImagePart(data=...)` -> image input。
- `VideoPart(url=...)` / `VideoPart(data=...)` -> video input。
- `VideoPart(file_id=...)`、`FilePart`、audio part 暂不支持 embedding 映射。
- tool call/result/reasoning item 不属于 embedding-compatible 输入。
- `sparse_embedding` 仅支持纯文本输入；包含图片或视频时 adapter 应抛 `UnsupportedCapabilityError`，避免发送 provider 会拒绝或语义不明确的请求。

Ark 多模态 embedding API 以“一个样本包含多个 content part”表达多模态输入，并一次返回一个向量。v0.4 因此要求每次 request 只包含一个 `EmbeddingInput`；如需处理多个样本，应由用户代码循环调用，adapter 不会静默合并或拆分样本边界。

### 响应

Provider embedding response 到 `EmbeddingResponse`：

```text
single data object -> EmbeddingVector(index=0)
dense vector -> EmbeddingVector.dense / embedding
sparse vector -> SparseEmbedding(indices, values, dimensions)
encoding_format -> EmbeddingVector.encoding_format
dimensions -> EmbeddingVector.dimensions
usage -> Usage
raw -> raw response
```

Sparse vector 形状需要通过 fixture 锁定。若 provider 返回 dict/map 形式，应结构化转换为 `indices` 与 `values`；不要把原始 sparse map 当作字符串塞进 metadata。

## Capabilities

`get_adapter_capability()` 应可靠声明 adapter 已实现能力：

```text
supports_generation=True
supports_stream_generation=True
supports_async=True
supports_text_embedding=True
supports_multimodal_embedding=True
supports_function_tools=True
supports_usage_mapping=True
```

API family capability：

- `GenerationCapability.supported=True`
- `GenerationCapability.streaming=True`
- `GenerationCapability.input_modalities=("text", "image", "video", "file")`
- `GenerationCapability.output_modalities=("text",)`
- `GenerationCapability.structured_output=True`
- `GenerationCapability.reasoning_config=True`
- `GenerationCapability.supported_reasoning_efforts=("minimal", "low", "medium", "high")`
- `GenerationCapability.reasoning_output=True`
- `GenerationCapability.remote_context=True`
- `GenerationCapability.function_tools=True`
- `EmbeddingCapability.supported=True`
- `EmbeddingCapability.input_modalities=("text", "image", "video")`
- `EmbeddingCapability.dense=True`
- `EmbeddingCapability.sparse=True`
- `EmbeddingCapability.instructions=True`
- `ResourceCapability.file_upload/retrieve/list/delete=True`
- `ResourceCapability.preprocessing=True`
- `ToolCapability.user_function_tools=True`

Model capability：

- 默认不维护内部模型能力真值表。
- `get_model_capability(model)` 返回 unknown fields。
- 用户可通过 `model_capability_overrides` 或方法参数覆写。
- 可把资料中“250615 及之后版本默认支持 Responses API”等事实放入 metadata 备注，但不作为强校验。

## Error Mapping

所有 Ark SDK provider 调用失败包装为 `ProviderRequestError`：

```text
provider="volcengine"
operation="responses.create" / "files.create" / "embeddings.create" / ...
status_code
request_id
error_type
error_code
error_param
raw
cause
```

响应映射失败包装为 `ProviderResponseMappingError`：

- 缺少必要字段。
- output item 类型全不可映射。
- embedding vector 结构无法转换。
- file status 返回结构异常且无法降级 unknown。

Remote context invalid 判断：

- error param 为 `previous_response_id` 或 previous response 相关字段。
- error code/type/message 包含 previous response expired/invalid。
- error message 包含 context expired/invalid。

默认不自动重试；只有显式 replay policy 触发 remote context fallback。

## Provider-native Replay

Volcengine adapter 应与 OpenAI adapter 保持一致：

- 从 response output item 映射 normalized item 时挂载 `ProviderItemSnapshot(provider="volcengine", api_family="responses")`。
- request mapper 在 `ReplayMode.PREFER_PROVIDER_NATIVE` 下优先使用同 provider/API family 的可重放 snapshot。
- `ReplayMode.REQUIRE_PROVIDER_NATIVE` 下，任何待发送 item 缺少 snapshot 且无法原生重放时抛 `InvalidItemError`。
- 差分传输时只要求 suffix items 满足 replay policy；已由 `previous_response_id` 覆盖的前缀不参与本轮 input 构造。
- fallback 到完整 input 时，完整 `items` 都需要按 replay policy 构造。

跨 provider replay 继续不支持。

## 测试计划

默认测试不调用真实 Volcengine API。

### Generation Mapper

覆盖：

- text-only request。
- image URL/data request。
- video file id / URL / data request。
- file id document request。
- generation config 映射。
- `ReasoningConfig(mode="enabled", effort="low")` 映射为 `thinking` + `reasoning`。
- `ResponseFormat` 映射为 `text.format`。
- function tool 声明。
- function result 回填。
- `RemoteContextHint(previous_response_id, covered_item_count)` 差分传输。
- `covered_item_count` 缺失、越界、suffix 为空的错误。
- `provider_options` 透传与冲突字段处理。

### Response Mapper

覆盖：

- assistant message output。
- function_call output。
- reasoning output。
- usage cached/reasoning token 映射。
- provider-native snapshot。
- unsupported output item metadata。
- 全不可映射 output item 抛错。

### Streaming Mapper

使用本地 event fixture 覆盖：

- response lifecycle。
- output item added/done。
- text delta/done。
- reasoning summary part/text delta/done。
- function call arguments delta/done。
- completed usage。
- incomplete/failed/error。
- unknown event raw passthrough。

### Files

覆盖：

- upload 参数映射，包括默认 `user_data` 与 video fps。
- retrieve/list/delete response 映射。
- status normalization。
- wait helper：ready、failed、timeout。
- provider request error wrapping。

### Embeddings

覆盖：

- text embedding。
- image embedding。
- video embedding。
- mixed multimodal sample。
- instructions/dimensions/encoding_format。
- sparse embedding map/list 两类 fixture。
- usage mapping。
- batch input、file_id video 或 unsupported part 抛显式错误。

### Capabilities 与 Client

覆盖：

- API key/base URL 解析。
- lazy sync/async client 创建。
- adapter capability。
- model capability unknown 与 overrides。
- remote context fallback 只在显式 replay policy 下发生。

## Optional Integration Tests

真实 API 测试默认关闭：

```text
ENV_VATBRAIN_RUN_INTEGRATION_TESTS=1
ENV_VATBRAIN_VOLCENGINE_API_KEY=...
```

建议 integration tests 分组：

- smoke text generation。
- smoke streaming generation。
- smoke file upload/retrieve/delete。
- smoke multimodal embedding。

Integration tests 不进入默认 CI，不作为本阶段文档验收条件。

## 文档同步

v0.4 已同步更新：

- [impls/python/STATUS.md](impls/python/STATUS.md)
- [user/python/api-reference.CN.md](user/python/api-reference.CN.md)
- [user/python/quickstart.CN.md](user/python/quickstart.CN.md)
- [user/python/STATUS.md](user/python/STATUS.md)
- 新增 [user/python/volcengine-quickstart.CN.md](user/python/volcengine-quickstart.CN.md)
- [INDEX.md](INDEX.md)

`docs/user/python` 已把“仅 OpenAI provider”的限制改为“OpenAI + Volcengine”，并明确 Volcengine 的支持范围与非范围。

## 实施拆分与结果

### Step 1：包骨架与 capability

- 新增 optional dependency：`volcengine-python-sdk[ark]>=5.0.30,<6`。
- 新增 provider 包。
- 实现 provider constants、`VolcengineClient` 初始化和 capability。
- 新增 client/capability tests。

### Step 2：Responses generation 非流式

- 实现 generation request mapper。
- 实现 generation response mapper。
- 实现 sync/async `generate` / `agenerate`。
- 覆盖 text、multimodal、structured output、reasoning、function tool 和 usage fixtures。

### Step 3：Remote context 与 replay

- 实现 `previous_response_id` 差分传输。
- 实现 provider-native snapshot。
- 实现 `ReplayPolicy` 三种模式。
- 实现 explicit remote context fallback。

### Step 4：Streaming

- 实现 stream mapper。
- 实现 sync/async `stream_generate` / `astream_generate`。
- 用 event fixture 覆盖 lifecycle、text、reasoning、tool、error 与 unknown。

### Step 5：Files API

- 实现 upload/retrieve/list/delete/wait。
- 覆盖 `FileUploadRequest`、`FilePreprocessConfig.video_fps`、`FileResource` 状态映射。

### Step 6：Multimodal embedding

- 实现 embedding mapper。
- 实现 sync/async `embed` / `aembed`。
- 覆盖 dense/sparse、instructions、多模态 input 与 usage。

### Step 7：用户文档与状态

- 新增 Volcengine quickstart。
- 更新 API reference 与 STATUS。
- 补充可选 integration test 说明。

以上步骤已完成。当前默认测试结果：`123 passed`。

## 验收标准

- 默认测试通过：`cd python && ./.venv/bin/python -m pytest`。
- Volcengine adapter 不引入 Chat Completions generation 路径。
- Core/OpenAI adapter 不依赖 Volcengine optional dependency。
- 所有 public 行为有用户文档入口。
- adapter capability 真实反映 v0.4 已实现范围。
- `provider="volcengine"` 在响应、错误、capability、snapshot 中保持一致。

## 风险与决策点

### Ark SDK 类型滞后于文档

火山方舟文档字段可能早于 Ark SDK 类型发布。v0.4 不使用 OpenAI-compatible SDK 或 direct HTTP 绕过该限制。解决策略是：先验证 Ark SDK 是否支持原生额外参数；若不支持，则把对应字段标记为暂不支持，并在实现状态和用户文档中说明。

### Provider Options 过度膨胀

`caching`、`instructions`、`include`、`expire_at` 等短期通过 `provider_options` 透传。只有当字段具备明确跨 provider 语义并有第二个 provider 验证时，才考虑提升为 core。

### Reasoning 可见性差异

Volcengine 返回 reasoning summary，不代表所有 provider 都允许回传原始 reasoning。Normalized `ReasoningItem` 应保守表达 summary 与 metadata，原生内容保存在 raw/snapshot。

### Files Purpose 不进入 Core

火山方舟使用 `user_data`，但当前资料显示它主要服务 Files API 的 provider-side 查询过滤/分类，而不是可跨 provider 复用的文件资源语义。v0.4 删除 core `FilePurpose`，不再把 `purpose` 放入 `FileUploadRequest` / `FileResource`；Volcengine adapter 以字符串参数和 `provider_options` 承接原生字段，返回值只保留 `metadata["raw_purpose"]`。若后续多个 provider 出现一致的文件用途语义，再重新评估是否提升为 core。

### Hosted Tools 边界

Web Search、Image Process、Knowledge Search、Remote MCP 能力诱人，但执行责任、计费、权限和生命周期不同。v0.4 不把它们纳入通用 tool 模型，避免在第二 provider 阶段过早固化。
