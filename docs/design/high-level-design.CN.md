# vatbrain 高层次设计方案

状态：设计草案  
日期：2026-05-04  
最近更新：2026-05-10

## 背景

`vatbrain` 面向多个 AI 厂商提供统一的 LLM 推理调用抽象。它的目标不是替代厂商 SDK，也不是构建自动 agent 框架，而是在 OpenAI、Anthropic、Google 及其他厂商能力之上提供一套稳定、清晰、可移植的领域模型。

该抽象层重点统一以下内容：

- 内容生成与多轮推理上下文表达。
- 文本、图片、音频、视频、文件等多模态输入输出表达。
- 工具声明、工具调用输出、工具结果回填协议。
- 流式事件模型。
- token 与 usage 统计。
- provider/model 能力描述、能力提示与用户覆写。
- provider 侧存储、缓存、上下文 ID 等远端状态优化提示。
- 文件资源上传、引用、状态管理与预处理。
- 图片、视频等媒体生成任务与产物表达。
- embedding，尤其是多模态 embedding 的输入与输出表达。

## 设计哲学

### Full-context First

每次内容生成调用都应以完整上下文序列作为语义事实来源。provider 侧的 conversation、previous response、cache 或其他状态能力可以作为优化手段，但不能成为 `vatbrain` 的核心状态模型。

这一设计使 `vatbrain` 能够兼容只支持全量 messages/completion 调用的厂商，也能降低远程 response 过期、不可迁移或不可恢复带来的风险。

### Explicit Provider Invocation

`vatbrain` 不提供自动 provider routing、自动模型选择、自动 fallback 或自动成本优化。用户必须明确知道自己要调用的厂商、模型及相关配置，并显式发起调用。

能力描述用于帮助用户理解和校验 provider/model 能力，而不是替用户做规划。由于许多厂商并不提供可靠、完整、实时的模型能力查询接口，`vatbrain` 不应暗示自己总能掌握模型能力真值。

### No Hidden Orchestration

`vatbrain` 不内建类似 ReAct 的推理循环，也不自动执行工具调用。工具调用是模型输出的一种结构化结果，工具执行、结果回填和下一轮调用由用户代码自行决定。

因此，`vatbrain` 的角色是推理协议抽象层，而不是 agent runtime。

### Item-centered Content Model

`Item` 是 `vatbrain` 的核心内容元模型，用于表达“可被模型消费或由模型产生的上下文组件”。它不应只等同于 chat message，而应覆盖文本、图片、音频、视频、文件、工具调用、工具结果、reasoning 信息及其他可扩展内容。

`Item` 可以被不同 API 家族共用，但每个 API 家族应限定自己可接受的 `Item` 范围，并明确这些 `Item` 在该 API 中的语义。

### Capability-aware Portability

`vatbrain` 的抽象层可以表达多个厂商原生 API 可实现特性的并集，但每个 provider adapter 只承诺自己真实支持的 adapter 能力。对于具体模型的上下文窗口、输出向量维度、模态支持等 model 能力，`vatbrain` 应允许表达未知、provider 声明、用户声明或其他来源，而不是强行维护一张内部模型能力真值表。

不应为了表面统一而隐藏能力差异。

### Provider State as Optimization

provider 侧的 stored response、previous response、conversation、context cache 或其他上下文状态能力应被视为优化提示，而不是 `vatbrain` 的核心语义状态。

`vatbrain` 允许用户通过 `RemoteContextHint` 表达是否启用 provider-side cache，以及完整 `items` 中新增 item 的起始位置。用户不直接管理 provider response id；response-style adapter 会从历史 item 的 provider snapshot metadata 中查找 response id，并按 provider 语义决定是否发送 suffix。调用语义仍由用户传入的完整 `Item` 序列定义。provider conversation 这类持久化上下文暂不进入通用 core 抽象，prompt/cache retention 与远端过期时间仍通过 provider-specific 能力处理。

