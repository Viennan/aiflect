from __future__ import annotations

from types import SimpleNamespace

from whero.vatbrain import GenerationStreamAccumulator, MessageItem, TextPart
from whero.vatbrain.core.generation import StreamEventType
from whero.vatbrain.core.items import FunctionCallItem
from whero.vatbrain.providers.volcengine.stream import from_volcengine_stream_event


def test_stream_text_delta_maps_to_normalized_event() -> None:
    event = SimpleNamespace(
        type="response.output_text.delta",
        response_id="resp_1",
        item_id="msg_1",
        output_index=0,
        content_index=0,
        delta="hello",
    )

    mapped = from_volcengine_stream_event(event, sequence=3)

    assert mapped.provider == "volcengine"
    assert mapped.type == StreamEventType.TEXT_DELTA.value
    assert mapped.sequence == 3
    assert mapped.response_id == "resp_1"
    assert mapped.item_id == "msg_1"
    assert mapped.delta == "hello"
    assert mapped.metadata["provider_event_type"] == "response.output_text.delta"
    assert mapped.metadata["semantic_type"] == StreamEventType.ITEM_DELTA.value


def test_stream_function_call_item_and_arguments_map_to_tool_events() -> None:
    item_event = SimpleNamespace(
        type="response.output_item.added",
        output_index=1,
        item=SimpleNamespace(
            type="function_call",
            id="fc_1",
            name="lookup",
            arguments="",
            call_id="call_1",
            status="in_progress",
        ),
    )
    delta_event = {
        "type": "response.function_call_arguments.delta",
        "item_id": "fc_1",
        "output_index": 1,
        "delta": '{"q"',
    }

    created = from_volcengine_stream_event(item_event, sequence=0)
    delta = from_volcengine_stream_event(delta_event, sequence=1)

    assert created.type == StreamEventType.ITEM_CREATED.value
    assert isinstance(created.item, FunctionCallItem)
    assert created.item.name == "lookup"
    assert delta.type == StreamEventType.TOOL_CALL_DELTA.value
    assert delta.delta == '{"q"'


def test_stream_reasoning_summary_delta_maps_to_reasoning_delta() -> None:
    event = {
        "type": "response.reasoning_summary_text.delta",
        "item_id": "rs_1",
        "output_index": 0,
        "summary_index": 0,
        "delta": "thinking",
    }

    mapped = from_volcengine_stream_event(event, sequence=8)

    assert mapped.type == StreamEventType.REASONING_DELTA.value
    assert mapped.delta == "thinking"
    assert mapped.metadata["reasoning_kind"] == "summary"
    assert mapped.metadata["summary_index"] == 0


def test_stream_terminal_events_map_completed_incomplete_failed_and_error() -> None:
    completed_response = SimpleNamespace(
        id="resp_1",
        model="doubao-test",
        status="completed",
        output=[],
        usage=SimpleNamespace(input_tokens=1, output_tokens=2, total_tokens=3),
    )
    failed_response = SimpleNamespace(
        id="resp_2",
        model="doubao-test",
        status="failed",
        output=[],
        usage=None,
        error=SimpleNamespace(message="failed", code="bad"),
    )

    completed = from_volcengine_stream_event(
        SimpleNamespace(type="response.completed", response=completed_response),
        sequence=1,
    )
    incomplete = from_volcengine_stream_event(
        SimpleNamespace(type="response.incomplete", response=completed_response),
        sequence=2,
    )
    failed = from_volcengine_stream_event(
        SimpleNamespace(type="response.failed", response=failed_response),
        sequence=3,
    )
    errored = from_volcengine_stream_event(
        SimpleNamespace(type="error", message="bad input", code="invalid", param="input"),
        sequence=4,
    )

    assert completed.type == StreamEventType.RESPONSE_COMPLETED.value
    assert completed.usage is not None
    assert completed.usage.total_tokens == 3
    assert incomplete.type == StreamEventType.RESPONSE_INCOMPLETE.value
    assert failed.type == StreamEventType.RESPONSE_FAILED.value
    assert "failed" in (failed.error or "")
    assert errored.type == StreamEventType.RESPONSE_ERROR.value
    assert "bad input" in (errored.error or "")


def test_stream_accumulator_rebuilds_volcengine_text_response() -> None:
    accumulator = GenerationStreamAccumulator(provider="volcengine")
    for sequence, event in enumerate(
        [
            {"type": "response.output_text.delta", "response_id": "resp_1", "delta": "hel"},
            {"type": "response.output_text.delta", "response_id": "resp_1", "delta": "lo"},
            {
                "type": "response.completed",
                "response": SimpleNamespace(
                    id="resp_1",
                    model="doubao-test",
                    status="completed",
                    output=[],
                    usage=None,
                ),
            },
        ]
    ):
        accumulator.add(from_volcengine_stream_event(event, sequence=sequence))

    response = accumulator.to_response()

    assert response.provider == "volcengine"
    assert response.id == "resp_1"
    assert isinstance(response.output_items[0], MessageItem)
    assert response.output_items[0].parts == (TextPart("hello"),)
