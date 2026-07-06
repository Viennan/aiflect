# Provider 能力整合设计

状态：设计草案  
日期：2026-05-05  
最近更新：2026-06-06

## 背景

在第一阶段，`aiflect` 以 OpenAI adapter 验证了核心 generation、streaming、function tool、text embedding 和 capability 模型。新增的火山方舟资料显示，现代 provider 往往不只提供“文本生成接口”，还同时提供 Responses/Chat 双 API、文件资源管理、多模态 embedding、provider-hosted tools、图片生成、视频生成和异步任务。

因此，`aiflect` 的设计需要从“单一 LLM 调用抽象”演进为“多 API 家族共享同一内容模型和能力模型”的架构。相关第三方资料索引见 [volengine/INDEX.md](../3rds/volengine/INDEX.md)。

## 设计哲学

### Provider State Is Optimization

`aiflect` 仍坚持 Full-context First：一次 generation 调用的语义事实来源是用户传入的完整 `Item` 序列。provider 的 `previous_response_id`、cache、stored response 或 context API 可以作为性能、成本和延迟优化，但不能成为核心状态模型。provider conversation 这类持久化上下文暂不进入通用 core 抽象。

Full-context First 是语义约束，不等同于每次都全量传输。若用户显式提供 `RemoteContextHint.new_items_start_index`，response-style adapter 可以在边界前一个 item 的 provider snapshot metadata 中查找 response id，并只把新增 suffix 发送给 provider。新增边界必须来自 `RemoteContextHint` 等显式字段，不能由 adapter 根据 role、purpose 或 provider id 自动猜测。

这样做的原因是，火山方舟 Responses API 支持默认存储 response、`previous_response_id` 和 `caching`，但这些能力具有 provider 生命周期、过期时间和迁移限制。它们应通过 `RemoteContextHint.enable_cache`、`provider_options` 或 adapter 优化策略暴露，而不是让用户误以为 `aiflect` 自身维护了远端会话真值。远端过期时间暂不作为通用 core 字段。

远端状态失效时，用户传入的完整 `Item` 序列仍应足够恢复调用。为避免同 provider 重放时丢失原生字段，core 应引入 provider-native snapshot 和显式 replay policy。强制 replay 模式要求所有待重放 item 都有匹配 provider/API family 的可重放 snapshot，否则必须报错。跨 provider replay 暂不支持，长期作为 TODO 研究。

参考：[response_api.md](../3rds/volengine/response_api.md)、[reasoning.md](../3rds/volengine/reasoning.md)。

### API Family Boundaries

`generation`、`embedding`、`resource/file`、`media generation` 属于不同 API 家族。它们可以共享 `Item`、`Usage`、`Capability`、`ProviderError` 等基础模型，但不应强行放进同一个 request/response。

这一边界来自几个差异：

- generation 表达多轮推理上下文、工具调用、reasoning 和结构化输出。
- embedding 表达样本级向量化、dense/sparse vectors、instructions 和跨模态检索语义。
- resource/file 表达上传、检索、状态、过期、预处理和删除。
- media generation 表达图片/视频产物、流式局部产物、异步任务、轮询和 artifact 输出。

### Responses API over Chat Compatibility

对于同时支持 Responses API 与 Chat Completions API 的 provider，`aiflect` adapter 应只使用 Responses API 实现 generation。Chat API 可以作为资料中的迁移对照、参数语义参考或 legacy provider 的实现参考，但不应在同一个 provider adapter 中作为兼容 fallback 或平行调用路径。

这个原则尤其适用于火山方舟：资料中同时包含 Chat API 与 Responses API，但 `VolcengineClient.generate()`、`stream_generate()` 和工具调用映射应以 Responses API 为目标。

### Explicit Tool Ownership

`aiflect` 不自动执行用户定义的函数工具，这一原则不变。当前通用 core 暂只抽象 user-executed function tools。

例如火山方舟 Responses API 支持 function、web search、image process、knowledge search 和 MCP。v0.3 阶段只将 function tool 纳入通用 core；web search、image process、knowledge search、MCP 等 provider-hosted/remote tools 留待后续专门设计，避免过早固化执行责任和生命周期语义。