Full-context First 不等于每次 provider 请求都必须传输完整 input。若用户明确提供 `RemoteContextHint.new_items_start_index`，response-style adapter 可以在边界前一个 item 中找到 response id 时只发送新增 suffix；若找不到 response id，则退化为完整 input。adapter 不能只凭 role、purpose 或 provider item id 猜测哪些 item 是 history、哪些 item 是新增输入。

当 response-style provider 返回明确的 previous response/context 失效错误时，adapter 应移除失效 response id，并基于完整 `Item` 序列自动 refresh 一次。该行为只针对明确的 remote context invalid/expired 错误，不扩大为通用网络或业务错误重试。为避免丢失 provider 原生 item 字段，`vatbrain` 支持 provider-native snapshot 与强制 replay 策略；详见 [provider-native-replay.CN.md](provider-native-replay.CN.md)。

### API-family Separation

generation、embedding、resource/file、media generation 是不同 API 家族。它们可以共享 `Item`、usage、capability、error 和 provider client，但不应强行合并为一个请求模型。

这一分离避免把多轮推理、样本向量化、文件生命周期、图片/视频产物、异步任务等差异很大的语义混在一起。

### Responses API over Chat Compatibility

对于同时支持 Responses API 与 Chat Completions API 的 provider，`vatbrain` 的 generation adapter 应仅使用 Responses API。

Chat Completions API 可以作为迁移资料、语义对照或 legacy provider 的参考，但不应为了兼容性在同一个 provider adapter 中额外引入 Chat Completions API 调用路径。这样可以避免双调用面带来的映射分叉、测试膨胀和行为差异。

### Explicit Tool Ownership

工具声明必须表达执行责任。当前通用 core 只抽象用户代码执行并回填结果的 function tool。provider-hosted tool、remote tool 或 MCP tool 暂不进入通用 core 抽象，后续在语义稳定后再设计。

`vatbrain` 不自动执行用户工具。

## 模块职责

### Core

`core` 定义厂商无关的领域模型，重点包括：

- `Item` 及其内容结构。
- role、purpose、modality 等语义枚举。
- generation 请求、响应与流式事件。
- embedding 请求、响应与向量结果。
- resource/file 请求、响应与文件状态。
- media generation 请求、产物、任务与流式事件。
- 工具声明、工具调用、工具结果。
- usage、capability、error 等通用模型。

`core` 应保持纯粹，不依赖具体 provider SDK。

### Provider Client

client 的初始化粒度是 provider，而不是 model。同一个 provider client 可以复用认证信息、base URL、HTTP 连接池、超时、重试基础设施等 provider 级资源，并在每次调用时由用户显式传入 model。

provider client 应支持通用初始化参数，例如 `api_key`、`base_url`、`timeout`、`max_retries`。其中 `api_key` 应支持从环境变量读取。环境变量命名以 `ENV_VATBRAIN_` 开头，并按 provider 区分，例如 OpenAI adapter 使用 `ENV_VATBRAIN_OPENAI_API_KEY`。

概念形态如下：

```text
ProviderClient(config).generate(model=..., items=...)
ProviderClient(config).stream_generate(model=..., items=...)
ProviderClient(config).embed(model=..., inputs=...)
ProviderClient(config).upload_file(...)
ProviderClient(config).generate_image(model=..., ...)
```

client 不负责选择模型，不执行 fallback，不运行工具循环。

### Providers

`providers` 负责实现各厂商 adapter，将 `vatbrain` 的领域模型映射到厂商原生 API，并将厂商响应或流式事件映射回 `vatbrain` 的统一模型。

每个 provider adapter 应暴露自身支持的 adapter capability。它可以只实现部分 API 家族，例如只支持 generation，不支持 embedding，或只支持文本 embedding，不支持多模态 embedding。

