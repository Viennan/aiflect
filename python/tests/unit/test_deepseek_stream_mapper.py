from __future__ import annotations

from types import SimpleNamespace

from whero.aiflect import GenerationStreamAccumulator, MessageItem, TextPart
from whero.aiflect.core.generation import StreamEventType
from whero.aiflect.core.items import FunctionCallItem
from whero.aiflect.providers.deepseek.stream import from_deepseek_stream_event


def test_deepseek_text_delta_maps_to_normalized_event() -> None:
    event = SimpleNamespace(
        type="content_block_delta",
        index=0,
        delta=SimpleNamespace(type="text_delta", text="hel"),
    )

    mapped = from_deepseek_stream_event(event, sequence=3)

    assert mapped.type == StreamEventType.TEXT_DELTA.value
    assert mapped.provider == "deepseek"
    assert mapped.sequence == 3
    assert mapped.item_id == "content_block_0"
    assert mapped.delta == "hel"
    assert mapped.metadata["provider_event_type"] == "content_block_delta"
    assert mapped.metadata["content_index"] == 0


def test_deepseek_tool_use_stream_rebuilds_function_call() -> None:
    accumulator = GenerationStreamAccumulator(provider="deepseek")
    events = [
        SimpleNamespace(
            type="content_block_start",
            index=1,
            content_block=SimpleNamespace(
                type="tool_use",
                id="toolu_1",
                name="lookup",
                input={},
            ),
        ),
        SimpleNamespace(
            type="content_block_delta",
            index=1,
            delta=SimpleNamespace(type="input_json_delta", partial_json='{"q"'),
        ),
        SimpleNamespace(
            type="content_block_delta",
            index=1,
            delta=SimpleNamespace(type="input_json_delta", partial_json=':"x"}'),
        ),
    ]

    for sequence, event in enumerate(events):
        accumulator.add(from_deepseek_stream_event(event, sequence=sequence))

    response = accumulator.to_response()

    assert isinstance(response.output_items[0], FunctionCallItem)
    assert response.output_items[0].call_id == "toolu_1"
    assert response.output_items[0].name == "lookup"
    assert response.output_items[0].arguments == '{"q":"x"}'


def test_deepseek_stream_accumulator_rebuilds_text_response() -> None:
    accumulator = GenerationStreamAccumulator(provider="deepseek")
    events = [
        SimpleNamespace(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="text_delta", text="hel"),
        ),
        SimpleNamespace(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="text_delta", text="lo"),
        ),
        SimpleNamespace(type="message_stop"),
    ]

    for sequence, event in enumerate(events):
        accumulator.add(from_deepseek_stream_event(event, sequence=sequence))

    response = accumulator.to_response()

    assert response.provider == "deepseek"
    assert isinstance(response.output_items[0], MessageItem)
    assert response.output_items[0].parts == (TextPart("hello"),)


def test_deepseek_usage_and_terminal_events_map() -> None:
    usage_event = SimpleNamespace(
        type="message_delta",
        delta=SimpleNamespace(stop_reason="end_turn"),
        usage=SimpleNamespace(input_tokens=1, cache_read_input_tokens=2, output_tokens=3),
    )
    stop_event = SimpleNamespace(type="message_stop")

    usage = from_deepseek_stream_event(usage_event, sequence=0)
    stopped = from_deepseek_stream_event(stop_event, sequence=1)

    assert usage.type == StreamEventType.USAGE_UPDATED.value
    assert usage.usage is not None
    assert usage.usage.input_tokens == 3
    assert usage.usage.cached_tokens == 2
    assert usage.usage.total_tokens == 6
    assert usage.metadata["stop_reason"] == "end_turn"
    assert stopped.type == StreamEventType.RESPONSE_COMPLETED.value


def test_deepseek_reasoning_error_and_unknown_events_map() -> None:
    reasoning = from_deepseek_stream_event(
        SimpleNamespace(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="thinking_delta", thinking="thought"),
        ),
        sequence=0,
    )
    errored = from_deepseek_stream_event(
        {"type": "error", "error": {"message": "bad"}},
        sequence=1,
    )
    unknown = from_deepseek_stream_event({"type": "ping"}, sequence=2)

    assert reasoning.type == StreamEventType.REASONING_DELTA.value
    assert reasoning.delta == "thought"
    assert errored.type == StreamEventType.RESPONSE_ERROR.value
    assert "bad" in (errored.error or "")
    assert unknown.type == StreamEventType.UNKNOWN.value
    assert unknown.metadata["provider_event_type"] == "ping"
