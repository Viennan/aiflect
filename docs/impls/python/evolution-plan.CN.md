# Python 版本演进方案

状态：演进计划
日期：2026-05-06
最近更新：2026-05-29

## 背景

Python 是 `vatbrain` 的参考实现语言。第一阶段已经完成基础包结构、core 基础模型、OpenAI provider client、OpenAI Responses API generation/streaming、function tool 映射、text embedding、usage 和 capability 基础表达。

后续演进需要吸收高层设计和 provider 能力整合设计中的新边界：

- generation、embedding、resource/file、media generation 是独立 API 家族。
- 对同时支持 Responses API 与 Chat Completions API 的 provider，generation adapter 仅使用 Responses API。
- provider-side state/cache/previous response 只作为优化 hint，不改变 Full-context First。
- v0.3 先只抽象 user-executed function tools；provider-hosted tools、remote tools、MCP tools 后续再设计。
- reasoning 既是配置，也是可能出现的输出 item。
- 文件资源具有独立生命周期。
- embedding 需要支持多模态输入、instructions、dense/sparse vectors。

参考设计：

- [design/high-level-design.CN.md](design/high-level-design.CN.md)
- [design/provider-capability-integration.CN.md](design/provider-capability-integration.CN.md)
- [impls/python/openai-adapter.CN.md](impls/python/openai-adapter.CN.md)
- [3rds/volengine/INDEX.md](3rds/volengine/INDEX.md)

## 当前实现阶段

截至 2026-05-29，Python 参考实现已完成 v0.5：

- 包结构、core 基础模型、OpenAI provider client 已稳定。
- v0.2 OpenAI Responses contract hardening 已完成。
- v0.3 Core API Family Expansion 已完成，见 [impls/python/v0.3-core-api-family-expansion.CN.md](impls/python/v0.3-core-api-family-expansion.CN.md)。
- OpenAI adapter 已支持 Responses generation/streaming、JSON Schema structured output、function/custom tools、remote context hint、provider-native replay、text embedding 与 capability。
- Python Pydantic structured output helper 已完成，见 [impls/python/pydantic-structured-output.CN.md](impls/python/pydantic-structured-output.CN.md)。
- v0.4 Volcengine adapter MVP 已完成，见 [impls/python/volcengine-adapter.CN.md](impls/python/volcengine-adapter.CN.md)。
- Volcengine adapter 已支持 Ark SDK-only Responses generation/streaming、Files API、多模态 embedding、function tools、reasoning、structured output、provider-native replay 与 remote context fallback。
- v0.5 Media Generation 已完成，见 [impls/python/v0.5-media-generation.CN.md](impls/python/v0.5-media-generation.CN.md)。
- OpenAI adapter 已支持直接 Images API 图片生成、参考图生成与图片流式生成。
- Volcengine adapter 已支持 Ark Images API 图片生成、参考图生成、图片流式生成，以及 Ark Content Generation 视频任务创建、查询与轮询。
- 默认单元测试不依赖真实 provider API。

当前主要缺口已经从 core 抽象建设、第二 provider MVP 与基础 media generation 转向稳定化：

- Provider-hosted tools、Remote MCP、Web Search helper、Image Process helper 与 Knowledge Search helper 暂不做，历史 v0.5 hosted tools 规划已过期。
- Provider capability matrix、可选真实 API integration tests、migration notes 与错误处理 cookbook 仍需完善。
- 跨 provider replay 暂不支持，长期 TODO 是 compatibility report。

## 演进原则

### 先稳定 core，再扩 provider

新增 provider 前，应先让 core 模型能表达目标 provider 的必要语义。避免在 provider adapter 内堆积 provider-specific 临时结构，导致后续无法跨 provider 复用。

### Responses-only for dual API providers

OpenAI、火山方舟等同时支持 Responses API 与 Chat Completions API 的 provider，Python adapter 的 generation 实现只使用 Responses API。Chat Completions API 不作为兼容 fallback 或平行实现路径。

如果未来某个 provider 不提供 Responses 风格 API，才允许将 Chat/Completions 风格 API 映射到 `vatbrain` generation 模型。