若 provider 同时提供 Responses API 与 Chat Completions API，generation adapter 应选择 Responses API 作为唯一实现目标。Chat Completions API 不应作为同一 provider 的兼容 fallback 或平行实现面。只有当某个 provider 不提供 Responses 风格 API 时，adapter 才可以基于其 Chat/Completions 风格 API 映射到 `vatbrain` generation 模型。

对于 model capability，provider adapter 可以接入厂商 API、SDK 常量、厂商文档快照或用户配置，但必须标注来源和可靠性。当无法可靠获取时，应返回 unknown，而不是猜测。

### Generation

generation API 负责内容生成、多轮上下文、多模态理解、结构化输出、工具调用等推理类场景。

其核心输入是完整、有序的 `Item` 序列。该序列表达一次推理调用所需的全部上下文，包括系统指令、用户输入、历史 assistant 输出、工具调用与工具结果等。

generation 输出同样应以 `Item` 序列表达，避免把模型输出简化为纯文本。

generation 请求还应包含若干通用行为配置。凡是表达“用户希望模型如何推理、如何生成输出、如何使用工具”的跨厂商语义，都应优先进入 `core` 的通用配置，而不是被放进某个 provider 的专有参数中。

例如 reasoning 配置和并行工具调用配置应被视为通用 generation 语义：

- reasoning 配置描述用户对模型推理行为的要求，例如 reasoning effort、reasoning token budget、是否请求 reasoning summary 或可观察 trace。
- tool call 配置描述用户对工具调用行为的约束，例如是否允许 parallel tool calls、是否指定 tool choice。

不同 provider/model 可以只支持其中一部分字段。adapter 负责将通用语义映射到厂商原生参数；无法映射时应基于 capability 与用户策略进行处理。

provider 侧上下文状态可以通过 generation request 中的远端上下文 hint 表达，但只作为优化提示。即使某个 provider 支持 `previous_response_id` 或缓存，`vatbrain` 的推荐编程模型仍是由用户代码维护完整语义上下文。通用 `RemoteContextHint.enable_cache` 只表达是否启用 provider-side cache/stored response，远端过期时间等细节仍不进入通用 core。

### Embedding

embedding API 与 generation API 平行存在，不强行并入 generation 请求模型。embedding 的输入输出形态、批处理语义、向量维度、encoding format 和 usage 统计通常与内容生成接口不同，因此需要独立抽象。

embedding 可以与 generation 共用 `Item`，但只能使用 embedding-compatible 的 `Item` 子集，例如文本、图片、音频、视频、文件等可被表征的内容。工具调用、工具结果、reasoning 等推理协议类 `Item` 不应作为 embedding 输入。

embedding 中的 `Item` 列表表达“同一个待向量化样本的多模态内容集合”，而不是 generation 中的多轮推理上下文。

embedding 可包含任务指令，例如 query/corpus 检索指令、目标模态提示等。这类指令会影响向量空间语义，应作为 embedding 的通用配置，而不是 provider 专有参数。

embedding 输出可包含 dense vector、sparse vector 或 provider 特定 encoding format。标准模型应优先表达 dense/sparse 的结构化结果，同时保留 raw response。

### Resources and Files

resource/file API 负责表达 provider 文件资源生命周期，包括上传、检索、列表、删除、状态、过期时间、用途和预处理配置。

文件资源不应只作为 message content 中的字符串处理。对于大文件、多次复用文件、需要 provider 预处理的图片、视频或 PDF，`vatbrain` 应提供独立资源模型，并允许 generation、embedding 或 media generation 通过 `FilePart` 引用资源。

本地路径上传属于 I/O 副作用，不应默认隐式发生。若 adapter 提供便捷上传能力，应通过明确方法或显式配置启用。

### Media Generation

media generation API 负责图片、视频、音频等媒体产物生成、编辑、变体生成和多模态参考生成。

图片/视频生成与 LLM generation 不同：它们通常包含输出格式、分辨率、宽高比、数量、duration、watermark、artifact URL/base64、流式局部产物、异步任务与轮询。因此应作为独立 API 家族，而不是复用 `GenerationRequest`。

