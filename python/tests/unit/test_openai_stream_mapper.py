from __future__ import annotations

from types import SimpleNamespace

from whero.aiflect import FunctionToolType, GenerationStreamAccumulator, MessageItem, TextPart
from whero.aiflect.core.generation import StreamEventType
from whero.aiflect.core.items import FunctionCallItem
from whero.aiflect.providers.openai.stream import from_openai_stream_event


def test_stream_text_delta_maps_to_item_delta() -> None:
    event = SimpleNamespace(
        type="response.output_text.delta",
        response_id="resp_1",
        item_id="msg_1",
        delta="hello",
    )

    mapped = from_openai_stream_event(event, sequence=3)

    assert mapped.type == StreamEventType.TEXT_DELTA.value
    assert mapped.sequence == 3
    assert mapped.response_id == "resp_1"
    assert mapped.item_id == "msg_1"
    assert mapped.delta == "hello"
    assert mapped.metadata["provider_event_type"] == "response.output_text.delta"
    assert mapped.metadata["semantic_type"] == StreamEventType.ITEM_DELTA.value


def test_stream_content_part_lifecycle_maps_metadata_indexes() -> None:
    event = {
        "type": "response.content_part.added",
        "response_id": "resp_1",
        "item_id": "msg_1",
        "output_index": 0,
        "content_index": 1,
        "part": {"type": "output_text", "text": ""},
    }

    mapped = from_openai_stream_event(event, sequence=2)

    assert mapped.type == StreamEventType.CONTENT_PART_CREATED.value
    assert mapped.metadata["output_index"] == 0
    assert mapped.metadata["content_index"] == 1
    assert mapped.delta == {"type": "output_text", "text": ""}


def test_stream_text_done_maps_to_text_completed() -> None:
    event = SimpleNamespace(
        type="response.output_text.done",
        response_id="resp_1",
        item_id="msg_1",
        output_index=0,
        content_index=0,
        text="hello",
    )

    mapped = from_openai_stream_event(event, sequence=4)

    assert mapped.type == StreamEventType.TEXT_COMPLETED.value
    assert mapped.delta == "hello"


def test_stream_function_arguments_delta_maps_to_tool_delta() -> None:
    event = {
        "type": "response.function_call_arguments.delta",
        "response_id": "resp_1",
        "item_id": "fc_1",
        "delta": '{"q"',
    }

    mapped = from_openai_stream_event(event, sequence=4)

    assert mapped.type == StreamEventType.TOOL_CALL_DELTA.value
    assert mapped.delta == '{"q"'
    assert mapped.metadata["provider_event_type"] == "response.function_call_arguments.delta"


def test_stream_function_call_item_added_maps_to_function_call_item() -> None:
    event = SimpleNamespace(
        type="response.output_item.added",
        response_id="resp_1",
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

    mapped = from_openai_stream_event(event, sequence=3)

    assert mapped.type == StreamEventType.ITEM_CREATED.value
    assert isinstance(mapped.item, FunctionCallItem)
    assert mapped.item.name == "lookup"
    assert mapped.metadata["output_index"] == 1


def test_stream_custom_tool_call_item_added_maps_to_function_call_item() -> None:
    event = SimpleNamespace(
        type="response.output_item.added",
        response_id="resp_1",
        output_index=1,
        item=SimpleNamespace(
            type="custom_tool_call",
            id="ctc_1",
            name="run_code",
            input="print('hello')",
            call_id="call_1",
            status="in_progress",
        ),
    )

    mapped = from_openai_stream_event(event, sequence=3)

    assert mapped.type == StreamEventType.ITEM_CREATED.value
    assert isinstance(mapped.item, FunctionCallItem)
    assert mapped.item.type == FunctionToolType.CUSTOM
    assert mapped.item.input == "print('hello')"
    assert mapped.metadata["tool_type"] == "custom"


def test_stream_custom_tool_input_delta_maps_to_tool_delta() -> None:
    event = {
        "type": "response.custom_tool_call_input.delta",
        "response_id": "resp_1",
        "item_id": "ctc_1",
        "delta": "print",
    }

    mapped = from_openai_stream_event(event, sequence=4)

    assert mapped.type == StreamEventType.TOOL_CALL_DELTA.value
    assert mapped.delta == "print"
    assert mapped.metadata["tool_type"] == "custom"


def test_stream_reasoning_summary_delta_maps_to_reasoning_delta() -> None:
    event = {
        "type": "response.reasoning_summary_text.delta",
        "response_id": "resp_1",
        "item_id": "rs_1",
        "delta": "thinking",
    }

    mapped = from_openai_stream_event(event, sequence=8)

    assert mapped.type == StreamEventType.REASONING_DELTA.value
    assert mapped.delta == "thinking"
    assert mapped.metadata["reasoning_kind"] == "summary"


def test_stream_incomplete_maps_response_and_usage() -> None:
    response = SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status="incomplete",
        output=[],
        usage=SimpleNamespace(input_tokens=1, output_tokens=2, total_tokens=3),
    )
    event = SimpleNamespace(type="response.incomplete", response=response)

    mapped = from_openai_stream_event(event, sequence=5)

    assert mapped.type == StreamEventType.RESPONSE_INCOMPLETE.value
    assert mapped.response_id == "resp_1"
    assert mapped.usage is not None
    assert mapped.usage.total_tokens == 3