参考：[function_calling.md](../3rds/volengine/function_calling.md)、[response_api.md](../3rds/volengine/response_api.md)。

### Reasoning Visibility Is Provider-specific

reasoning 不只是一个控制参数，也可能作为模型输出内容出现。火山方舟同时存在 `thinking.type`、`reasoning.effort`、Chat API 的 `reasoning_content` 和 Responses API 的 `reasoning` output item。

`aiflect` 应将 reasoning 设计为两层：

- `ReasoningConfig`：用户希望模型如何推理，例如 mode、effort、budget、summary policy。
- `ReasoningItem`：provider 返回的 reasoning summary、reasoning text 或 provider 原始 reasoning 内容。

由于不同 provider 对 reasoning 可见性、可回传性和安全策略不同，`ReasoningItem` 应保留来源、可见性、是否可作为后续上下文回传等元数据。

参考：[reasoning.md](../3rds/volengine/reasoning.md)、[streaming.md](../3rds/volengine/streaming.md)。

## 模块职责

### Core

`core` 继续负责 provider-neutral 领域模型，但需要扩展 API 家族：

- `core.items`：扩展 `TextPart`、`ImagePart`、`AudioPart`、`VideoPart`、`FilePart`、`ReasoningItem`、`FunctionCallItem`、`FunctionResultItem`。
- `core.generation`：表达 full-context generation、reasoning config、structured output、tool call config、remote context hints 和 generation stream。
- `core.embeddings`：表达多模态 embedding input、instructions、dense vector、sparse vector、encoding format、usage。
- `core.resources`：表达 provider file/resource 的生命周期、状态、用途、预处理配置。
- `core.media`：表达图片/视频生成请求、产物、流式事件、异步任务。
- `core.tools`：表达 user-executed function tools 和执行责任；provider-hosted/remote tools 暂缓。
- `core.capabilities`：按 API 家族表达 adapter capability 和 model capability。

### Provider Client

provider client 仍按 provider 初始化，并在每次调用时显式传入 model。对于火山方舟，概念形态可以是：

```text
VolcengineClient(config).generate(model=..., items=...)
VolcengineClient(config).stream_generate(model=..., items=...)
VolcengineClient(config).embed(model=..., inputs=...)
VolcengineClient(config).upload_file(...)
VolcengineClient(config).generate_image(model=..., ...)
VolcengineClient(config).create_video_generation_task(model=..., ...)
```

环境变量建议使用 `ENV_AIFLECT_VOLCENGINE_API_KEY`。如果 adapter 选择兼容 OpenAI SDK 调用火山方舟，也不能把 provider identity 伪装成 OpenAI；provider id 应保持 `volcengine`。

### Providers

provider adapter 负责将通用模型映射到厂商 API。对于火山方舟，adapter 需要面对至少两类调用面：

- OpenAI-compatible SDK surface：Responses、Images、Files 等。Chat Completions 仅作为资料对照，不作为 adapter 实现目标。
- 火山方舟原生 SDK surface：Ark/AsyncArk、multimodal embeddings、content generation task 等。

adapter 可以分阶段选择调用面，但必须在 adapter capability 中声明真实覆盖范围。

## 核心抽象完善

### Remote Context Hint

为了表达 provider-side cache/delta 优化，而不破坏 Full-context First，可以在 generation request 中加入 `remote_context` 类型的 hint：

```text
RemoteContextHint
- enable_cache
- session_key
- new_items_start_index
- provider_options
```

这些字段只是优化提示。用户仍应传入完整语义上下文。adapter 可以选择忽略 hint，也可以在 capability 中声明支持。provider conversation 持久化上下文暂不纳入该模型。

`new_items_start_index` 表示完整 `GenerationRequest.items` 中从哪里开始是本轮新增 item。adapter 若基于 provider remote context 做差分传输，可以从边界前一个 item 的 snapshot metadata 中查找 response id，并发送 `items[new_items_start_index:]`；若 response id 缺失或失效，则必须重新发送完整 `items`。

`enable_cache` 描述是否启用 provider-side cache/stored response 优化。对 response-style provider，它允许本轮 response 被 provider 存储并在未来作为 response id anchor；对 Anthropic Messages API，它映射为 automatic prompt caching。