### 保持 Full-context First

即使 provider 支持 `previous_response_id`、stored response、context cache 或 conversation，Python API 的推荐编程模型仍是用户传入完整语义上下文。

provider-side state 通过 `RemoteContextHint` 或 `provider_options` 的明确字段表达，仅作为优化提示。v0.3 的 `RemoteContextHint` 暂不表达 provider conversation 持久化上下文，也暂不表达 cache policy 或远端过期时间。

当使用 `previous_response_id` 优化请求时，用户仍传入完整 `items`。如果 provider response 已覆盖其中的历史前缀，应通过 `RemoteContextHint.covered_item_count` 显式说明覆盖范围；adapter 才能在 provider 请求层只发送追加 suffix。覆盖范围缺失时不得猜测 history/append 边界。

`RemoteContextHint.store=None` 表示不显式指定本轮 response 的存储策略，依赖 provider 默认行为。使用某个 `previous_response_id` 时，需要保证被引用 response 在生成时已开启存储；本轮 `store=True` 只影响本轮 response 未来是否适合作为 previous response 被引用。

当 `previous_response_id` 或 provider-side context 失效时，Python client 不应默认静默重试。v0.3 已提供显式 `ReplayPolicy`：用户可以选择仅抛错、移除失效 remote context 后用完整 `items` 重放，或要求强制 provider-native replay。完整设计见 [design/provider-native-replay.CN.md](design/provider-native-replay.CN.md)。

### 小步发布，测试闭环

每个阶段都应具备单元测试和 mapping fixture 测试。真实 API integration test 可以作为可选测试层，不进入默认 CI。

### 文档与行为同步

任何 public API、用户可见行为或编程模型变化，都需要同步更新 `docs/user/python` 与 `docs/impls/python/STATUS.md`。

## 版本路线

### v0.2：Responses contract hardening

状态：已完成。
目标：巩固 OpenAI adapter，稳定第一阶段 public API，避免在 core 扩展前留下 provider 合约债务。

#### 范围

- 修正 OpenAI Responses API 参数映射，特别是 streaming options 与当前 SDK 类型的契合度。
- 扩充 OpenAI streaming event 映射：
  - response lifecycle。
  - output item lifecycle。
  - content part lifecycle。
  - text delta/done。
  - function call arguments delta/done。
  - reasoning/summary 事件的 raw passthrough 或初步 normalized event。
  - failed/incomplete/error。
- 增加 stream accumulator helper，用于从事件流重建 `GenerationResponse`。
- 增强 structured output 映射，明确 `ResponseFormat` 的 JSON schema 结构。
- 增强 provider error mapping，至少区分 request error、response mapping error、unsupported capability。
- 调整 `openai` 依赖下限到实际验证过的 Responses API SDK 范围。

#### 非范围

- 不新增 Volcengine adapter。
- 不实现 media generation。
- 不改变 `OpenAIClient.generate()` 的基本调用方式。

#### 主要文件

```text
python/whero/vatbrain/core/generation.py
python/whero/vatbrain/core/errors.py
python/whero/vatbrain/providers/openai/mapper.py
python/whero/vatbrain/providers/openai/stream.py
python/whero/vatbrain/providers/openai/client.py
python/tests/unit/test_openai_*.py
```

#### 验证

- `python/.venv/bin/python -m pytest`
- 新增 OpenAI Responses create params fixture tests。
- 新增 OpenAI stream event fixture tests。

### v0.3：Core API family expansion

状态：已完成。
目标：让 Python core 能表达 provider 能力整合设计中的核心语义，为 Volcengine adapter 做准备。

#### 范围

##### Items

扩展 `core.items`：

```text
PartKind
- text
- image
- audio
- video
- file

ItemKind
- message
- function_call
- function_result
- reasoning
```

新增：

- `AudioPart`
- `VideoPart`
- `FilePart`
- `ReasoningItem`
- 可选 `ArtifactPart`，若 media generation 在同阶段进入 core。

`FilePart` 应支持：

- provider file id。
- URL。
- base64/data URL。
- local path metadata。
- MIME type。
- media type。
- provider 标识。