def test_stream_completed_event_maps_response_and_usage() -> None:
    response = SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status="completed",
        output=[],
        usage=SimpleNamespace(input_tokens=1, output_tokens=2, total_tokens=3),
    )
    event = SimpleNamespace(type="response.completed", response=response)

    mapped = from_openai_stream_event(event, sequence=5)

    assert mapped.type == StreamEventType.RESPONSE_COMPLETED.value
    assert mapped.response_id == "resp_1"
    assert mapped.response is not None
    assert mapped.usage is not None
    assert mapped.usage.total_tokens == 3


def test_stream_failed_and_error_events_are_distinct() -> None:
    failed = from_openai_stream_event(
        {
            "type": "response.failed",
            "response_id": "resp_1",
            "error": {"message": "failed"},
        },
        sequence=6,
    )
    errored = from_openai_stream_event(
        {
            "type": "response.error",
            "response_id": "resp_1",
            "error": {"message": "bad"},
        },
        sequence=7,
    )

    assert failed.type == StreamEventType.RESPONSE_FAILED.value
    assert errored.type == StreamEventType.RESPONSE_ERROR.value
    assert "failed" in (failed.error or "")
    assert "bad" in (errored.error or "")


def test_unknown_stream_event_preserves_raw_provider_type() -> None:
    event = {"type": "response.web_search_call.in_progress", "response_id": "resp_1"}

    mapped = from_openai_stream_event(event, sequence=9)

    assert mapped.type == StreamEventType.UNKNOWN.value
    assert mapped.metadata["provider_event_type"] == "response.web_search_call.in_progress"
    assert mapped.raw_event is event


def test_stream_accumulator_rebuilds_text_response_from_events() -> None:
    accumulator = GenerationStreamAccumulator(provider="openai")
    for sequence, event in enumerate(
        [
            {"type": "response.output_text.delta", "response_id": "resp_1", "delta": "hel"},
            {"type": "response.output_text.delta", "response_id": "resp_1", "delta": "lo"},
            {"type": "response.completed", "response": SimpleNamespace(id="resp_1", model="gpt-test", status="completed", output=[], usage=None)},
        ]
    ):
        accumulator.add(from_openai_stream_event(event, sequence=sequence))

    response = accumulator.to_response()

    assert response.id == "resp_1"
    assert isinstance(response.output_items[0], MessageItem)
    assert response.output_items[0].parts == (TextPart("hello"),)


def test_stream_accumulator_rebuilds_function_call_arguments() -> None:
    accumulator = GenerationStreamAccumulator(provider="openai")
    events = [
        SimpleNamespace(
            type="response.output_item.added",
            response_id="resp_1",
            output_index=0,
            item=SimpleNamespace(
                type="function_call",
                id="fc_1",
                name="lookup",
                arguments="",
                call_id="call_1",
                status="in_progress",
            ),
        ),
        {
            "type": "response.function_call_arguments.delta",
            "response_id": "resp_1",
            "item_id": "fc_1",
            "output_index": 0,
            "delta": '{"q"',
        },
        {
            "type": "response.function_call_arguments.done",
            "response_id": "resp_1",
            "item_id": "fc_1",
            "output_index": 0,
            "arguments": '{"q":"x"}',
        },
    ]
    for sequence, event in enumerate(events):
        accumulator.add(from_openai_stream_event(event, sequence=sequence))

    response = accumulator.to_response()

    assert isinstance(response.output_items[0], FunctionCallItem)
    assert response.output_items[0].name == "lookup"
    assert response.output_items[0].arguments == '{"q":"x"}'


def test_stream_accumulator_rebuilds_custom_tool_input() -> None:
    accumulator = GenerationStreamAccumulator(provider="openai")
    events = [
        SimpleNamespace(
            type="response.output_item.added",
            response_id="resp_1",
            output_index=0,
            item=SimpleNamespace(
                type="custom_tool_call",
                id="ctc_1",
                name="run_code",
                input="",
                call_id="call_1",
                status="in_progress",
            ),
        ),
        {
            "type": "response.custom_tool_call_input.delta",
            "response_id": "resp_1",
            "item_id": "ctc_1",
            "output_index": 0,
            "delta": "print",
        },
        {
            "type": "response.custom_tool_call_input.done",
            "response_id": "resp_1",
            "item_id": "ctc_1",
            "output_index": 0,
            "input": "print('hello')",
        },
    ]
    for sequence, event in enumerate(events):
        accumulator.add(from_openai_stream_event(event, sequence=sequence))

    response = accumulator.to_response()

    assert isinstance(response.output_items[0], FunctionCallItem)
    assert response.output_items[0].type == FunctionToolType.CUSTOM
    assert response.output_items[0].name == "run_code"
    assert response.output_items[0].input == "print('hello')"
    assert response.output_items[0].arguments == "print('hello')"


def test_stream_accumulator_prefers_completed_response_when_it_has_output_items() -> None:
    final_response = SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                id="msg_1",
                role="assistant",
                content=[SimpleNamespace(type="output_text", text="final")],
            )
        ],
        usage=None,
    )
    accumulator = GenerationStreamAccumulator(provider="openai")
    accumulator.add(
        from_openai_stream_event(
            {"type": "response.output_text.delta", "response_id": "resp_1", "delta": "partial"},
            sequence=0,
        )
    )
    accumulator.add(
        from_openai_stream_event(SimpleNamespace(type="response.completed", response=final_response), sequence=1)
    )

    response = accumulator.to_response()

    assert isinstance(response.output_items[0], MessageItem)
    assert response.output_items[0].id == "msg_1"
    assert response.output_items[0].parts == (TextPart("final"),)
