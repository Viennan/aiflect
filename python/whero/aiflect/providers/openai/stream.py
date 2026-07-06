"""OpenAI streaming event mapping."""

from __future__ import annotations

from typing import Any

from whero.aiflect.core.generation import (
    GenerationResponse,
    GenerationStreamEvent,
    StreamEventType,
)
from whero.aiflect.core.items import FunctionCallItem
from whero.aiflect.core.tools import FunctionToolType
from whero.aiflect.providers.openai.mapper import PROVIDER, from_openai_generation_response, usage_from_openai


def from_openai_stream_event(event: Any, *, sequence: int) -> GenerationStreamEvent:
    """Convert one OpenAI stream event to an aiflect stream event."""

    event_type = _get_attr(event, "type", None)
    response_id = _response_id_from_event(event)
    item_id = _get_attr(event, "item_id", None)
    metadata = _metadata_from_event(event, event_type)

    if event_type == "response.created":
        response = _get_attr(event, "response", None)
        return GenerationStreamEvent(
            type=StreamEventType.RESPONSE_CREATED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=_get_attr(response, "id", response_id),
            response=_safe_response(response),
            metadata=metadata,
            raw_event=event,
        )
    if event_type in {"response.in_progress", "response.started", "response.queued"}:
        if event_type == "response.queued":
            metadata["status"] = "queued"
        return GenerationStreamEvent(
            type=StreamEventType.RESPONSE_STARTED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "response.output_item.added":
        item = _get_attr(event, "item", None)
        normalized_item = None
        item_type = _get_attr(item, "type", None)
        if item_type == "function_call":
            normalized_item = FunctionCallItem(
                id=_get_attr(item, "id", None),
                name=_get_attr(item, "name", ""),
                arguments=_get_attr(item, "arguments", ""),
                call_id=_get_attr(item, "call_id", ""),
                status=_get_attr(item, "status", None),
            )
        elif item_type == "custom_tool_call":
            input_text = _get_attr(item, "input", "")
            normalized_item = FunctionCallItem(
                id=_get_attr(item, "id", None),
                name=_get_attr(item, "name", ""),
                arguments=input_text,
                call_id=_get_attr(item, "call_id", ""),
                status=_get_attr(item, "status", None),
                type=FunctionToolType.CUSTOM,
                input=input_text,
            )
            metadata["tool_type"] = FunctionToolType.CUSTOM.value
        return GenerationStreamEvent(
            type=StreamEventType.ITEM_CREATED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=_get_attr(item, "id", item_id),
            item=normalized_item,
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "response.output_item.done":
        item = _get_attr(event, "item", None)
        normalized_item = None
        item_type = _get_attr(item, "type", None)
        if item_type == "function_call":
            normalized_item = FunctionCallItem(
                id=_get_attr(item, "id", None),
                name=_get_attr(item, "name", ""),
                arguments=_get_attr(item, "arguments", ""),
                call_id=_get_attr(item, "call_id", ""),
                status=_get_attr(item, "status", None),
            )
        elif item_type == "custom_tool_call":
            input_text = _get_attr(item, "input", "")
            normalized_item = FunctionCallItem(
                id=_get_attr(item, "id", None),
                name=_get_attr(item, "name", ""),
                arguments=input_text,
                call_id=_get_attr(item, "call_id", ""),
                status=_get_attr(item, "status", None),
                type=FunctionToolType.CUSTOM,
                input=input_text,
            )
            metadata["tool_type"] = FunctionToolType.CUSTOM.value
        return GenerationStreamEvent(
            type=StreamEventType.ITEM_COMPLETED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=_get_attr(item, "id", item_id),
            item=normalized_item,
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "response.content_part.added":
        return GenerationStreamEvent(
            type=StreamEventType.CONTENT_PART_CREATED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=_get_attr(event, "part", None),
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "response.content_part.done":
        return GenerationStreamEvent(
            type=StreamEventType.CONTENT_PART_COMPLETED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=_get_attr(event, "part", None),
            metadata=metadata,
            raw_event=event,
        )
    if event_type in {"response.output_text.delta", "response.text.delta"}:
        return GenerationStreamEvent(
            type=StreamEventType.TEXT_DELTA.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=_get_attr(event, "delta", ""),
            metadata={**metadata, "semantic_type": StreamEventType.ITEM_DELTA.value},
            raw_event=event,
        )
    if event_type == "response.output_text.done":
        text = _get_attr(event, "text", None)
        return GenerationStreamEvent(
            type=StreamEventType.TEXT_COMPLETED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=text,
            metadata=metadata,
            raw_event=event,
        )
    if event_type in {"response.function_call_arguments.delta", "response.tool_call.delta"}:
        return GenerationStreamEvent(
            type=StreamEventType.TOOL_CALL_DELTA.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=_get_attr(event, "delta", ""),
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "response.custom_tool_call_input.delta":
        return GenerationStreamEvent(
            type=StreamEventType.TOOL_CALL_DELTA.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=_get_attr(event, "delta", ""),
            metadata={**metadata, "tool_type": FunctionToolType.CUSTOM.value},
            raw_event=event,
        )
    if event_type in {"response.function_call_arguments.done", "response.tool_call.done"}:
        return GenerationStreamEvent(
            type=StreamEventType.TOOL_CALL_COMPLETED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=_get_attr(event, "arguments", None),
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "response.custom_tool_call_input.done":
        input_text = _get_attr(event, "input", _get_attr(event, "text", None))
        return GenerationStreamEvent(
            type=StreamEventType.TOOL_CALL_COMPLETED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=input_text,
            metadata={**metadata, "tool_type": FunctionToolType.CUSTOM.value},
            raw_event=event,
        )
    if event_type == "response.reasoning_summary_part.added":
        return GenerationStreamEvent(
            type=StreamEventType.REASONING_CREATED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=_get_attr(event, "part", None),
            metadata={**metadata, "reasoning_kind": "summary"},
            raw_event=event,
        )
    if event_type == "response.reasoning_summary_part.done":
        return GenerationStreamEvent(
            type=StreamEventType.REASONING_COMPLETED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=_get_attr(event, "part", None),
            metadata={**metadata, "reasoning_kind": "summary"},
            raw_event=event,
        )
    if event_type == "response.reasoning_summary_text.delta":
        return GenerationStreamEvent(
            type=StreamEventType.REASONING_DELTA.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=_get_attr(event, "delta", ""),
            metadata={**metadata, "reasoning_kind": "summary"},
            raw_event=event,
        )
    if event_type == "response.reasoning_summary_text.done":
        return GenerationStreamEvent(
            type=StreamEventType.REASONING_COMPLETED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=_get_attr(event, "text", None),
            metadata={**metadata, "reasoning_kind": "summary"},
            raw_event=event,
        )
    if event_type == "response.reasoning_text.delta":
        return GenerationStreamEvent(
            type=StreamEventType.REASONING_DELTA.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=_get_attr(event, "delta", ""),
            metadata={**metadata, "reasoning_kind": "text"},
            raw_event=event,
        )
    if event_type == "response.reasoning_text.done":
        return GenerationStreamEvent(
            type=StreamEventType.REASONING_COMPLETED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=_get_attr(event, "text", None),
            metadata={**metadata, "reasoning_kind": "text"},
            raw_event=event,
        )
    if event_type == "response.usage.updated":
        return GenerationStreamEvent(
            type=StreamEventType.USAGE_UPDATED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            usage=usage_from_openai(_get_attr(event, "usage", None)),
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "response.completed":
        response = _get_attr(event, "response", None)
        return GenerationStreamEvent(
            type=StreamEventType.RESPONSE_COMPLETED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=_get_attr(response, "id", response_id),
            response=_safe_response(response),
            usage=usage_from_openai(_get_attr(response, "usage", None)),
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "response.incomplete":
        response = _get_attr(event, "response", None)
        return GenerationStreamEvent(
            type=StreamEventType.RESPONSE_INCOMPLETE.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=_get_attr(response, "id", response_id),
            response=_safe_response(response),
            usage=usage_from_openai(_get_attr(response, "usage", None)),
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "response.failed":
        error = _get_attr(event, "error", None)
        response = _get_attr(event, "response", None)
        if error is None and response is not None:
            error = _get_attr(response, "error", None)
        return GenerationStreamEvent(
            type=StreamEventType.RESPONSE_FAILED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            error=str(error) if error is not None else None,
            response=_safe_response(response),
            metadata=metadata,
            raw_event=event,
        )
    if event_type in {"response.error", "error"}:
        error = _get_attr(event, "error", None)
        return GenerationStreamEvent(
            type=StreamEventType.RESPONSE_ERROR.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            error=str(error) if error is not None else None,
            metadata=metadata,
            raw_event=event,
        )
    return GenerationStreamEvent(
        type=StreamEventType.UNKNOWN.value,
        sequence=sequence,
        provider=PROVIDER,
        response_id=response_id,
        item_id=item_id,
        metadata=metadata,
        raw_event=event,
    )


def _safe_response(response: Any | None) -> GenerationResponse | None:
    if response is None:
        return None
    try:
        return from_openai_generation_response(response)
    except Exception:
        return GenerationResponse(
            id=_get_attr(response, "id", None),
            provider=PROVIDER,
            model=_get_attr(response, "model", None),
            raw=response,
        )


def _response_id_from_event(event: Any) -> str | None:
    response = _get_attr(event, "response", None)
    return _get_attr(response, "id", _get_attr(event, "response_id", None))


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _metadata_from_event(event: Any, event_type: str | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {"provider_event_type": event_type}
    for name in ("sequence_number", "output_index", "content_index", "status", "call_id", "name"):
        value = _get_attr(event, name, None)
        if value is not None:
            metadata[name] = value
    return metadata