视频生成等耗时任务应通过 task/operation 模型表达创建、查询、取消、完成、失败和 artifact 输出。

### Tools

`tools` 只定义协议，不定义行为。它负责表达：

- 工具 schema。
- 工具执行责任，例如 user、provider、remote。
- 模型请求调用工具的结构化输出。
- 用户执行工具后回填给模型的工具结果。
- 工具调用与工具结果之间的关联标识。

`vatbrain` 不自动执行工具，也不自动把工具结果提交给模型。

provider-hosted tools，例如 web search、image process、knowledge search 或 MCP，暂不作为通用 core tool 模型暴露。短期如需使用，应通过 provider-specific options 或后续 adapter 专有扩展处理。

### Usage

`usage` 负责统一 token 与资源消耗统计。它应同时保留 normalized usage 和 provider raw usage。

normalized usage 可覆盖输入 token、输出 token、cache token、reasoning token、多模态 token 等字段；raw usage 用于保留厂商原始统计信息，避免过度归一化造成信息损失。

## 核心抽象

### Item

`Item` 建议至少包含三个语义维度：

- `kind`：该 item 是什么，例如 message、text、image、audio、video、file、function_call、function_result、reasoning。
- `role`：该 item 在推理上下文中的来源或说话者，例如 system、developer、user、assistant、tool。
- `purpose`：该 item 的用途，例如 instruction、query、context、answer、tool_io、artifact。

单一 role 无法充分表达 item 语义。例如，一张图片可以来自 user，目的可以是 query context；一个文件可以来自 tool，目的可以是 retrieval result；一段 reasoning 可以来自 assistant，但并不等同于最终回答。

对于由 provider 返回、后续可能重放的 item，`Item` 还需要能够关联 provider-native snapshot。snapshot 只用于同 provider/API family 下的高保真重放，不应作为跨 provider 的通用语义来源。

### Generation Request/Response

generation 请求的核心语义是：

```text
GenerationRequest
- model
- items
- tools
- generation_config
- response_format
- reasoning
- tool_call_config
- stream_options
- remote_context
- replay_policy
- provider_options
```

其中 `items` 是完整上下文序列。`reasoning` 与 `tool_call_config` 表达跨厂商的通用 generation 语义。`remote_context` 表达 provider 侧状态、缓存、previous response 及其对完整 `items` 前缀的覆盖范围。`replay_policy` 表达当用户需要重放完整上下文时，adapter 是否允许、偏好或强制使用 provider-native snapshot，以及 remote context 失效时是否允许显式 fallback。`provider_options` 只用于承载少量不可移植但必要的厂商专有参数。

generation 响应的核心语义是：

```text
GenerationResponse
- id
- provider
- model
- output_items
- stop_reason
- usage
- metadata
- raw
```

### Embedding Request/Response

embedding 请求应以样本为单位组织输入：

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

每个 input 可以包含一个或多个 embedding-compatible `Item`，用于表达同一样本的多模态内容集合。

embedding 响应应表达：

```text
EmbeddingResponse
- provider
- model
- vectors
- dimensions
- usage
- metadata
- raw
```

其中 `vectors` 可以包含 dense vector 与 sparse vector。对于只支持 dense vector 的 provider，sparse vector 为 unknown 或空。

### Resource/File Request/Response

文件资源请求应表达：

```text
FileUploadRequest
- file
- purpose
- mime_type
- expires_at
- preprocess
- provider_options
```

文件资源响应应表达：

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

`FilePart` 可在不同 API 家族中引用 `FileResource`：

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

### Media Generation Request/Response