本阶段只定义模型，不默认执行本地文件上传。

##### Generation

扩展 `core.generation`：

- `RemoteContextHint`
- `ReplayPolicy` 与 provider-native replay 策略
- `ReasoningConfig.mode`
- 更明确的 `ReasoningConfig.effort`
- `ResponseFormat` 的 JSON schema name/description/schema/strict
- stream event metadata 字段增强

Python 语言层可以增加 Pydantic structured output 便捷层，作为 `ResponseFormat` 的 schema 生成与最终响应解析 helper；该能力不改变 core 的 JSON Schema-only 原则，也不恢复 JSON mode 兼容。方案见 [impls/python/pydantic-structured-output.CN.md](impls/python/pydantic-structured-output.CN.md)。

##### Embeddings

扩展 `core.embeddings`：

- `EmbeddingRequest.instructions`
- `SparseEmbedding`
- `EmbeddingVector.dense`
- `EmbeddingVector.sparse`
- modality-aware usage metadata

保持现有 text embedding 用法兼容：

```python
client.embed(model="text-embedding-3-small", inputs=["hello"])
```

##### Resources

新增 `core.resources`：

```text
FileUploadRequest
FileResource
FileStatus
FilePreprocessConfig
```

`FilePreprocessConfig` 仅保留 `video_fps` 与 `provider_options`，避免把单一 provider 的 OCR、图片细节或切片策略提前固化进 core。
`FilePurpose` 已从 core 中移除；火山方舟 `purpose` 现阶段主要是 Files API 查询/上传的 provider-native 选项，尚不足以成为 vatbrain 通用文件资源语义。

##### Media

新增 `core.media` 的最小模型：

```text
MediaArtifact
ImageGenerationRequest
ImageGenerationResponse
ImageGenerationStreamEvent
MediaGenerationTask
TaskStatus
```

本阶段可以只定义模型和测试，不接入 provider。

##### Tools

扩展 `core.tools`：

- `ToolExecutionOwner`: 当前仅 `user`。
- `FunctionToolSpec`，保留现有 `ToolSpec` 的兼容别名。
- `FunctionToolType(function | custom)`，其中 `custom` 表达 raw string input 工具，OpenAI adapter 映射为 custom tool。
- 暂不新增 `HostedToolSpec`、`RemoteToolSpec` 或 `MCPToolSpec`。

##### Capabilities

将 capability 从扁平字段逐步演进到 API family 结构：

```text
GenerationCapability
EmbeddingCapability
ResourceCapability
MediaGenerationCapability
ToolCapability
AdapterCapability
ModelCapability
```

`GenerationCapability` 应包含 provider/adapter 支持的 reasoning effort 字符串集合；`ModelCapability.supported_reasoning_efforts` 用于表达具体 model 的更窄集合或用户覆写。

保留第一阶段字段的兼容属性或迁移说明，避免立即破坏 OpenAI adapter。

#### 非范围

- 不要求 OpenAI adapter 立刻支持所有新增 part。
- 不实现 Volcengine API 调用。
- 不实现自动工具执行。
- 不实现 response id 失效后的自动 retry/fallback；provider-native replay 基础能力先服务 OpenAI 同 provider 重放。

#### 主要文件

```text
python/whero/vatbrain/core/items.py
python/whero/vatbrain/core/generation.py
python/whero/vatbrain/core/embeddings.py
python/whero/vatbrain/core/resources.py
python/whero/vatbrain/core/media.py
python/whero/vatbrain/core/tools.py
python/whero/vatbrain/core/capabilities.py
python/whero/vatbrain/__init__.py
python/tests/unit/test_*.py
```

#### 验证

- core dataclass construction tests。
- backward compatibility tests for existing OpenAI usage。
- embedding dense/sparse shape tests。
- capability unknown/source/reliability tests。

### v0.4：Volcengine adapter MVP

状态：已完成。
目标：实现第二个 provider adapter，用火山方舟验证 Python core 的跨厂商表达能力。

