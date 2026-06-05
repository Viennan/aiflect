"""Anthropic streaming event mapping."""

from __future__ import annotations

from typing import Any

from whero.vatbrain.core.generation import (
    GenerationResponse,
    GenerationStreamEvent,
    StreamEventType,
)
from whero.vatbrain.core.items import FunctionCallItem
from whero.vatbrain.providers.anthropic.mapper import (
    PROVIDER,
    from_anthropic_generation_response,
    usage_from_anthropic,
)


def from_anthropic_stream_event(event: Any, *, sequence: int) -> GenerationStreamEvent:
    """Convert one Anthropic stream event to a vatbrain stream event."""

    event_type = _get_attr(event, "type", None)
    metadata = _metadata_from_event(event, event_type)
    response_id = _message_id_from_event(event)

    if event_type == "message_start":
        message = _get_attr(event, "message", None)
        return GenerationStreamEvent(
            type=StreamEventType.RESPONSE_CREATED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=_get_attr(message, "id", response_id),
            response=_safe_response(message),
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "content_block_start":
        block = _get_attr(event, "content_block", None)
        block_type = _get_attr(block, "type", None)
        item_id = _get_attr(block, "id", _content_block_item_id(event))
        if block_type == "tool_use":
            item = FunctionCallItem(
                id=item_id,
                name=_get_attr(block, "name", ""),
                arguments="",
                call_id=_get_attr(block, "id", ""),
            )
            return GenerationStreamEvent(
                type=StreamEventType.ITEM_CREATED.value,
                sequence=sequence,
                provider=PROVIDER,
                response_id=response_id,
                item_id=item_id,
                item=item,
                metadata={
                    **metadata,
                    "name": item.name,
                    "call_id": item.call_id,
                    "semantic_type": StreamEventType.TOOL_CALL_CREATED.value,
                },
                raw_event=event,
            )
        if block_type in {"thinking", "redacted_thinking"}:
            return GenerationStreamEvent(
                type=StreamEventType.REASONING_CREATED.value,
                sequence=sequence,
                provider=PROVIDER,
                response_id=response_id,
                item_id=item_id,
                delta=block,
                metadata={**metadata, "reasoning_kind": block_type},
                raw_event=event,
            )
        return GenerationStreamEvent(
            type=StreamEventType.CONTENT_PART_CREATED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=block,
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "content_block_delta":
        delta = _get_attr(event, "delta", None)
        delta_type = _get_attr(delta, "type", None)
        item_id = _content_block_item_id(event)
        if delta_type == "text_delta":
            return GenerationStreamEvent(
                type=StreamEventType.TEXT_DELTA.value,
                sequence=sequence,
                provider=PROVIDER,
                response_id=response_id,
                item_id=item_id,
                delta=_get_attr(delta, "text", ""),
                metadata={**metadata, "semantic_type": StreamEventType.ITEM_DELTA.value},
                raw_event=event,
            )
        if delta_type == "input_json_delta":
            return GenerationStreamEvent(
                type=StreamEventType.TOOL_CALL_DELTA.value,
                sequence=sequence,
                provider=PROVIDER,
                response_id=response_id,
                item_id=item_id,
                delta=_get_attr(delta, "partial_json", ""),
                metadata=metadata,
                raw_event=event,
            )
        if delta_type in {"thinking_delta", "signature_delta"}:
            value = _get_attr(delta, "thinking", _get_attr(delta, "signature", ""))
            return GenerationStreamEvent(
                type=StreamEventType.REASONING_DELTA.value,
                sequence=sequence,
                provider=PROVIDER,
                response_id=response_id,
                item_id=item_id,
                delta=value,
                metadata={**metadata, "reasoning_delta_type": delta_type},
                raw_event=event,
            )
        return GenerationStreamEvent(
            type=StreamEventType.ITEM_DELTA.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=item_id,
            delta=delta,
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "content_block_stop":
        return GenerationStreamEvent(
            type=StreamEventType.CONTENT_PART_COMPLETED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            item_id=_content_block_item_id(event),
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "message_delta":
        delta = _get_attr(event, "delta", None)
        usage = usage_from_anthropic(_get_attr(event, "usage", None))
        if usage is not None:
            return GenerationStreamEvent(
                type=StreamEventType.USAGE_UPDATED.value,
                sequence=sequence,
                provider=PROVIDER,
                response_id=response_id,
                usage=usage,
                metadata={**metadata, "stop_reason": _get_attr(delta, "stop_reason", None)},
                raw_event=event,
            )
        return GenerationStreamEvent(
            type=StreamEventType.ITEM_DELTA.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            delta=delta,
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "message_stop":
        return GenerationStreamEvent(
            type=StreamEventType.RESPONSE_COMPLETED.value,
            sequence=sequence,
            provider=PROVIDER,
            response_id=response_id,
            metadata=metadata,
            raw_event=event,
        )
    if event_type == "error":
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
        metadata=metadata,
        raw_event=event,
    )


def _safe_response(response: Any | None) -> GenerationResponse | None:
    if response is None:
        return None
    try:
        return from_anthropic_generation_response(response)
    except Exception:
        return GenerationResponse(
            id=_get_attr(response, "id", None),
            provider=PROVIDER,
            model=_get_attr(response, "model", None),
            raw=response,
        )


def _message_id_from_event(event: Any) -> str | None:
    message = _get_attr(event, "message", None)
    if message is not None:
        return _get_attr(message, "id", None)
    return _get_attr(event, "message_id", _get_attr(event, "response_id", None))


def _content_block_item_id(event: Any) -> str:
    index = _get_attr(event, "index", _get_attr(event, "content_index", 0))
    return f"content_block_{index}"


def _metadata_from_event(event: Any, event_type: str | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {"provider_event_type": event_type}
    index = _get_attr(event, "index", _get_attr(event, "content_index", None))
    if index is not None:
        metadata["content_index"] = index
        metadata["output_index"] = index
    for name in ("message_id", "stop_reason", "stop_sequence"):
        value = _get_attr(event, name, None)
        if value is not None:
            metadata[name] = value
    delta = _get_attr(event, "delta", None)
    if delta is not None:
        delta_type = _get_attr(delta, "type", None)
        if delta_type is not None:
            metadata["delta_type"] = delta_type
    return metadata


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)
