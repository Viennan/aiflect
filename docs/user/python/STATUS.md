# Python 用户文档状态

状态：v0.5 已系统化整理
日期：2026-05-05
最近更新：2026-05-31

## 当前文档

- [user/python/quickstart.CN.md](user/python/quickstart.CN.md)：渐进式用户指南，从安装、client 初始化、generation、remote context/replay、streaming、图片/视频生成、structured output、tools、embedding、capability 到错误处理。
- [user/python/api-reference.CN.md](user/python/api-reference.CN.md)：Python public API 参考，覆盖当前暴露给用户的 core dataclass、enum、provider client、media generation、Pydantic helper、capability、usage 与错误类型。
- [user/python/volcengine-quickstart.CN.md](user/python/volcengine-quickstart.CN.md)：Volcengine / 火山方舟 provider 快速开始，覆盖 Ark SDK-only 安装、generation、streaming、图片生成、视频任务、Files API、多模态 embedding、function tools、remote context 与限制。
- [user/python/pydantic-structured-output.CN.md](user/python/pydantic-structured-output.CN.md)：Pydantic structured output 编程模型，说明 helper、默认 schema 行为、strict schema、解析与错误处理。

## 已覆盖

- OpenAI provider client：
  - 初始化。
  - 显式凭据初始化与 SecretString 存储。
  - 同步/异步 generation。
  - 同步/异步 streaming。
  - 同步/异步 embedding。
  - 直接 Images API 图片生成、参考图生成与图片流式生成。
  - capability 查询。
- Volcengine provider client：
  - `whero-vatbrain[volcengine]` optional dependency。
  - 显式凭据初始化与 SecretString 存储。
  - Ark SDK-only 调用边界。
  - 同步/异步 generation 与 streaming。
  - Responses API text/image/video/file input。
  - JSON Schema structured output。
  - reasoning config 与 reasoning summary stream event。
  - user-executed function tools。
  - Files API upload/retrieve/list/delete/wait。
  - 多模态 embedding、instructions、dense/sparse vector。
  - Ark Images API 图片生成、参考图生成与图片流式生成。
  - Ark Content Generation 视频任务创建、查询与轮询。
  - provider-native replay 与 previous response 差分传输。
  - capability 查询。
- Generation：
  - Full-context First 编程模型。
  - `GenerationConfig`。
  - `ReasoningConfig`。
  - `ToolCallConfig`。
  - `ResponseFormat` JSON Schema structured output。
  - `RemoteContextHint` 与 `covered_item_count`。
  - `ReplayPolicy`、provider snapshot、OpenAI `phase` 与 `AssistantMessagePhase`。
  - response id 失效后的显式 fallback。
- Streaming：
  - 标准化 event。
  - `raw_event`。
  - `GenerationStreamAccumulator`。
- Structured Output：
  - JSON Schema-only 原则。
  - Pydantic helper。
  - `generate_parsed()` / `agenerate_parsed()`。
  - schema name、description、strict 默认行为。
- Tools：
  - Function tool 参数 schema 与 `FunctionCallItem.arguments` 解析。
  - Custom tool raw string input。
  - `FunctionResultItem` 回填。
  - 空 `parameters_schema` 与 custom tool 的区别。
- Embedding：
  - OpenAI text embedding。
  - Volcengine multimodal embedding。
- Media Generation：
  - OpenAI `generate_image()` / `agenerate_image()`。
  - OpenAI `stream_generate_image()` / `astream_generate_image()`。
  - Volcengine `generate_image()` / `agenerate_image()`。
  - Volcengine `stream_generate_image()` / `astream_generate_image()`。
  - Volcengine `create_video_generation_task()` / `get_video_generation_task()` / `wait_for_video_generation_task()` 及异步 counterparts。
  - Volcengine 视频任务的 text/image/video/audio/file reference content。
  - 图片生成 `background` provider capability：OpenAI 支持 `auto`、`transparent`、`opaque`，Volcengine 当前不支持。
  - 图片/视频生成请求的 `watermark` 参数，默认要求添加 AI 水印；无可控水印能力的 provider 会忽略。
  - `ImageGenerationRequest` 不包含 `tools`，media generation 不复用 function tool 模型。
- Core models：
  - `MessageItem`、content parts、function call/result、reasoning item。
  - resources/file 模型。
  - media artifact/task 模型。
  - `VideoGenerationRequest`。
  - usage、capability、errors。
- 限制：
  - 已实现 OpenAI 与 Volcengine provider。
  - OpenAI 文本 generation 仅 Responses API。
  - Volcengine 文本 generation 仅 Ark SDK Responses API，不使用 OpenAI-compatible surface。
  - OpenAI 图片生成仅直接使用 Images API，不使用 Responses API hosted image generation tool。
  - Volcengine 图片/视频生成仅使用 Ark SDK 原生 Images API 与 Content Generation tasks。
  - 不自动工具执行。
  - 不暴露 provider-hosted/remote/MCP tool 的通用抽象。
  - 不暴露 provider conversation 持久化上下文抽象。
  - 不兼容 JSON mode。
  - 不支持跨 provider replay。

## 后续维护规则

- 新增 public API 时，同步更新 [user/python/api-reference.CN.md](user/python/api-reference.CN.md)。
- 用户常用主流程变化时，同步更新 [user/python/quickstart.CN.md](user/python/quickstart.CN.md)。
- Structured output helper 变化时，同步更新 [user/python/pydantic-structured-output.CN.md](user/python/pydantic-structured-output.CN.md)。
- 新增 provider adapter 时，新增 provider-specific quickstart，并在 API reference 中说明支持范围。
- 若 provider adapter 支持某个 core 模型的真实调用，应把“core-only”边界更新为“provider-supported”。

## 待完善

- Provider capability matrix。
- 可选真实 API 调用示例。
- 更系统的错误处理 cookbook。
- 跨 provider 迁移指南。
