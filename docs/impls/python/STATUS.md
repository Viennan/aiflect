# Python 实现状态

状态：v0.6 Anthropic adapter、Anthropic structured output 与 remote context cache 策略升级已完成
日期：2026-05-05
最近更新：2026-06-07

## 定位

本文件描述 Python 参考实现的当前能力基线、暂不实现项、后续规划和验证方式。它不维护需求生命周期或需求级进度；相关需求状态见 [requirements/STATUS.md](../../requirements/STATUS.md)。

## 当前基线

Python 是 `vatbrain` 的参考实现语言。当前实现已完成 v0.6 Anthropic adapter、Anthropic structured output，并完成 RemoteContextHint/cache 策略升级：通用 API 使用 `enable_cache/new_items_start_index`，response-style provider 自动管理 response id 与失效 refresh，Anthropic provider 保持 full messages automatic caching。

核心文档：

- [high-level-design.CN.md](../../design/high-level-design.CN.md)
- [provider-capability-integration.CN.md](../../design/provider-capability-integration.CN.md)
- [provider-native-replay.CN.md](../../design/provider-native-replay.CN.md)
- [REQ-2026-05-python-reference-implementation-roadmap.CN.md](../../requirements/REQ-2026-05-python-reference-implementation-roadmap.CN.md)
- [volcengine-adapter.CN.md](volcengine-adapter.CN.md)
- [anthropic-adapter.CN.md](anthropic-adapter.CN.md)
- [remote-context-cache-strategy.CN.md](remote-context-cache-strategy.CN.md)
- [v0.5-media-generation.CN.md](v0.5-media-generation.CN.md)
- [v0.2-responses-contract-hardening.CN.md](v0.2-responses-contract-hardening.CN.md)
- [v0.3-core-api-family-expansion.CN.md](v0.3-core-api-family-expansion.CN.md)
- [impls/python/pydantic-structured-output.CN.md](pydantic-structured-output.CN.md)

## 已实现

### 包与基础设施

- Python 包脚手架与 `pyproject.toml`。
- 通用 client 初始化配置：`ClientConfig`。
- `SecretString`：provider adapter 用于存储 LLM API key。
- OpenAI / Volcengine / Anthropic adapter 不再从环境变量自动读取 API key；需要初始化时显式传入，或通过 `ClientConfig.api_key` 提供。
- 默认单元测试不依赖真实 provider API。

### Core

- `core.items`：
  - `MessageItem`、`TextPart`、`ImagePart`、`AudioPart`、`VideoPart`、`FilePart`。
  - `FunctionCallItem`、`FunctionResultItem`。
  - `ReasoningItem`。
  - `AssistantMessagePhase`。
  - `ProviderItemSnapshot` 与 lookup helper。
- `core.generation`：
  - `GenerationRequest`、`GenerationResponse`、`GenerationConfig`。
  - `ResponseFormat`，仅支持 JSON Schema structured output。
  - `ReasoningConfig`。
  - `RemoteContextHint(enable_cache, new_items_start_index)`。
  - `ReplayPolicy`、`ReplayMode`。
  - `GenerationStreamEvent` 与 `GenerationStreamAccumulator`。
- `core.embeddings`：
  - `EmbeddingInput`、`EmbeddingRequest`、`EmbeddingResponse`。
  - `EmbeddingVector.dense/sparse` 与兼容字段 `embedding`。
  - `SparseEmbedding`。
- `core.resources`：
  - `FileUploadRequest`、`FileResource`、`FileStatus`、`FilePreprocessConfig(video_fps/provider_options)`。
- `core.media`：
  - `MediaArtifact`、`ImageGenerationRequest`、`ImageGenerationResponse`、`ImageGenerationStreamEvent`、`MediaGenerationTask`。
  - `ImageGenerationRequest` 不包含 `tools`；media generation 不复用 generation function tool 模型。
