# 火山方舟资料索引

状态：第三方资料索引  
最近更新：2026-05-15

## 概览

本目录保存火山方舟相关开发资料的本地快照，用于分析 `vatbrain` 的跨厂商抽象边界。资料覆盖 Chat API、Responses API、Responses API 专题教程、Files API、多模态 embedding、图片/视频理解、图片/视频生成、函数调用、结构化输出、reasoning 与 streaming。

这些资料是第三方能力事实来源，不是 `vatbrain` 自身设计文档。面向产品设计的归纳请参见 [design/provider-capability-integration.CN.md](design/provider-capability-integration.CN.md)。

## 推理与对话

- [3rds/volengine/response_api.md](3rds/volengine/response_api.md)：Responses API 概览，包含与 Chat API 的差异、默认存储、`previous_response_id`、`caching`、结构化输出、内置工具和函数工具差异。
- [3rds/volengine/response_api_text_gen.md](3rds/volengine/response_api_text_gen.md)：Responses API 文本生成专题，包含 Ark SDK 调用、文档中的 OpenAI-compatible 示例对照、`previous_response_id` 分支对话、`store`/`caching`、streaming event、`instructions` 与上下文管理规则；v0.4 实现只采用 Ark SDK。
- [3rds/volengine/response_api_multimodal_understanding.md](3rds/volengine/response_api_multimodal_understanding.md)：Responses API 多模态理解专题，覆盖图片、视频、文档通过 Files API、file id、URL/base64 等方式输入，包含视频预处理 fps、文件处理等待和流式输出示例。
- [3rds/volengine/response_api_reasoning.md](3rds/volengine/response_api_reasoning.md)：Responses API reasoning 专题，说明 `thinking.type`、reasoning summary 流式事件、`reasoning.effort`、`reasoning_tokens`、加密思考内容 include 与模型支持差异。
- [3rds/volengine/response_api_tool_calling.md](3rds/volengine/response_api_tool_calling.md)：Responses API 工具调用专题，说明 function tool 声明、`function_call` 输出、`function_call_output` 回填、`call_id` 关联，以及 Web Search、Image Process、Knowledge Search、Remote MCP 等 provider-hosted/remote tools。
- [3rds/volengine/text_generation.md](3rds/volengine/text_generation.md)：文本生成能力，包含 Chat API 与 Responses API 示例、流式、异步和输出长度控制。
- [3rds/volengine/streaming.md](3rds/volengine/streaming.md)：Chat API 与 Responses API 流式输出示例，包含 Responses 事件类型示例。
- [3rds/volengine/reasoning.md](3rds/volengine/reasoning.md)：深度思考与 reasoning 控制，包含 `thinking.type`、`reasoning.effort`、reasoning 内容回传、工具调用场景中的上下文行为。

## 结构化输出与工具

- [3rds/volengine/structured_output.md](3rds/volengine/structured_output.md)：结构化输出 beta 能力，包含 `response_format`、`text.format`、JSON schema 与模型限制。
- [3rds/volengine/function_calling.md](3rds/volengine/function_calling.md)：函数调用流程、工具声明、工具结果回填、并行工具调用和工具调用调优建议。

## 多模态理解与资源

- [3rds/volengine/file_api.md](3rds/volengine/file_api.md)：Files API，包含上传、检索、列表、删除、文件状态、过期时间、预处理配置和文件类型限制。
- [3rds/volengine/image_understanding.md](3rds/volengine/image_understanding.md)：图片理解，包含 URL、base64、本地文件路径与 Files API 输入方式。
- [3rds/volengine/video_understanding.md](3rds/volengine/video_understanding.md)：视频理解，包含 File ID、base64、URL、fps 和流式示例。

## Embedding

- [3rds/volengine/embeding.md](3rds/volengine/embeding.md)：Doubao 多模态 embedding，包含文本/图片/视频混合输入、`instructions`、dense embedding、sparse embedding 与 usage 示例。

## 媒体生成

- [3rds/volengine/image_generation.md](3rds/volengine/image_generation.md)：图片生成与编辑，包含文生图、图生图、组图生成、联网搜索工具、流式图片生成事件和输出格式。
- [3rds/volengine/video_generation.md](3rds/volengine/video_generation.md)：视频生成、编辑、延长和多模态参考，包含异步任务创建、轮询、输出规格和联网搜索工具。

## 对 vatbrain 的设计提示

- 火山方舟的 Responses API 与 `vatbrain` 的 `Full-context First` 不冲突，但其默认存储、`previous_response_id` 和 `caching` 应被视为 provider-side optimization，而不是核心语义状态。
- 火山方舟同时暴露用户执行的 function tools 与 provider-hosted tools，因此 `Tool` 抽象需要表达执行责任。
- Files API 说明文件资源具有独立生命周期，不能只作为 message content 的一个字符串字段处理。
- 多模态 embedding 和媒体生成说明 `vatbrain` 需要把 inference、representation、resource、media generation 分成不同 API 家族。