详细实现方案见 [impls/python/volcengine-adapter.CN.md](impls/python/volcengine-adapter.CN.md)。本节保留 v0.4 的阶段边界、关键设计决策和验收口径，具体 mapper、Ark SDK 调用面、模块职责与测试矩阵以独立方案为准。

#### 设计输入

v0.4 方案基于以下知识库资料：

- [impls/python/v0.3-core-api-family-expansion.CN.md](impls/python/v0.3-core-api-family-expansion.CN.md)：当前 Python core 与 OpenAI adapter 基线。
- [design/provider-capability-integration.CN.md](design/provider-capability-integration.CN.md)：API family、provider-side state、资源、embedding 与 hosted tools 边界。
- [design/provider-native-replay.CN.md](design/provider-native-replay.CN.md)：provider-native snapshot、`ReplayPolicy` 与 remote context fallback。
- [3rds/volengine/response_api_text_gen.md](3rds/volengine/response_api_text_gen.md)：Responses API 文本生成、上下文、streaming、store/cache。
- [3rds/volengine/response_api_multimodal_understanding.md](3rds/volengine/response_api_multimodal_understanding.md)：Responses API 图片、视频、文档理解与 Files API 引用。
- [3rds/volengine/response_api_reasoning.md](3rds/volengine/response_api_reasoning.md)：`thinking.type`、reasoning summary 与 `reasoning.effort`。
- [3rds/volengine/response_api_tool_calling.md](3rds/volengine/response_api_tool_calling.md)：Responses API function calling 与 provider-hosted tools 对照。

#### Provider identity

- provider id：`volcengine`
- client：`VolcengineClient`
- API key 初始化：用户必须显式传入 LLM `api_key` / `ClientConfig.api_key`；adapter 不读取环境变量作为隐式 fallback。
- 默认 base URL：`https://ark.cn-beijing.volces.com/api/v3`
- provider-native snapshot key：`volcengine.responses`
- 底层使用 Ark SDK 的 LLM api key 初始化语义，adapter 内部以 `SecretString` 保存 API key。

#### 调用面原则

- generation 仅使用 Responses API。
- 不引入 Chat Completions API 调用路径。
- Chat API 资料只作为参数语义和迁移对照。
- 仅使用火山方舟 Ark SDK，即 `volcenginesdkarkruntime`、`Ark` / `AsyncArk` 及其原生类型/方法。
- 不使用火山方舟 OpenAI-compatible SDK surface，不把 OpenAI SDK 配置为火山方舟 base URL，也不引入 direct HTTP fallback。
- 本地文件路径不会在 generation/embedding mapper 中隐式上传；上传必须通过 file API 显式发生。

#### 范围

##### Generation

支持：

- text input。
- image input。
- video input by URL/base64/file id。
- `ReasoningConfig.mode` -> `thinking.type`。
- `ReasoningConfig.effort` -> `reasoning.effort`。
- function tools。
- function call output。
- `RemoteContextHint.previous_response_id`。
- `RemoteContextHint.store` -> `store`。
- cache/caching 暂不进入 `RemoteContextHint`，需要时通过 `provider_options` 透传。
- structured output via `text.format`。
- usage mapping。
- provider-native snapshot：对 provider response output 中可重放的 message、function call、function call output、reasoning item 保存原生 payload。
- `provider_options` 透传 `caching`、`instructions`、`include`、`service_tier`、`expire_at` 等尚未进入通用 core 的火山方舟参数。
- 停止序列不进入 `GenerationConfig`；如目标 API 支持 provider-native stop/stop_sequences，应由用户通过 `provider_options` 显式传递。

##### Streaming

支持 Responses API streaming：

- response created / in_progress。
- text delta/done。
- reasoning summary delta/done。
- reasoning summary part added/done。
- output item added/done。
- function call arguments delta/done。
- response completed/failed/incomplete/error。
- unknown event raw passthrough。

##### Files

支持：

- `upload_file`
- `retrieve_file`
- `list_files`
- `delete_file`
- 可选 `wait_for_file_processing`