- `core.tools`：
  - `FunctionToolSpec` / `ToolSpec`。
  - `FunctionToolType(function | custom)`。
  - `ToolChoice` 与 `ToolExecutionOwner(user)`。
- `core.capabilities`：
  - API family capability。
  - `CapabilityValue` 来源与可靠性。
  - adapter/model capability。
  - model-level `supports_structured_output`。
  - provider/model supported reasoning efforts 字段。
- `core.errors` 与 `core.usage`：
  - provider request/response mapping error 诊断字段。
  - normalized usage 与 raw usage。

### OpenAI Adapter

- Responses API generation。
- Responses API streaming。
- Async generation / streaming。
- OpenAI Responses API 合约加固：
  - 不生成未验证的 `stream_options.include_usage`。
  - structured output 映射为 `text.format` JSON Schema。
  - 不兼容 JSON mode / `json_object`。
  - 覆盖 response、content part、text、function/custom tool、reasoning、incomplete、failed/error 与 unknown passthrough stream event。
  - `GenerationStreamAccumulator` 支持文本与 function/custom tool call 重建。
  - provider request / response mapping error 诊断字段。
- Function tool 映射。
- Custom tool 映射：
  - `ToolSpec(type="custom")` -> OpenAI custom tool。
  - `custom_tool_call` -> `FunctionCallItem(type="custom", input=...)`。
  - `FunctionResultItem(tool_type="custom")` -> `custom_tool_call_output`。
  - streaming 复用 tool call event，并用 `metadata["tool_type"]` 标记 custom。
- Provider-native replay：
  - response item 映射时保存 provider 原始 snapshot。
  - 同 provider/API family 重放时默认优先使用 snapshot。
  - 支持 `ReplayPolicy(mode="normalized_only")`。
  - 支持 `ReplayPolicy(mode="require_provider_native")`。
  - OpenAI assistant message `phase` 与通用 `AssistantMessagePhase` 互相映射。
- Remote context 差分传输：
  - 用户仍传完整 `items`。
  - `RemoteContextHint.new_items_start_index` 表达新增 item 的起始位置。
  - output item snapshot metadata 保存 parent response id。
  - 找到 anchor response id 时 optimized attempt 发送 suffix。
  - previous response 失效时自动 refresh 并重新构造完整 input。
- OpenAI text embeddings。
- OpenAI Images API：
  - `generate_image()` / `agenerate_image()`。
  - `stream_generate_image()` / `astream_generate_image()`。
  - 无参考图时调用 `images.generate`。
  - 存在 `ImagePart(data=...)` 参考图时调用 `images.edit`。
  - 不通过 Responses API hosted image generation tool 间接生成图片。
  - 不隐式下载 URL 参考图；OpenAI edit 路径要求显式图片内容。
  - `background` 映射到 OpenAI Images API，capability 声明支持 `auto`、`transparent`、`opaque`。
  - normalized `watermark` 被忽略，不发送给 OpenAI Images API。
- Adapter/model capability 查询与用户覆写。

### Pydantic Structured Output

- Optional helper：`whero-vatbrain[pydantic]`。
- `pydantic_output()` 从 Pydantic v2 type 生成 `ResponseFormat`。
- `PydanticOutputSpec.parse_text()` 与 `parse_response()`。
- `ParsedGenerationResponse.output_parsed`。
- `StructuredOutputParseError`。
- OpenAI、Volcengine 与 Anthropic client `generate_parsed()` / `agenerate_parsed()`。
- 默认 schema name 来自 type 名称，description 来自 type docstring，strict 为 `True`。

### Volcengine Adapter

- Provider package：`whero.vatbrain.providers.volcengine`。
- Optional dependency：`whero-vatbrain[volcengine]`，使用 `volcengine-python-sdk[ark]>=5.0.30,<6`。
- Client：`VolcengineClient`。
- LLM API key 必须在初始化时显式传入；adapter 内部以 `SecretString` 保存。
- 严格使用 Ark SDK 原生 surface：
  - `Ark` / `AsyncArk`。
  - `responses.create`。
  - `files.create/retrieve/list/delete/wait_for_processing`。
  - `multimodal_embeddings.create`。
  - `images.generate`。
  - `content_generation.tasks.create/get`。