`session_key` 描述多轮请求所属的 provider-side cache pool / session cache 标识。它不是 `aiflect` 的会话状态句柄，也不允许用户省略完整 `items`。OpenAI adapter 可映射为 `prompt_cache_key`，Volcengine adapter 可映射为 Responses API Session cache 参数组合。

### Provider-native Replay

provider-native replay 用于同 provider/API family 下的高保真上下文重放。它不取代 normalized `Item`，而是在 `Item` 上关联 provider 原始 item payload：

```text
ProviderItemSnapshot
- provider
- api_family
- item_type
- payload
- replayable
- captured_from
- schema_version
- metadata
```

generation request 可增加 replay policy：

```text
ReplayPolicy
- mode: normalized_only | prefer_provider_native | require_provider_native
- cross_provider: unsupported
```

其中 `require_provider_native` 是强制 replay 选项。它适合 OpenAI Responses 这类历史 item 原生字段会影响后续生成行为的场景。

remote context 的传输策略不进入通用 `ReplayPolicy`。core 只表达 `new_items_start_index` 这样的新增边界；各 provider adapter 根据自身 API 语义决定是否差分传输。例如 OpenAI Responses adapter 在 anchor item 上存在 response id 且边界明确时，应只发送新增 input；失效 refresh 则回到完整 `items`。

OpenAI assistant message 的 `phase` 可作为 `AssistantMessagePhase(commentary | final_answer)` 纳入通用抽象候选，因为它表达 assistant 历史输出阶段，而非纯粹随机 provider 参数。但即便纳入该字段，也仍需要 provider-native snapshot 保留更完整的 provider payload。

完整方案见 [provider-native-replay.CN.md](provider-native-replay.CN.md)。

### Resource/File

文件资源应独立于 message content：

```text
FileResource
- id
- provider
- filename
- purpose
- mime_type
- bytes
- status
- created_at
- expires_at
- preprocess
- metadata
- raw
```

`FilePart` 则用于在 generation、embedding 或 media generation 中引用文件：

```text
FilePart
- file_id
- url
- data
- local_path
- mime_type
- media_type
- provider
- metadata
```

本地路径上传不应默认隐式发生。若 adapter 提供便捷上传，应通过显式方法或清晰的 `auto_upload` 配置开启。

参考：[file_api.md](../3rds/volengine/file_api.md)、[image_understanding.md](../3rds/volengine/image_understanding.md)、[video_understanding.md](../3rds/volengine/video_understanding.md)。

### Multimodal Embedding

embedding request 应补充：

```text
EmbeddingRequest
- model
- inputs
- instructions
- dimensions
- encoding_format
- sparse_embedding
- provider_options
```

embedding response 应补充：

```text
EmbeddingVector
- index
- dense
- sparse
- encoding_format
- dimensions
- metadata
- raw
```

`instructions` 属于 embedding 的通用语义，因为多模态检索中 query/corpus 的目标模态和任务指令会显著影响向量空间，而不是 provider 私有杂项。

参考：[embeding.md](../3rds/volengine/embeding.md)。

### Media Generation

图片/视频生成不应复用 generation request。建议新增 media API 家族：

```text
ImageGenerationRequest
- model
- prompt
- input_items
- size
- output_format
- response_format
- count
- tools
- stream_options
- provider_options

ImageGenerationResponse
- provider
- model
- artifacts
- usage
- raw
```

视频生成通常是异步任务：

```text
MediaGenerationTask
- id
- provider
- model
- status
- artifacts
- error
- created_at
- updated_at
- raw
```

这类 API 需要 artifact model，例如 URL、base64、provider file id、mime type、size、duration、metadata。

参考：[image_generation.md](../3rds/volengine/image_generation.md)、[video_generation.md](../3rds/volengine/video_generation.md)。

## Capability 完善

capability 应按 API 家族拆分，而不是只用几个布尔字段：

```text
AdapterCapability
- generation
- stream_generation
- text_embedding
- multimodal_embedding
- sparse_embedding
- file_resources
- image_generation
- video_generation
- user_function_tools
- usage_mapping
```