文件预处理配置支持 video fps 与 raw provider_options。火山方舟 `purpose` 不进入 core model，由 Volcengine adapter 作为 provider-native 字符串参数处理，默认 `user_data`，返回的原始值保存在 `FileResource.metadata["raw_purpose"]`。

##### Embedding

支持火山多模态 embedding：

- text。
- image URL/data URL。
- video URL/data URL。
- instructions。
- dimensions。
- encoding_format。
- sparse embedding。
- usage mapping。
- v0.4 每次 request 只提交一个 `EmbeddingInput`；该 input 内部可混合 text/image/video parts，与 Ark API 一次返回一个向量的语义保持一致。

##### Capabilities

声明 adapter capability：

- generation。
- stream generation。
- function tools。
- provider-side state/cache hints。
- file resources。
- multimodal embedding。
- sparse embedding。
- usage mapping。
- async 调用能力，前提是 Ark SDK backend 支持。

model capability 仍默认 unknown，允许用户 overrides。

##### Replay

Provider-native replay 基础能力已优先在 OpenAI adapter 上实现。v0.4 同步支持 Volcengine Responses API 的最小 replay 面：

- 已新增 `ProviderItemSnapshot`，保存同 provider/API family 的原始 item payload。
- 已新增 `ReplayPolicy`，支持 `normalized_only`、`prefer_provider_native`、`require_provider_native`。
- 已支持 `require_provider_native` 作为强制 replay 选项，缺少可重放 snapshot 时抛错。
- 已支持 `on_remote_context_invalid="replay_without_remote_context"`；默认 `raise`，只有用户显式启用时才清除失效 `previous_response_id` 并用完整 `items` 重试一次。
- 已新增 `RemoteContextHint.covered_item_count`，用于表达 `previous_response_id` 覆盖完整 `items` 的前缀长度。
- Volcengine provider 应支持 previous response 差分传输：存在 `previous_response_id` 且覆盖边界明确时发送 suffix，失效 fallback 重新构造完整 input。
- Volcengine Responses output item 原生字段通过 snapshot 保真；仅具备跨 provider 语义的字段才进入 normalized core。
- 跨 provider replay 暂不支持，记录为长期 TODO。

##### Structured Output

Volcengine Responses API 的 structured output 映射为 `text.format` JSON Schema。v0.4 只支持 `ResponseFormat` 的 JSON Schema-only 编程模型，不恢复 JSON mode，也不为 Chat API 的 `response_format` 建立独立路径。

##### Error Mapping

Volcengine adapter 应沿用 `ProviderRequestError` / `ProviderResponseMappingError`：

- Ark SDK 调用失败包装为 `ProviderRequestError(provider="volcengine", operation=...)`。
- provider response 缺字段、未知结构无法映射时包装为 `ProviderResponseMappingError`。
- previous response/context 失效判断至少覆盖错误参数、错误码和错误消息中出现的 `previous_response_id`、previous response expired、context expired/invalid 等信息。

#### 非范围

- 不支持 Chat Completions API。
- 不支持跨 provider replay。
- 不自动执行 function tools。
- 不自动 provider routing。
- 不自动上传本地文件，除非用户显式调用 file API。
- 不支持 image/video generation；留给 v0.5。
- 不支持 hosted tools 的高级封装；可通过 provider_options 临时透传。
- 不将 `caching`、`instructions`、`expire_at` 提升为通用 core 字段。
- 不引入 provider conversation 持久化上下文抽象。

#### 目录结构

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

测试：

```text
python/tests/unit/test_volcengine_client.py
python/tests/unit/test_volcengine_generation_mapper.py
python/tests/unit/test_volcengine_stream_mapper.py
python/tests/unit/test_volcengine_files.py
python/tests/unit/test_volcengine_embeddings.py
```

#### SDK 选择

固定策略：

- Responses generation/streaming：使用 Ark / AsyncArk SDK 的 `responses.create` 及其原生 request/response/event 类型，以 fixture test 锁定实际参数。
- Files API：使用 Ark / AsyncArk SDK 的 files surface；必须支持 upload/retrieve/list/delete。若 wait helper 不稳定，adapter 可以基于 Ark SDK retrieve/list 自行轮询。
- Multimodal embedding：使用 Ark SDK 暴露的多模态 embedding surface。
- 若 Ark SDK 当前版本无法表达某个文档字段，应先验证 Ark SDK 原生扩展点；仍无法表达时标记为暂不支持或暂停确认，不通过 OpenAI-compatible SDK 或 direct HTTP 绕过。

