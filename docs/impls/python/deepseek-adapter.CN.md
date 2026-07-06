# Python DeepSeek Adapter 实现记录

状态：已实现
最近更新：2026-06-07

## 定位

本文记录 Python 参考实现新增 DeepSeek provider adapter 的实现方案与落地状态。需求状态见 [REQ-2026-06-python-deepseek-provider.CN.md](../../requirements/REQ-2026-06-python-deepseek-provider.CN.md)，高层设计见 [deepseek-provider-support.CN.md](../../design/deepseek-provider-support.CN.md)。

DeepSeek adapter 首期只实现 Anthropic-compatible Messages API。OpenAI completion compatible 形式通过 `api_format="openai_completion"` 预留，但当前 fail fast。

## 包结构

```text
python/whero/aiflect/providers/deepseek/
  __init__.py
  capabilities.py
  client.py
  mapper.py
  stream.py
```

Optional dependency：

```toml
deepseek = [
    "anthropic>=0.105.2,<1",
]
```

## Client

`DeepSeekClient` 与其他 provider client 保持同形：

- `generate()`
- `agenerate()`
- `stream_generate()`
- `astream_generate()`
- `get_adapter_capability()`
- `get_model_capability()`

初始化参数新增：

```python
api_format: str = "anthropic"
```

当前行为：

- `"anthropic"`：使用 Anthropic SDK client 调用 DeepSeek Anthropic-compatible endpoint。
- `"openai_completion"`：抛 `ValueError`。
- 其他值：抛 `ValueError`。

默认 base URL：

```text
https://api.deepseek.com/anthropic
```

优先级：显式 `base_url` > `ClientConfig.base_url` > 默认 base URL。

## Request Mapper

入口：

```python
to_deepseek_generation_params(request, stream=False) -> dict[str, Any]
```

主要映射：

- `model` -> `model`
- `MessageItem.system/developer` 初始 prefix -> `system`
- `MessageItem.user/assistant` -> `messages`
- `TextPart` -> `{"type": "text", "text": ...}`
- `GenerationConfig.temperature` -> `temperature`
- `GenerationConfig.top_p` -> `top_p`
- `GenerationConfig.max_output_tokens` -> `max_tokens`
- `FunctionToolSpec` -> DeepSeek Anthropic-compatible tool
- `ToolChoice.AUTO/NONE/REQUIRED` -> `auto/none/any`
- `ReasoningConfig.mode enabled/auto` -> `thinking={"type": "enabled"}`
- `ReasoningConfig.mode disabled/none` -> `thinking={"type": "disabled"}`
- `ReasoningConfig.effort high/max` -> `output_config={"effort": ...}`
- `stream=True` -> top-level `stream=True`

拒绝项：

- 缺少 `max_tokens`。
- 非初始位置的 system/developer message。
- `ImagePart`、`AudioPart`、`VideoPart`、`FilePart`。
- `FunctionToolType.CUSTOM`。
- `ResponseFormat`。
- 显式 `cache_control`。
- `output_format`。
- `output_config.format`。
- `ToolCallConfig.parallel_tool_calls=False`。
- unsupported reasoning fields：`budget_tokens`、`summary`、`include_trace`、`provider_options`。

`RemoteContextHint.enable_cache=True`、`session_key` 与 `new_items_start_index` 被兼容接收，但不影响 params。

## Response Mapper

入口：

```python
from_deepseek_generation_response(response) -> GenerationResponse
```

支持 content block：

- `text` -> assistant `MessageItem`
- `tool_use` -> `FunctionCallItem`
- `thinking` -> `ReasoningItem`

每个可重放 block 保存：

```python
ProviderItemSnapshot(
    provider="deepseek",
    api_family="anthropic_messages",
    item_type=block_type,
    payload=...,
)
```

Usage 映射：

- `input_tokens + cache_creation_input_tokens + cache_read_input_tokens` -> `Usage.input_tokens`
- `output_tokens` -> `Usage.output_tokens`
- `cache_read_input_tokens` -> `Usage.cached_tokens`
- provider raw usage 保留在 `Usage.raw` 与 `metadata`

## Stream Mapper

入口：

```python
from_deepseek_stream_event(event, sequence=...) -> GenerationStreamEvent
```

支持事件：

- `message_start` -> `response.created`
- `content_block_start(tool_use)` -> `item.created`
- `content_block_start(thinking)` -> `reasoning.created`
- `content_block_delta(text_delta)` -> `text.delta`
- `content_block_delta(input_json_delta)` -> `tool_call.delta`
- `content_block_delta(thinking_delta/signature_delta)` -> `reasoning.delta`
- `message_delta` with usage -> `usage.updated`
- `message_stop` -> `response.completed`
- `error` -> `response.error`
- 其他事件 -> `unknown`

## Capability

`capabilities.py` 声明：

- provider：`deepseek`
- generation/streaming/async：支持
- text embedding / multimodal embedding：不支持
- input modalities：`("text",)`
- output modalities：`("text",)`
- structured output：不支持
- reasoning config：支持
- supported reasoning efforts：`("high", "max")`
- remote context：不支持 transport
- function tools：支持
- custom tools：不支持
- parallel tool calls control：不支持

## 测试

新增单元测试：

- `tests/unit/test_deepseek_generation_mapper.py`
- `tests/unit/test_deepseek_client.py`
- `tests/unit/test_deepseek_stream_mapper.py`
- `tests/unit/test_capabilities.py`

Costly test 接入：

- `tests/conftest.py` 支持 provider `"deepseek"`。
- generation costly tests 增加 DeepSeek marker；image 与 structured output case 依赖 model capability 自动 skip。

已执行验证：

```bash
cd python
../.venv/bin/python -m pytest tests/unit/test_deepseek_generation_mapper.py tests/unit/test_deepseek_client.py tests/unit/test_deepseek_stream_mapper.py tests/unit/test_capabilities.py
```

结果：`26 passed`。

```bash
scripts/run-costly-tests --provider deepseek --feature generation --all-models --yes
```

结果：`4 passed, 10 skipped`，覆盖 `deepseek-v4-flash` 与 `deepseek-v4-pro` 的 generation/text streaming costly smoke。

## 参考

- [deepseek-provider-support.CN.md](../../design/deepseek-provider-support.CN.md)
- [REQ-2026-06-python-deepseek-provider.CN.md](../../requirements/REQ-2026-06-python-deepseek-provider.CN.md)
- [anthropic_api.CN.md](../../3rds/deepseek/anthropic_api.CN.md)