model capability 可以继续允许 unknown，但应增加 modality 与 API family 维度，例如：

- 支持的 input modalities：text、image、audio、video、file。
- 支持的 output modalities：text、image、audio、video、embedding。
- reasoning mode 与 provider/model 支持的 effort 字符串集合。
- structured output 支持情况。
- embedding dense/sparse、dimensions、instructions 支持情况。
- media generation 的 resolution、duration、output format、streaming/task 支持情况。

## 演进路线

### 阶段 1：设计与 core 稳定

- 更新高层设计，明确 provider state、resource/file、media generation、reasoning visibility，并记录 provider-hosted/remote tools 暂缓进入通用 core 的取舍。
- 扩展 `Item` 的设计语义，但实现上可先保持最小破坏。
- 先定义接口边界，再做 provider adapter。

### 阶段 2：Python core 扩展

- 增加 `FilePart`、`VideoPart`、`AudioPart`、`ReasoningItem`。
- 增加多模态 embedding 和 sparse embedding 模型。
- 增加 resource/file 与 media artifact/task core 模型。
- 增强 capability API family 表达。

### 阶段 3：Volcengine adapter MVP

- provider id：`volcengine`。
- client 初始化支持 `api_key`、`base_url`、`timeout`、`max_retries`。
- API key 环境变量：`ENV_AIFLECT_VOLCENGINE_API_KEY`。
- 支持 Responses API text/image/video understanding、reasoning、function tool、streaming、usage。
- 不引入 Chat Completions API 调用路径。
- 支持 Files API 上传/检索/删除。
- 支持 multimodal embedding。

### 阶段 4：Hosted tools 与 media generation

- 支持 web search、image process、knowledge search、MCP 的声明映射。
- 支持 image generation 的同步/流式事件。
- 支持 video generation 的任务创建、轮询、结果映射。

## FAQ

### 火山方舟的 `previous_response_id` 是否改变 Full-context First？

不改变。`previous_response_id` 是 provider-side optimization。`aiflect` 的语义事实仍来自用户传入的完整上下文。adapter 可以使用 `previous_response_id` 降低成本或延迟，但不能让它成为不可见状态依赖。若 adapter 使用 `previous_response_id` 做差分传输，用户必须提供新增边界；失效 refresh 仍应回到完整 `items`。

用户不直接传入 `previous_response_id`。adapter 从边界前一个 item 的 provider snapshot metadata 中读取 response id；如果找不到或失效，就回到完整 `items`。本轮 `RemoteContextHint.enable_cache=True` 会请求 provider 创建未来可引用的 response。

### 跨 provider replay 是否支持？

暂不支持。provider-native snapshot 不跨 provider 使用。长期 TODO 是研究基于 normalized `Item`、assistant phase、reasoning visibility、tool protocol item 和 file reference 的受限迁移能力，并在执行前提供兼容性报告。

### 火山方舟 adapter 是否需要兼容 Chat API？

不需要。火山方舟同时提供 Chat API 与 Responses API 时，`aiflect` 只使用 Responses API。Chat API 文档可以帮助理解迁移差异，但不进入 adapter 的 generation 调用路径。

### provider-hosted tools 是否违反 No Hidden Orchestration？

原则上不违反，但其执行责任、生命周期和审计语义需要单独设计。当前通用 core 只抽象用户执行的 function tool；provider-hosted/remote tools 暂不进入 v0.3。

### 为什么图片/视频生成不直接放进 generation？

因为媒体生成的请求、产物、流式事件、异步任务和 usage 统计都与 LLM generation 差异很大。复用名称会让 API 看似统一但语义混乱。它应作为 media generation API 家族存在。

### 是否应该马上实现 Volcengine adapter？

不建议直接开写完整 adapter。应先稳定 core 边界，随后做 Volcengine adapter MVP：Responses API、Files API、多模态 embedding。图片/视频生成和 provider-hosted/remote tools 可以作为后续阶段。

### 第三方资料如何进入知识库？

第三方资料保存在 `docs/3rds`，作为能力事实来源；设计归纳进入 `docs/design`；实现细节进入 `docs/impls`；用户用法进入 `docs/user`。