依赖策略：

- 将 Volcengine Ark SDK 作为 optional dependency：`volcengine-python-sdk[ark]>=5.0.30,<6`，安装 extra 为 `.[volcengine]`。
- core 和 OpenAI adapter 不依赖 Volcengine SDK。

#### 实施步骤

1. 新增 optional dependency 与 provider 包骨架，不改变 OpenAI adapter 行为。
2. 实现 `capabilities.py` 与 `VolcengineClient` 初始化、sync/async lazy client、API key/base URL 解析。
3. 实现 Responses mapper：text/image/video/file/function/reasoning/structured output/usage/remote context。
4. 实现 streaming mapper 与 accumulator fixture，覆盖 text、reasoning summary、function call、completed/failed/unknown event。
5. 实现 Files API：upload/retrieve/list/delete/wait，覆盖视频 fps 预处理。
6. 实现 multimodal embedding mapper，覆盖 text/image/video、instructions、dense/sparse vector 与 usage。
7. 补充 provider-native snapshot、`ReplayPolicy` 与 remote context fallback 测试。
8. 更新用户文档和 STATUS，新增 `docs/user/python/volcengine-quickstart.CN.md`。

每一步应保持默认 `python/.venv/bin/python -m pytest` 可通过。AI 协助下，mapper 与 fixture test 可以小步并行推进；真正需要人工核验的是 Ark SDK 合约和真实 API 差异。

#### 验收标准

- `VolcengineClient.generate()` / `agenerate()` 支持 Responses API 文本、多模态输入、function tool、structured output、reasoning 与 usage 映射。
- `VolcengineClient.stream_generate()` / `astream_generate()` 输出标准化 `GenerationStreamEvent`，并保留 `raw_event`。
- `VolcengineClient.upload_file()` / retrieve/list/delete/wait 可操作 provider 文件资源，且不会由 generation 隐式触发上传。
- `VolcengineClient.embed()` / `aembed()` 支持多模态输入、instructions、dense/sparse 结果映射。
- adapter capability 与 model capability unknown/override 语义与 OpenAI adapter 一致。
- 默认测试不依赖真实 API；可选 integration tests 通过环境变量显式启用。

#### 实现结果

v0.4 已落地以下文件：

```text
python/whero/vatbrain/providers/volcengine/__init__.py
python/whero/vatbrain/providers/volcengine/capabilities.py
python/whero/vatbrain/providers/volcengine/client.py
python/whero/vatbrain/providers/volcengine/mapper.py
python/whero/vatbrain/providers/volcengine/stream.py
python/whero/vatbrain/providers/volcengine/files.py
python/whero/vatbrain/providers/volcengine/embeddings.py
python/tests/unit/test_volcengine_client.py
python/tests/unit/test_volcengine_generation_mapper.py
python/tests/unit/test_volcengine_stream_mapper.py
python/tests/unit/test_volcengine_files.py
python/tests/unit/test_volcengine_embeddings.py
```

实现中确认 PyPI 安装包名为 `volcengine-python-sdk[ark]`，导入模块为 `volcenginesdkarkruntime`。所有 provider 调用均通过 Ark SDK 原生 `Ark` / `AsyncArk` 客户端完成。

验证：

```bash
cd python
.venv/bin/python -m pytest
```

v0.4 完成时结果：`123 passed`。

### v0.5：Media generation

状态：已完成。
目标：覆盖 OpenAI Images API 图片生成、Volcengine Ark 图片生成和 Volcengine 视频生成，并用两个 provider 的接口交集完善 media generation core model。OpenAI adapter 负责屏蔽 `images.generate` 与 `images.edit` 的 API 分裂，用户侧统一使用 `ImageGenerationRequest`。详细方案与实现记录见 [impls/python/v0.5-media-generation.CN.md](impls/python/v0.5-media-generation.CN.md)。