- 未使用火山方舟 OpenAI-compatible SDK surface，未把 OpenAI SDK 配置为火山方舟 base URL，未引入 direct HTTP fallback。
- Responses generation：
  - text/image/video/file input。
  - JSON Schema structured output via `text.format`。
  - `ReasoningConfig.mode -> thinking.type`。
  - `ReasoningConfig.effort -> reasoning.effort`。
  - function tool / function call / function call output。
  - usage/cached/reasoning token mapping。
  - provider-native snapshot 与 same-provider replay。
  - `RemoteContextHint.enable_cache + new_items_start_index` 驱动的差分传输。
  - output item snapshot metadata 保存 parent response id。
  - previous response 失效时自动 full-context refresh。
- Responses streaming：
  - lifecycle、content part、text delta/done、function call arguments、reasoning summary、completed/incomplete/failed/error 与 unknown passthrough。
- Files API：
  - upload/retrieve/list/delete/wait。
  - 火山方舟 `purpose` 仅作为 Volcengine adapter 的 provider-native 字符串参数处理，默认 `user_data`。
  - video fps 预处理映射为 `preprocess_configs.video.fps`。
- Multimodal embedding：
  - text/image/video mixed input。
  - `instructions` 通过 Ark SDK `extra_body` 传递。
  - dimensions、encoding_format、dense/sparse vector 与 usage mapping。
  - `sparse_embedding` 仅允许纯文本输入；混合图片/视频时会抛 `UnsupportedCapabilityError`。
  - v0.4 每次 embedding request 只提交一个 `EmbeddingInput`，与 Ark 多模态接口“一次返回一个向量”的语义一致。
- Ark Images API：
  - `generate_image()` / `agenerate_image()`。
  - `stream_generate_image()` / `astream_generate_image()`。
  - text-to-image 与 reference image 均统一映射到 `Ark.images.generate`。
  - 支持 URL/base64 data 参考图、output_format、response_format 与 provider_options。
  - 图片分辨率/长宽比不作为 normalized `size` 字段暴露，默认由模型从 prompt 推断。
  - `watermark` 映射到 Ark `images.generate` 同名参数，默认 `True`。
  - `count` 映射到 Ark `sequential_image_generation_options.max_images`；`sequential_image_generation` 等组图开关通过 `provider_options` 传递。
  - `background` 与 `quality` 当前无 Ark Images API 等价字段，adapter 忽略，capability 声明背景控制不支持。
- Ark Content Generation 视频任务：
  - `create_video_generation_task()` / `acreate_video_generation_task()`。
  - `get_video_generation_task()` / `aget_video_generation_task()`。
  - `wait_for_video_generation_task()` / `await_video_generation_task()`。
  - 支持 text/image/video/audio reference content 的最小映射。
  - `watermark` 映射到 Ark task create 同名参数，默认 `True`。
  - 支持 task status、artifact、error 与 usage metadata 映射。
- Capability：
  - adapter capability 声明 generation/streaming/async/function tools/files/multimodal embedding/sparse embedding/media generation/usage。
  - model capability 默认 unknown，支持用户 overrides。

### Anthropic Adapter

- Provider package：`whero.vatbrain.providers.anthropic`。
- Optional dependency：`whero-vatbrain[anthropic]`，使用 `anthropic>=0.105.2,<1`。
- Client：`AnthropicClient`。
- API key 必须在初始化时显式传入；adapter 内部以 `SecretString` 保存。
- 严格使用官方 Anthropic SDK 原生 surface：
  - `Anthropic` / `AsyncAnthropic`。
  - `messages.create`。
