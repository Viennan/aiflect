"""Volcengine Responses API request and response mapping."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from whero.vatbrain.core.errors import InvalidItemError, ProviderResponseMappingError, UnsupportedCapabilityError
from whero.vatbrain.core.generation import (
    GenerationConfig,
    GenerationRequest,
    GenerationResponse,
    ReplayMode,
    ReplayPolicy,
    ResponseFormat,
    ToolCallConfig,
)
from whero.vatbrain.core.items import (
    FilePart,
    FunctionCallItem,
    FunctionResultItem,
    ImagePart,
    Item,
    MessageItem,
    ProviderItemSnapshot,
    ReasoningItem,
    Role,
    TextPart,
    VideoPart,
    provider_snapshot_for,
)
from whero.vatbrain.core.tools import FunctionToolSpec, FunctionToolType, ToolChoice, ToolSpec
from whero.vatbrain.core.usage import Usage

PROVIDER = "volcengine"
API_FAMILY = "responses"

_RESPONSE_CREATE_SDK_PARAMS = {
    "input",
    "model",
    "instructions",
    "max_output_tokens",
    "parallel_tool_calls",
    "previous_response_id",
    "thinking",
    "store",
    "caching",
    "stream",
    "temperature",
    "text",
    "tool_choice",
    "tools",
    "top_p",
    "max_tool_calls",
    "expire_at",
    "extra_headers",
    "extra_query",
    "extra_body",
    "timeout",
    "reasoning",
    "session",
    "service_tier",
}


def to_volcengine_generation_params(
    request: GenerationRequest,
    *,
    stream: bool = False,
    use_remote_context: bool = True,
) -> dict[str, Any]:
    """Convert a vatbrain generation request into Ark Responses API parameters."""

    input_items = _volcengine_input_items(request, use_remote_context=use_remote_context)
    params: dict[str, Any] = {
        "model": request.model,
        "input": [_item_to_volcengine_input(item, request.replay_policy) for item in input_items],
    }
    if stream:
        params["stream"] = True
    if request.tools:
        params["tools"] = [_tool_to_volcengine_tool(tool) for tool in request.tools]
    if request.generation_config:
        params.update(_generation_config_to_params(request.generation_config))
    if request.response_format:
        params["text"] = _response_format_to_volcengine_text(request.response_format)
    if request.reasoning:
        reasoning_params = dict(request.reasoning.provider_options)
        if request.reasoning.mode is not None:
            params["thinking"] = {"type": request.reasoning.mode}
        if request.reasoning.effort is not None:
            reasoning_params["effort"] = request.reasoning.effort
        if reasoning_params:
            params["reasoning"] = reasoning_params
    if request.remote_context:
        _merge_sdk_provider_options(
            params,
            request.remote_context.provider_options,
            sdk_params=_RESPONSE_CREATE_SDK_PARAMS,
        )
        if use_remote_context and request.remote_context.previous_response_id is not None:
            params["previous_response_id"] = request.remote_context.previous_response_id
        if request.remote_context.store is not None:
            params["store"] = request.remote_context.store
    if request.tool_call_config:
        params.update(_tool_call_config_to_params(request.tool_call_config))
    _merge_sdk_provider_options(
        params,
        request.provider_options,
        sdk_params=_RESPONSE_CREATE_SDK_PARAMS,
    )
    if not use_remote_context:
        params.pop("previous_response_id", None)
    return params


def from_volcengine_generation_response(response: Any) -> GenerationResponse:
    """Convert an Ark Responses API response into a vatbrain response."""

    output_items: list[Item] = []
    unsupported_output_items: list[dict[str, Any]] = []
    for item in _get_attr(response, "output", []) or []:
        try:
            output_items.append(_volcengine_output_item_to_item(item))
        except ProviderResponseMappingError:
            unsupported_output_items.append(_unsupported_output_item_summary(item))
    if unsupported_output_items and not output_items:
        raise ProviderResponseMappingError(
            "Volcengine response contains only unsupported output item types.",
            provider=PROVIDER,
            operation="responses.create",
            raw=response,
        )
    metadata: dict[str, Any] = {}
    if unsupported_output_items:
        metadata["unsupported_output_items"] = unsupported_output_items
    return GenerationResponse(
        id=_get_attr(response, "id", None),
        provider=PROVIDER,
        model=_get_attr(response, "model", None),
        output_items=tuple(output_items),
        stop_reason=_get_attr(response, "status", None),
        usage=usage_from_volcengine(_get_attr(response, "usage", None)),
        metadata=metadata,
        raw=response,
    )


def usage_from_volcengine(usage: Any | None) -> Usage | None:
    """Normalize Ark usage objects or dictionaries."""

    if usage is None:
        return None
    input_tokens = _get_attr(usage, "input_tokens", None)
    if input_tokens is None:
        input_tokens = _get_attr(usage, "prompt_tokens", None)
    output_tokens = _get_attr(usage, "output_tokens", None)
    if output_tokens is None:
        output_tokens = _get_attr(usage, "completion_tokens", None)
    total_tokens = _get_attr(usage, "total_tokens", None)
    cached_tokens = _detail_token(usage, "input_tokens_details", "cached_tokens")
    reasoning_tokens = _detail_token(usage, "output_tokens_details", "reasoning_tokens")
    metadata: dict[str, Any] = {}
    for name in ("tool_usage", "tool_usage_details"):
        value = _get_attr(usage, name, None)
        if value is not None:
            metadata[name] = _to_plain_data(value)
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_tokens=cached_tokens,
        reasoning_tokens=reasoning_tokens,
        raw=usage,
        metadata=metadata,
    )


def _volcengine_input_items(request: GenerationRequest, *, use_remote_context: bool) -> tuple[Item, ...]:
    if not use_remote_context or request.remote_context is None:
        return request.items
    remote_context = request.remote_context
    if remote_context.previous_response_id is None:
        return request.items
    if remote_context.covered_item_count is None:
        raise InvalidItemError(
            "Volcengine previous_response_id replay requires "
            "RemoteContextHint.covered_item_count."
        )
    if remote_context.covered_item_count > len(request.items):
        raise InvalidItemError(
            "RemoteContextHint.covered_item_count exceeds GenerationRequest.items length."
        )
    suffix = request.items[remote_context.covered_item_count :]
    if not suffix:
        raise InvalidItemError("Volcengine previous_response_id replay requires at least one new item.")
    return suffix


def _item_to_volcengine_input(item: Item, replay_policy: ReplayPolicy | None = None) -> dict[str, Any]:
    mode = replay_policy.mode if replay_policy is not None else ReplayMode.PREFER_PROVIDER_NATIVE
    if mode != ReplayMode.NORMALIZED_ONLY:
        snapshot = provider_snapshot_for(item, provider=PROVIDER, api_family=API_FAMILY)
        if snapshot is not None:
            return dict(snapshot.payload)
        if mode == ReplayMode.REQUIRE_PROVIDER_NATIVE:
            raise InvalidItemError("Provider-native replay requires a Volcengine Responses item snapshot.")
    if isinstance(item, MessageItem):
        return _message_to_volcengine_input(item)
    if isinstance(item, FunctionResultItem):
        payload: dict[str, Any] = {
            "type": "function_call_output",
            "call_id": item.call_id,
            "output": item.output,
        }
        if "status" in item.metadata:
            payload["status"] = item.metadata["status"]
        return payload
    if isinstance(item, FunctionCallItem):
        if item.type != FunctionToolType.FUNCTION:
            raise UnsupportedCapabilityError("Volcengine adapter maps function tool calls only.")
        return {
            "type": "function_call",
            "name": item.name,
            "call_id": item.call_id,
            "arguments": item.arguments,
            **({"id": item.id} if item.id is not None else {}),
            **({"status": item.status} if item.status is not None else {}),
        }
    if isinstance(item, ReasoningItem):
        return _reasoning_item_to_volcengine_input(item)
    raise InvalidItemError(f"Unsupported generation item: {item!r}")


def _message_to_volcengine_input(item: MessageItem) -> dict[str, Any]:
    content = []
    for part in item.parts:
        if isinstance(part, TextPart):
            content.append({"type": _text_type_for_role(item.role), "text": part.text})
        elif isinstance(part, ImagePart):
            content.append(_image_part_to_volcengine(part))
        elif isinstance(part, VideoPart):
            content.append(_video_part_to_volcengine(part))
        elif isinstance(part, FilePart):
            content.append(_file_part_to_volcengine(part))
        else:
            raise InvalidItemError(f"Unsupported message part: {part!r}")
    payload: dict[str, Any] = {"type": "message", "role": item.role.value, "content": content}
    if "partial" in item.metadata:
        payload["partial"] = item.metadata["partial"]
    if "status" in item.metadata:
        payload["status"] = item.metadata["status"]
    return payload


def _text_type_for_role(role: Role) -> str:
    return "output_text" if role == Role.ASSISTANT else "input_text"


def _image_part_to_volcengine(part: ImagePart) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "input_image", "detail": part.detail or "auto"}
    payload["image_url"] = _data_url(part.data, part.mime_type or "image/png") if part.data else part.url
    return payload


def _video_part_to_volcengine(part: VideoPart) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "input_video"}
    if part.file_id:
        payload["file_id"] = part.file_id
    else:
        payload["video_url"] = _data_url(part.data, part.mime_type or "video/mp4") if part.data else part.url
    if part.fps is not None:
        payload["fps"] = part.fps
    return payload


def _file_part_to_volcengine(part: FilePart) -> dict[str, Any]:
    media_type = (part.media_type or part.mime_type or "").lower()
    if media_type.startswith("image"):
        payload: dict[str, Any] = {"type": "input_image", "detail": part.metadata.get("detail", "auto")}
        if part.file_id:
            payload["file_id"] = part.file_id
        else:
            payload["image_url"] = _data_url(part.data, part.mime_type or "image/png") if part.data else part.url
        return payload
    if media_type.startswith("video"):
        payload = {"type": "input_video"}
        if part.file_id:
            payload["file_id"] = part.file_id
        else:
            payload["video_url"] = _data_url(part.data, part.mime_type or "video/mp4") if part.data else part.url
        if "fps" in part.metadata:
            payload["fps"] = part.metadata["fps"]
        return payload
    payload = {"type": "input_file"}
    if part.file_id:
        payload["file_id"] = part.file_id
    elif part.url:
        payload["file_url"] = part.url
    elif part.data:
        payload["file_data"] = _data_url(part.data, part.mime_type or "application/octet-stream")
    else:
        raise InvalidItemError("FilePart.local_path is metadata only; upload the file explicitly first.")
    if part.filename is not None:
        payload["filename"] = part.filename
    return payload


def _reasoning_item_to_volcengine_input(item: ReasoningItem) -> dict[str, Any]:
    summary_text = item.summary if item.summary is not None else item.text
    payload: dict[str, Any] = {
        "type": "reasoning",
        "summary": [{"type": "summary_text", "text": summary_text or ""}],
    }
    if item.id is not None:
        payload["id"] = item.id
    if item.status is not None:
        payload["status"] = item.status
    return payload


def _tool_to_volcengine_tool(tool: ToolSpec) -> dict[str, Any]:
    if not isinstance(tool, FunctionToolSpec):
        raise UnsupportedCapabilityError("Volcengine adapter currently maps function tools only.")
    if tool.type != FunctionToolType.FUNCTION:
        raise UnsupportedCapabilityError("Volcengine adapter does not support custom tools.")
    payload: dict[str, Any] = {
        "type": "function",
        "name": tool.name,
        "parameters": tool.parameters_schema or {"type": "object", "properties": {}},
    }
    if tool.description is not None:
        payload["description"] = tool.description
    if tool.strict is not None:
        payload["strict"] = tool.strict
    return payload


def _generation_config_to_params(config: GenerationConfig) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if config.temperature is not None:
        params["temperature"] = config.temperature
    if config.top_p is not None:
        params["top_p"] = config.top_p
    if config.max_output_tokens is not None:
        params["max_output_tokens"] = config.max_output_tokens
    return params


def _response_format_to_volcengine_text(response_format: ResponseFormat) -> dict[str, Any]:
    payload = {
        "type": "json_schema",
        "name": response_format.json_schema_name or "response",
        "schema": response_format.json_schema,
    }
    if response_format.json_schema_description is not None:
        payload["description"] = response_format.json_schema_description
    if response_format.json_schema_strict is not None:
        payload["strict"] = response_format.json_schema_strict
    return {"format": payload}


def _tool_call_config_to_params(config: ToolCallConfig) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if config.parallel_tool_calls is not None:
        params["parallel_tool_calls"] = config.parallel_tool_calls
    if config.tool_choice is not None:
        params["tool_choice"] = (
            config.tool_choice.value
            if isinstance(config.tool_choice, ToolChoice)
            else config.tool_choice
        )
    return params


def _volcengine_output_item_to_item(item: Any) -> Item:
    item_type = _get_attr(item, "type", None)
    try:
        if item_type == "message":
            return _volcengine_message_to_item(item)
        if item_type == "function_call":
            return FunctionCallItem(
                id=_get_attr(item, "id", None),
                name=_get_attr(item, "name", ""),
                arguments=_get_attr(item, "arguments", ""),
                call_id=_get_attr(item, "call_id", ""),
                status=_get_attr(item, "status", None),
                provider_snapshots=(_provider_snapshot(item, replayable=True),),
            )
        if item_type == "function_call_output":
            return FunctionResultItem(
                id=_get_attr(item, "id", None),
                call_id=_get_attr(item, "call_id", ""),
                output=_get_attr(item, "output", ""),
                provider_snapshots=(_provider_snapshot(item, replayable=True),),
            )
        if item_type == "reasoning":
            return _volcengine_reasoning_to_item(item)
    except Exception as exc:
        raise ProviderResponseMappingError(
            f"Malformed Volcengine output item: {item_type!r}",
            provider=PROVIDER,
            operation="responses.create",
            raw=item,
            cause=exc,
        ) from exc
    raise ProviderResponseMappingError(
        f"Unsupported Volcengine output item type: {item_type!r}",
        provider=PROVIDER,
        operation="responses.create",
        raw=item,
    )


def _volcengine_message_to_item(item: Any) -> MessageItem:
    parts: list[TextPart] = []
    content = _get_attr(item, "content", []) or []
    if isinstance(content, str):
        parts.append(TextPart(content))
    else:
        for content_item in content:
            content_type = _get_attr(content_item, "type", None)
            if content_type in {"output_text", "input_text", "text"}:
                parts.append(TextPart(_get_attr(content_item, "text", "")))
    if not parts:
        parts.append(TextPart(""))
    return MessageItem(
        Role(_get_attr(item, "role", Role.ASSISTANT.value)),
        parts,
        id=_get_attr(item, "id", None),
        provider_snapshots=(_provider_snapshot(item, replayable=True),),
    )


def _volcengine_reasoning_to_item(item: Any) -> ReasoningItem:
    summaries = []
    for summary in _get_attr(item, "summary", []) or []:
        text = _get_attr(summary, "text", None)
        if text:
            summaries.append(str(text))
    summary_text = "\n".join(summaries) if summaries else None
    return ReasoningItem(
        summary=summary_text,
        provider=PROVIDER,
        visibility="summary",
        can_be_replayed=True,
        id=_get_attr(item, "id", None),
        status=_get_attr(item, "status", None),
        raw=item,
        provider_snapshots=(_provider_snapshot(item, replayable=True),),
    )


def _detail_token(usage: Any, detail_name: str, token_name: str) -> int | None:
    details = _get_attr(usage, detail_name, None)
    if details is None:
        return None
    return _get_attr(details, token_name, None)


def _merge_sdk_provider_options(
    params: dict[str, Any],
    options: Mapping[str, Any],
    *,
    sdk_params: set[str],
) -> None:
    extra_body = dict(params.get("extra_body", {}) or {})
    for key, value in options.items():
        if key == "extra_body":
            extra_body.update(dict(value or {}))
        elif key in sdk_params:
            params[key] = value
        else:
            extra_body[key] = value
    if extra_body:
        params["extra_body"] = extra_body


def _data_url(data: str | None, mime_type: str) -> str | None:
    if data is None:
        return None
    if data.startswith("data:"):
        return data
    return f"data:{mime_type};base64,{data}"


def _provider_snapshot(item: Any, *, replayable: bool) -> ProviderItemSnapshot:
    payload = _to_plain_data(item)
    item_type = str(_get_attr(item, "type", payload.get("type", "")))
    return ProviderItemSnapshot(
        provider=PROVIDER,
        api_family=API_FAMILY,
        item_type=item_type,
        payload=payload,
        replayable=replayable,
        captured_from="response",
    )


def _to_plain_data(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain_data(item) for item in value]
    if isinstance(value, tuple):
        return [_to_plain_data(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "model_dump"):
        return _to_plain_data(value.model_dump(exclude_none=True))
    if hasattr(value, "to_dict"):
        return _to_plain_data(value.to_dict())
    if hasattr(value, "__dict__"):
        return {
            str(key): _to_plain_data(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return value


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _unsupported_output_item_summary(item: Any) -> dict[str, Any]:
    return {
        "id": _get_attr(item, "id", None),
        "type": _get_attr(item, "type", None),
        "status": _get_attr(item, "status", None),
    }


def json_arguments(arguments: Mapping[str, Any] | str) -> str:
    """Serialize tool call arguments consistently."""

    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