#### 范围

##### Image generation

支持：

- text-to-image。
- image-to-image/reference image。
- OpenAI 仅覆盖直接 Images API，不覆盖通过 GPT/Responses 内置 image generation tool 的间接路径。
- output format。
- response format。
- `background` 顶层参数作为 provider capability 处理；OpenAI 支持 `auto`、`transparent`、`opaque`，Volcengine 当前不支持并忽略。
- 分辨率/长宽比暂不进入 `ImageGenerationRequest` normalized 字段，图片生成默认采用 auto 模式，由模型从 prompt 推断；provider-native 控制可通过 `provider_options` 显式传递。
- `watermark` 顶层参数，默认要求添加 AI 水印；provider 或模型没有可控水印能力时忽略。
- stream events。
- partial image/artifact events。
- usage mapping。

##### Video generation

支持：

- create task。
- retrieve task。
- poll helper。
- task status mapping。
- artifact mapping。
- error mapping。
- `watermark` 顶层参数，默认要求添加 AI 水印；provider 或模型没有可控水印能力时忽略。

#### 非范围

- 不做 hosted tools / Remote MCP / Web Search helper / Image Process helper / Knowledge Search helper。
- 不复用 `ToolSpec` 表达 media generation hosted capability。
- 不通过 OpenAI GPT/Responses 模型内置工具间接生成图片。
- 不覆盖 OpenAI image variation API。
- 不做图像/视频编辑的所有 provider 专有高级参数标准化。
- 不内置媒体文件下载、保存或转码。
- 不自动上传本地参考文件。
- 不使用 Volcengine OpenAI-compatible SDK surface 或 direct HTTP fallback。

#### 实现结果

Core 已完成：

- `ImageGenerationRequest` 不包含 `tools`。
- `VideoGenerationRequest` 已进入 core media model，并从 `whero.vatbrain` 与 `whero.vatbrain.core` 导出。
- `ImageGenerationRequest` 与 `VideoGenerationRequest` 提供 `watermark=True` 默认值。
- `MediaGenerationCapability` 声明图片背景控制能力与支持枚举。
- `MediaArtifact`、`ImageGenerationResponse`、`ImageGenerationStreamEvent` 与 `MediaGenerationTask` 继续作为 media generation 统一结果模型。

OpenAI adapter 已完成：

- `OpenAIClient.generate_image()` / `agenerate_image()`。
- `OpenAIClient.stream_generate_image()` / `astream_generate_image()`。
- 无参考图时调用 OpenAI SDK `images.generate`。
- 存在 `ImagePart(data=...)` 参考图时调用 OpenAI SDK `images.edit`。
- OpenAI adapter 映射 normalized `background`，capability 声明支持 `auto`、`transparent`、`opaque`。
- OpenAI adapter 忽略 normalized `watermark`，不向 Images API 发送该字段。
- 不通过 Responses API hosted image generation tool 间接生成图片。
- 不隐式下载 `ImagePart(url=...)` 作为 OpenAI edit 输入。

Volcengine adapter 已完成：

- `VolcengineClient.generate_image()` / `agenerate_image()`。
- `VolcengineClient.stream_generate_image()` / `astream_generate_image()`。
- 图片生成严格使用 Ark SDK 原生 `images.generate`。
- 图片生成将 normalized `watermark` 映射为 Ark `watermark`。
- 图片生成将 normalized `count` 映射为 Ark `sequential_image_generation_options.max_images`。
- 图片生成忽略 `background` 与 `quality`，因为 Ark Images API 当前无等价字段；capability 声明背景控制不支持。
- `VolcengineClient.create_video_generation_task()` / `acreate_video_generation_task()`。
- `VolcengineClient.get_video_generation_task()` / `aget_video_generation_task()`。
- `VolcengineClient.wait_for_video_generation_task()` / `await_video_generation_task()`。
- 视频任务严格使用 Ark SDK 原生 `content_generation.tasks.create/get`。
- 视频任务创建将 normalized `watermark` 映射为 Ark `watermark`。