图片生成请求的核心语义可表达为：

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
```

视频生成和其他长耗时媒体任务应使用 task/operation 模型：

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

媒体产物应使用 artifact 模型表达 URL、base64、provider file id、mime type、size、duration、metadata 与 raw provider payload。

## 流式事件模型

流式输出应被视为标准事件日志，而不是简单的文本 delta。generation stream 应能表达 response 生命周期、item 生命周期、内容增量、工具调用参数增量、usage 更新和错误。

建议的事件类别包括：

- `response.created`
- `response.started`
- `item.created`
- `item.delta`
- `item.completed`
- `tool_call.created`
- `tool_call.delta`
- `tool_call.completed`
- `usage.updated`
- `response.completed`
- `response.failed`

事件应包含稳定的关联信息，例如 sequence、response id、item id、provider、timestamp 和 raw event。调用方应能基于事件流重建最终响应。

## Capability 模型

capability 模型应按 provider/model 暴露，并区分 API 家族。但它不是一个由 `vatbrain` 内部维护的全量模型数据库，也不保证对所有厂商、所有新模型实时准确。

capability 应拆分为两类：

- `AdapterCapability`：provider adapter 自身实现了哪些接口和转换能力，例如是否实现 generation、stream generation、embedding、工具调用映射、usage 解析等。这部分由 `vatbrain` adapter 可靠声明。
- `ModelCapability`：某个具体 provider/model 的能力与限制，例如上下文窗口、支持模态、输出向量维度、是否支持结构化输出等。这部分可能来自厂商 API、SDK 常量、文档、用户配置或运行时观测，也可能未知。

`ModelCapability` 的字段应允许 unknown。对于 max context tokens、embedding dimensions、max batch size 等易随模型变化而变化的字段，unknown 是正常状态，而不是异常。

每个 model capability 字段或 capability profile 应能携带来源信息，例如：

```text
CapabilitySource
- provider_api
- provider_sdk
- provider_docs
- user_config
- adapter_builtin
- runtime_observed
- unknown
```

同时应能表达可靠性或置信级别，例如：

```text
CapabilityReliability
- authoritative
- declared
- user_supplied
- best_effort
- observed
- unknown
```

其中：

- `authoritative` 表示来自厂商官方实时 API 或其他明确可靠来源。
- `declared` 表示来自厂商 SDK、文档或静态声明，但可能滞后。
- `user_supplied` 表示由用户配置提供，`vatbrain` 只负责使用，不判断其真实性。
- `best_effort` 表示 adapter 有合理依据但不应作为严格事实。
- `observed` 表示来自历史调用或错误信息推断，只能作为提示。
- `unknown` 表示当前无法可靠判断。

`vatbrain` 不应默认内建或长期维护完整模型能力表。若为了改善体验提供少量 adapter 内置能力信息，也必须标记为 `adapter_builtin` 和对应可靠性，并允许用户覆盖。

generation capability 可描述：

- 支持的输入与输出模态。
- 是否支持 streaming。
- 是否支持 async。
- 是否支持 provider-side store/cache/previous response。
- 是否支持工具调用。
- 是否支持工具调用参数流式输出。
- 是否支持 parallel tool calls。
- 是否支持 tool choice。
- 是否支持结构化输出。
- 是否支持 reasoning 输出。
- 是否支持 reasoning 配置。
- 支持的 reasoning effort 字符串集合。不同 provider 对 effort 的定义可能不同，因此应由 capability 明确列出，而不是由 `vatbrain` 假设全局枚举。
- 是否支持 reasoning token budget。
- 是否支持 reasoning summary。
- 最大上下文长度。
- usage 统计粒度。

embedding capability 可描述：

- 支持的输入模态。
- 是否支持多模态 embedding。
- 是否支持 sparse embedding。
- 是否支持 embedding instructions。
- 是否支持 batch。
- 最大 batch size。
- 最大输入长度。
- 输出向量维度。
- 是否支持自定义维度。
- 支持的 encoding format。

resource/file capability 可描述：

- 是否支持文件上传、检索、列表、删除。
- 支持的文件用途。
- 支持的 MIME 类型。
- 单文件大小限制。
- 文件总容量限制。
- 文件存储时间与过期策略。
- 是否支持预处理。
- 支持的预处理配置。

media generation capability 可描述：

- 是否支持图片生成、图片编辑、视频生成、视频编辑、视频延长。
- 支持的输入参考模态。
- 支持的输出格式、分辨率、宽高比、时长。
- 是否支持 streaming。
- 是否使用异步任务模型。
- usage 统计粒度。

capability 是能力描述和校验辅助，不是自动决策机制。调用前校验只能基于已知信息判断：

- 已知支持：可以通过校验。
- 已知不支持：应给出明确错误。
- 未知：应由用户策略决定是继续调用、告警还是失败。

因此，capability check 不应把 unknown 当作 false，也不应把 best effort 当作绝对事实。

## 非目标

以下能力不属于当前高层设计目标：

- 自动 provider routing。
- 自动模型选择。
- 自动 fallback。
- 自动成本/延迟优化。
- 内部维护完整、实时、权威的模型能力数据库。
- 内建 ReAct 或其他 agent 推理循环。
- 自动工具执行。
- 将所有 API 强行合并进单一请求模型。
- 对同时支持 Responses API 与 Chat Completions API 的 provider 维护双 generation 调用面。

这些能力可以由上层应用或独立框架基于 `vatbrain` 构建，但不应进入 `vatbrain` 核心。

## 演进路线

第一阶段应聚焦最小稳定核心：

- provider 级 client。
- generation 请求/响应。
- `Item` 基础模型。
- 文本与基础多轮上下文。
- 工具声明、工具调用输出、工具结果回填协议。
- 基础 streaming event。
- usage 与 adapter capability 基础模型。

第二阶段扩展多模态与结构化能力：

- 图片、音频、视频、文件输入。
- 更完整的 streaming event 映射。
- 结构化输出。
- reasoning visibility 与 reasoning item。
- provider-side state/cache hint。
- provider raw metadata 保留策略。

第三阶段引入 embedding：

- 文本 embedding。
- 多模态 embedding。
- embedding instructions。
- sparse embedding。
- batch embedding。
- embedding capability，并支持 unknown 与用户覆写。

第四阶段完善跨厂商一致性：

- resource/file API。
- provider-hosted/remote tools 的后续专项设计。
- media generation API 与异步 task 模型。
- 更细粒度的 capability 来源、可靠性和 unknown 处理。
- 更系统的 error model。
- 多 provider adapter 的一致性测试。
- 文档化 provider 差异。

## FAQ

### vatbrain 是否提供自动 routing？

不提供。用户需要显式选择 provider 和 model。`vatbrain` 只提供统一调用抽象和能力描述辅助。

### vatbrain 的 capability 查询是否权威？

不保证权威。adapter 自身支持哪些接口可以由 `vatbrain` 可靠声明，但具体模型的上下文窗口、embedding 维度、batch 限制等信息可能无法可靠获取。此时应返回 unknown，或使用用户显式提供的配置。

### vatbrain 是否维护内部模型能力表？

不应维护完整、实时、权威的内部模型能力表。厂商模型更新可能快于 SDK 或 `vatbrain` 发布节奏。若提供少量内置能力信息，也只能作为带来源和可靠性标记的辅助信息，并允许用户覆盖。

### vatbrain 是否内建 ReAct 或 agent loop？

不内建。模型输出工具调用后，用户自行执行工具，并把工具结果作为新的 `Item` 回填到下一次 generation 调用。

### provider client 应该按模型初始化吗？

不应该。client 的生命周期应按 provider 组织，同一个 provider client 可用于调用该 provider 下的不同模型。

### embedding 是否应该强行并入 GenerationRequest？

不应该。embedding 与 generation 是平行 API 家族，但可以共享部分通用模型，例如 `Item`、usage、capability、error。

### 多模态 embedding 如何表达？

多模态 embedding 使用 embedding-compatible `Item` 子集表达输入。一个 embedding input 可以包含文本、图片、视频、音频或文件等多个 `Item`，表示同一个待向量化样本的多模态内容集合。

### provider 的 previous response 或 cache 是否改变 Full-context First？

不改变。previous response、stored response、context cache 等能力只是 provider-side optimization。`vatbrain` 的语义事实仍应来自用户传入的完整上下文序列。provider conversation 持久化上下文暂不进入通用 core 抽象。

### 使用 previous response 时是否仍要把完整 items 全量传给 provider？

不一定。用户侧仍应传入完整 `items`，但 adapter 可以在 provider 请求层做增量传输优化：当 `RemoteContextHint(enable_cache=True, new_items_start_index=...)` 存在，且边界前一个 item 的 provider snapshot metadata 中存在匹配 response id 时，response-style adapter 可以发送 `previous_response_id` 和新增 suffix。对 Anthropic Messages adapter 来说，仍发送完整 messages，只把 `enable_cache=True` 映射为 automatic prompt caching。

启用 cache 时，response-style provider 会请求存储本轮 response，并将 parent response id 写入输出 item 的 provider snapshot metadata。下一轮用户只需要保留完整 `items` 并提供新增边界，不需要手工保存或传入 response id。

### response id 失效后是否应该自动重放？

应该在非常窄的条件下自动 refresh：只有当本次请求实际发送了 provider response id，且 provider 返回明确的 previous response/context invalid 或 expired 错误时，adapter 才移除该 id 并用完整 `items` 再请求一次。普通错误、未知错误和已开始输出的 stream 不做隐藏重试。需要严格保留 provider 原生 item 信息时，应使用强制 replay；缺少可重放 provider-native snapshot 时必须报错。

### 跨 provider replay 是否支持？

暂不支持。provider-native snapshot 只对原 provider/API family 有意义。长期可研究受限跨 provider replay，但必须先定义兼容性报告，明确哪些 item 可迁移、哪些字段会丢失、哪些语义需要用户确认。

### 同时支持 Responses API 与 Chat Completions API 的 provider 应如何适配？

应只适配 Responses API。Chat Completions API 可以作为迁移参考或 legacy provider 的实现参考，但不应为了兼容性在同一 provider adapter 中维护 Chat Completions 调用路径。

### provider-hosted tools 是否违反不自动执行工具的原则？

原则上不违反，但 provider-hosted/remote tools 的执行责任、生命周期和审计语义差异较大，当前暂不进入通用 core。v0.3 只抽象用户代码执行的 function tool；hosted/remote tools 留待后续专项设计。

### 文件资源为什么需要独立 API？

因为文件有上传、状态、过期、预处理、删除和复用等生命周期语义。把文件只作为 message 中的 URL 或字符串会丢失这些语义，也难以支持大文件、多次复用和 provider 预处理。

### 图片/视频生成为什么不直接复用 generation？

图片/视频生成包含 artifact、分辨率、输出格式、duration、异步任务、流式局部产物等语义，与 LLM generation 的多轮推理上下文不同。它应作为 media generation API 家族存在。

## 参考资料

- [provider-capability-integration.CN.md](provider-capability-integration.CN.md)
- [provider-native-replay.CN.md](provider-native-replay.CN.md)
- [volengine/INDEX.md](../3rds/volengine/INDEX.md)
- [response_api.md](../3rds/volengine/response_api.md)
- [file_api.md](../3rds/volengine/file_api.md)
- [embeding.md](../3rds/volengine/embeding.md)
- [image_generation.md](../3rds/volengine/image_generation.md)
- [video_generation.md](../3rds/volengine/video_generation.md)
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)
- [OpenAI Responses API migration guide](https://developers.openai.com/api/docs/guides/migrate-to-responses)
- [OpenAI streaming responses](https://platform.openai.com/docs/api-reference/streaming)
- [Anthropic Messages streaming](https://platform.claude.com/docs/en/build-with-claude/streaming)
- [Anthropic tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
- [Gemini API embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
- [Vertex AI multimodal embeddings API](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/multimodal-embeddings-api)