- Messages generation：
  - text/image input。
  - JSON Schema structured output via `output_config.format`。
  - initial system/developer instruction prefix 映射为 Anthropic top-level `system`。
  - Anthropic Messages API 要求 `max_tokens`；通过 `GenerationConfig.max_output_tokens` 或 provider-native `provider_options["max_tokens"]` 提供。
  - user-executed function tools。
  - `tool_use` -> `FunctionCallItem`。
  - `FunctionResultItem` -> `tool_result`。
  - `thinking` / `redacted_thinking` content block 尽量映射为 `ReasoningItem`。
  - provider-native content block snapshot 与 same-provider replay。
  - usage/cache token mapping。
  - structured output 与 assistant message prefill 不兼容；同用时提前抛 `UnsupportedCapabilityError`。
  - 拒绝显式 provider-native `output_config` 与旧 beta `output_format`，用户统一使用 `ResponseFormat`。
- Parsed structured output：
  - `generate_parsed()` / `agenerate_parsed()` 使用既有 `pydantic_output()` helper。
  - 最终响应复用 `ParsedGenerationResponse` / `StructuredOutputParseError`。
- Automatic prefix caching：
  - `RemoteContextHint.enable_cache=True` 映射为 top-level `cache_control={"type": "ephemeral"}`。
  - `new_items_start_index` 兼容接收但忽略。
  - 不做 response-style previous response 差分传输。
  - 不暴露 explicit cache control；显式传入 `cache_control` 会抛 `UnsupportedCapabilityError`。
- Messages streaming：
  - message lifecycle、text delta、tool input JSON delta、thinking delta、usage update、completed/error 与 unknown passthrough。
- Capability：
  - adapter capability 声明 generation/streaming/async/structured output/function tools/usage。
  - text/image input modality。
  - 不支持 embedding、Files API、media generation、provider-hosted/server tools、SDK Tool Runner。
  - model capability 默认 unknown，支持用户 overrides。

## 暂不实现

- 自动 provider routing。
- 自动模型选择或 fallback。
- 自动工具执行。
- 内建 ReAct/agent loop。
- 内部权威模型能力表。
- 对同时支持 Responses API 与 Chat Completions API 的 provider 维护双 generation 调用面。
- 隐式本地文件自动上传。
- Provider-hosted tool、remote tool、MCP tool 的通用 core 抽象。
- Provider conversation 持久化上下文抽象。
- JSON mode / `json_object` structured output 兼容。
- 跨 provider replay。

## 后续规划

### 后续阶段

- Provider-hosted tools 专门设计留待后续阶段。
- Provider capability matrix。
- 可选真实 API integration tests。
- API reference 与 migration notes 持续完善。

## 注意事项

- 所有 Python 命令必须使用项目根目录 `.venv`。
- Capability 中无法可靠获取的 model 字段应表达为 unknown。
- Reasoning 与 parallel tool calls 是通用 generation 配置，不应作为 OpenAI 专有参数处理。
- 不同 provider 的 reasoning effort 取值不同，应通过 capability 字段声明支持集合。
- 同时支持 Responses API 与 Chat Completions API 的 provider，Python generation adapter 仅使用 Responses API。
- Provider-side state/cache/previous response 只能作为优化 hint，不改变 Full-context First。
- `RemoteContextHint` 表达 `enable_cache` 与 `new_items_start_index`，不让用户直接传入 provider response id。
- Full-context First 要求用户传入完整 `items`，但 provider 请求层可以在新增边界明确且 anchor response id 可用时只传追加 suffix。
- Response id 失效后的 refresh 由 response-style provider client 自动处理；强制 replay 缺少 provider-native snapshot 时应失败而不是静默降级。

## 验证

```bash
cd python
../.venv/bin/python -m pytest
```

当前 v0.6 基线：`190 passed, 10 skipped`；Anthropic structured output 相关单测为 `21 passed`。