验证：

```bash
cd python
.venv/bin/python -m pytest
```

当前结果：`147 passed`。

### v0.6：Stabilization and compatibility

目标：稳定 public API，完善文档和测试策略。

范围：

- API reference。
- migration notes。
- provider capability matrix。
- optional integration tests。
- error hierarchy refinement。
- type-check/lint 可选引入。
- deprecation policy。

## 测试策略

### Unit tests

默认测试层，不调用真实 provider：

- core model construction。
- request mapper。
- response mapper。
- stream event mapper。
- error wrapping。
- capability unknown/source/reliability。

### Fixture tests

使用本地 JSON/dict fixture 模拟 provider 响应：

- OpenAI Responses events。
- Volcengine Responses events。
- Volcengine Files responses。
- Volcengine multimodal embeddings responses。
- media generation task responses。

### Optional integration tests

真实 API 测试必须默认关闭，通过环境变量显式启用：

```text
ENV_VATBRAIN_RUN_INTEGRATION_TESTS=1
ENV_VATBRAIN_OPENAI_API_KEY=...
ENV_VATBRAIN_VOLCENGINE_API_KEY=...
```

integration tests 不应影响默认 `pytest`。

## 文档同步计划

每个阶段完成时同步更新：

- [impls/python/STATUS.md](impls/python/STATUS.md)
- [user/python/quickstart.CN.md](user/python/quickstart.CN.md)
- [user/python/STATUS.md](user/python/STATUS.md)
- [INDEX.md](INDEX.md)

Volcengine adapter 已补齐：

```text
docs/user/python/volcengine-quickstart.CN.md
```

## 风险与决策点

### Core 兼容风险

`Item`、`EmbeddingVector`、`AdapterCapability` 扩展可能影响现有 OpenAI adapter。应保留兼容构造方式和旧字段读取方式，至少维持 v0.1 用户示例可运行。

### Ark SDK 表面差异

v0.4 只使用 Ark SDK surface。实现前需要针对每个 API family 验证 Ark SDK 的具体方法、参数与事件类型，并用 fixture test 锁定映射。generation 不应退回 Chat Completions API，也不应使用 OpenAI-compatible SDK surface。

### Provider-specific 参数边界

如 image process、knowledge search、MCP、video generation 高级参数，短期可以通过 provider-specific model 或 provider_options 表达。只有具备跨 provider 语义时才进入 core 通用字段。

### Provider-native replay 与通用抽象边界

OpenAI assistant message `phase` 暴露了一个重要边界：部分 provider 原生 item 字段会影响同 provider follow-up/replay 行为，但不应该为每个字段都扩展 provider-specific mapper 分支。后续实现应优先保存 provider-native snapshot，用 replay policy 决定是否使用原始 payload。具备跨 provider 潜力的字段，例如 assistant output phase，可以再提升为通用抽象。

跨 provider replay 暂不支持。长期 TODO 是提供 replay compatibility report，而不是直接把 provider-native payload 转换给另一个 provider。

### 自动上传本地文件

火山方舟 SDK 支持部分本地路径便捷上传，但 `vatbrain` 不应默认隐式上传。若实现便捷 API，必须是显式方法或显式 `auto_upload=True`。

### AI 协助下的实施成本

在 AI 协助下，core dataclass、mapper、fixture test 和文档同步的单位成本较低，适合小步快跑。真正需要谨慎投入的是 provider SDK 合约验证、真实 API 行为差异、streaming event 完整性和 public API 稳定性。

## 建议近期任务

1. 为 OpenAI / Volcengine 建立 provider capability matrix，区分 adapter builtin、provider docs 与用户覆写。
2. 设计 provider-hosted tools / Remote MCP 的执行责任模型，避免与 user-executed function tools 混淆。
3. 增加默认关闭的真实 API integration test 约定，验证 Ark SDK 与文档之间的运行时差异。
4. 梳理 v0.5 后的 migration notes 和跨 provider 编程示例。
5. 继续评估 provider-specific media 高级参数，只有具备跨 provider 语义时再提升为 core 通用字段。
