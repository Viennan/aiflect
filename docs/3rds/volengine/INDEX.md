# 火山方舟资料索引

状态：第三方资料索引  
最近更新：2026-06-12

## 概览

本目录保存火山方舟相关开发资料的本地快照，用于分析 `vatbrain` 的跨厂商抽象边界。资料覆盖 Chat API、Responses API、Responses API 专题教程、上下文缓存、Files API、多模态 embedding、图片/视频理解、图片/视频生成、函数调用、结构化输出、reasoning 与 streaming。

这些资料是第三方能力事实来源，不是 `vatbrain` 自身设计文档。面向产品设计的归纳请参见 [provider-capability-integration.CN.md](../../design/provider-capability-integration.CN.md)。

## 推理与对话

- [response_api.md](response_api.md)：Responses API 概览，包含与 Chat API 的差异、默认存储、`previous_response_id`、`caching`、结构化输出、内置工具和函数工具差异。
- [response_api_detail_ref.md](response_api_detail_ref.md)：Responses API 创建请求/响应参数 reference，详细列出 `input` item、`instructions`、`previous_response_id`、`expire_at`、`thinking`、`reasoning`、`include`、`caching`、`store`、采样参数、`text.format`、工具、`tool_choice`、`max_tool_calls` 与 `context_management`。
- [context_cache.md](context_cache.md)：上下文缓存总览，区分隐式缓存、显式缓存、Session 缓存、前缀缓存、Responses API 与 Context API 的调用方式和生命周期差异。
- [response_api_context_cache.md](response_api_context_cache.md)：Responses API 上下文缓存专题，覆盖前缀缓存、Session 缓存、`caching`、`previous_response_id`、`expire_at`、cache 链限制和计费说明。
- [response_api_text_gen.md](response_api_text_gen.md)：Responses API 文本生成专题，包含 Ark SDK 调用、文档中的 OpenAI-compatible 示例对照、`previous_response_id` 分支对话、`store`/`caching`、streaming event、`instructions` 与上下文管理规则；v0.4 实现只采用 Ark SDK。
- [response_api_multimodal_understanding.md](response_api_multimodal_understanding.md)：Responses API 多模态理解专题，覆盖图片、视频、文档通过 Files API、file id、URL/base64 等方式输入，包含视频预处理 fps、文件处理等待和流式输出示例。
- [response_api_reasoning.md](response_api_reasoning.md)：Responses API reasoning 专题，说明 `thinking.type`、reasoning summary 流式事件、`reasoning.effort`、`reasoning_tokens`、加密思考内容 include 与模型支持差异。
- [response_api_tool_calling.md](response_api_tool_calling.md)：Responses API 工具调用专题，说明 function tool 声明、`function_call` 输出、`function_call_output` 回填、`call_id` 关联，以及 Web Search、Image Process、Knowledge Search、Remote MCP 等 provider-hosted/remote tools。
- [text_generation.md](text_generation.md)：文本生成能力，包含 Chat API 与 Responses API 示例、流式、异步和输出长度控制。
- [streaming.md](streaming.md)：Chat API 与 Responses API 流式输出示例，包含 Responses 事件类型示例。
- [reasoning.md](reasoning.md)：深度思考与 reasoning 控制，包含 `thinking.type`、`reasoning.effort`、reasoning 内容回传、工具调用场景中的上下文行为。

## 结构化输出与工具

- [structured_output.md](structured_output.md)：结构化输出 beta 能力，包含 `response_format`、`text.format`、JSON schema 与模型限制。
- [function_calling.md](function_calling.md)：函数调用流程、工具声明、工具结果回填、并行工具调用和工具调用调优建议。

## 多模态理解与资源

- [file_api.md](file_api.md)：Files API，包含上传、检索、列表、删除、文件状态、过期时间、预处理配置和文件类型限制。
- [file_upload_api_ref.md](file_upload_api_ref.md)：Files API 上传参数 reference，覆盖 `file`、`purpose=user_data`、`preprocess_configs.video.fps/model`、`expire_at` 与 file object 响应。
- [file_object_ref.md](file_object_ref.md)：File object reference，列出 `id`、`purpose`、`bytes`、`created_at`、`expire_at`、`mime_type`、`status`、`error` 和 `preprocess_configs`。
- [file_retrieve_api_ref.md](file_retrieve_api_ref.md)：Files API 检索参数 reference，说明通过 file id 获取 file object。
- [file_del_api_ref.md](file_del_api_ref.md)：Files API 删除参数 reference，说明 file id 删除请求和 `deleted` 响应。
- [image_understanding.md](image_understanding.md)：图片理解，包含 URL、base64、本地文件路径与 Files API 输入方式。
- [video_understanding.md](video_understanding.md)：视频理解，包含 File ID、base64、URL、fps 和流式示例。

## Embedding

- [embeding.md](embeding.md)：Doubao 多模态 embedding，包含文本/图片/视频混合输入、`instructions`、dense embedding、sparse embedding 与 usage 示例。
- [embeding_api_ref.md](embeding_api_ref.md)：多模态 embedding API reference，详细列出 text/image/video 输入、`encoding_format`、`dimensions`、`instructions`、纯文本 sparse embedding、dense/sparse 响应和 usage 细分字段。

## 媒体生成

- [image_generation.md](image_generation.md)：图片生成与编辑，包含文生图、图生图、组图生成、联网搜索工具、流式图片生成事件和输出格式。
- [image_generation_api_ref.md](image_generation_api_ref.md)：图片生成 API reference，详细列出 `model`、`prompt`、`image`、`size`、组图参数、`stream`、`output_format`、`response_format`、`watermark`、提示词优化和响应/usage 字段。
- [image_generation_stream_api_ref.md](image_generation_stream_api_ref.md)：图片生成流式事件 reference，说明 `partial_succeeded`、`partial_failed`、`completed` 和错误事件字段。
- [video_generation.md](video_generation.md)：视频生成、编辑、延长和多模态参考，包含异步任务创建、轮询、输出规格和联网搜索工具。
- [video_gen_create_api_ref.md](video_gen_create_api_ref.md)：视频生成任务创建 API reference，详细列出 content、多模态参考、callback、尾帧、服务等级、过期时间、音频、draft、priority、resolution、ratio、duration/frames、seed、camera_fixed、watermark 等参数。
- [video_gen_query_api_ref.md](video_gen_query_api_ref.md)：视频生成任务查询 API reference，说明状态、产物 URL、尾帧、seed、resolution、ratio、duration/frames、fps、音频、priority、usage 等返回字段。
- [video_gen_cancel_api_ref.md](video_gen_cancel_api_ref.md)：视频生成任务取消/删除 API reference，说明 queued 任务取消与终态任务记录删除行为。

## 对 vatbrain 的设计提示

- 火山方舟的 Responses API 与 `vatbrain` 的 `Full-context First` 不冲突，但其默认存储、`previous_response_id` 和 `caching` 应被视为 provider-side optimization，而不是核心语义状态。
- 火山方舟 Responses API Session 缓存依赖 `caching={"type":"enabled"}`、`store`、`previous_response_id` 和 `expire_at` 共同工作；其中 `expire_at` 同时影响 response 存储和 token cache 生命周期，适合由 adapter 封装为受控策略。
- 火山方舟同时暴露用户执行的 function tools 与 provider-hosted tools，因此 `Tool` 抽象需要表达执行责任。
- Files API 说明文件资源具有独立生命周期，不能只作为 message content 的一个字符串字段处理。
- 多模态 embedding 和媒体生成说明 `vatbrain` 需要把 inference、representation、resource、media generation 分成不同 API 家族。
