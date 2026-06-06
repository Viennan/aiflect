"""OpenAI request/response mapping functions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from whero.vatbrain.core.embeddings import (
    EmbeddingInput,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingVector,
)
from whero.vatbrain.core.errors import InvalidItemError, ProviderResponseMappingError, UnsupportedCapabilityError
from whero.vatbrain.core.generation import (
    GenerationConfig,
    GenerationRequest,
    GenerationResponse,
    ReasoningConfig,
    RemoteContextHint,
    ReplayMode,
    ReplayPolicy,
    ResponseFormat,
    ToolCallConfig,
)
from whero.vatbrain.core.items import (
    AssistantMessagePhase,
    FunctionCallItem,
    FunctionResultItem,
    ImagePart,
    Item,
    MessageItem,
    ProviderItemSnapshot,
    Role,
    TextPart,
    provider_response_id_for,
    provider_snapshot_for,
)
from whero.vatbrain.core.tools import FunctionToolSpec, FunctionToolType, ToolChoice, ToolSpec
from whero.vatbrain.core.usage import Usage

PROVIDER = "openai"
API_FAMILY = "responses"
_REMOTE_CONTEXT_RESERVED_OPTIONS = {"previous_response_id", "store"}


def to_openai_generation_params(
    request: GenerationRequest,
    *,
    stream: bool = False,
    use_remote_context: bool = True,
) -> dict[str, Any]:
    """Convert a vatbrain generation request into OpenAI Responses API parameters."""

    _reject_remote_context_reserved_options(request.provider_options, owner="GenerationRequest.provider_options")
    if request.remote_context is not None:
        _reject_remote_context_reserved_options(
            request.remote_context.provider_options,
            owner="RemoteContextHint.provider_options",
        )
    input_items, previous_response_id = _openai_input_items(
        request,
        use_remote_context=use_remote_context,
    )
    params: dict[str, Any] = {
        "model": request.model,
        "input": [_item_to_openai_input(item, request.replay_policy) for item in input_items],
    }
    if stream:
        params["stream"] = True
    if request.tools:
        params["tools"] = [_tool_to_openai_tool(tool) for tool in request.tools]
    if request.generation_config:
        params.update(_generation_config_to_params(request.generation_config))
    if request.response_format:
        params["text"] = _response_format_to_openai_text(request.response_format)
    if request.reasoning:
        reasoning = _reasoning_to_openai(request.reasoning)
        if reasoning:
            params["reasoning"] = reasoning
    if request.remote_context:
        params.update(
            _remote_context_to_openai(
                request.remote_context,
                previous_response_id=previous_response_id,
            )
        )
    if request.tool_call_config:
        params.update(_tool_call_config_to_params(request.tool_call_config))
    params.update(request.provider_options)
    if not use_remote_context:
        params.pop("previous_response_id", None)
    return params


def to_openai_embedding_params(request: EmbeddingRequest) -> dict[str, Any]:
    """Convert a vatbrain embedding request into OpenAI embedding parameters."""

    if request.instructions is not None:
        raise UnsupportedCapabilityError("OpenAI embedding adapter does not support instructions.")
    if request.sparse_embedding:
        raise UnsupportedCapabilityError("OpenAI embedding adapter does not support sparse embeddings.")
    params: dict[str, Any] = {
        "model": request.model,
        "input": [_embedding_input_to_text(item) for item in request.inputs],
    }
    if request.dimensions is not None:
        params["dimensions"] = request.dimensions
    if request.encoding_format is not None:
        params["encoding_format"] = request.encoding_format
    params.update(request.provider_options)
    return params


def from_openai_generation_response(response: Any) -> GenerationResponse:
    """Convert an OpenAI Responses API response into a vatbrain response."""

    response_id = _get_attr(response, "id", None)
    output_items: list[Item] = []
    unsupported_output_items: list[dict[str, Any]] = []
    for item in _get_attr(response, "output", []) or []:
        try:
            output_items.append(_openai_output_item_to_item(item, response_id=response_id))
        except ProviderResponseMappingError:
            unsupported_output_items.append(_unsupported_output_item_summary(item))
    if unsupported_output_items and not output_items:
        raise ProviderResponseMappingError(
            "OpenAI response contains only unsupported output item types.",
            provider=PROVIDER,
            operation="responses.create",
            raw=response,
        )
    metadata: dict[str, Any] = {}
    if unsupported_output_items:
        metadata["unsupported_output_items"] = unsupported_output_items
    return GenerationResponse(
        id=response_id,
        provider=PROVIDER,
        model=_get_attr(response, "model", None),
        output_items=tuple(output_items),
        stop_reason=_get_attr(response, "status", None),
        usage=usage_from_openai(_get_attr(response, "usage", None)),
        metadata=metadata,
        raw=response,
    )


def from_openai_embedding_response(response: Any) -> EmbeddingResponse:
    """Convert an OpenAI embedding response into a vatbrain embedding response."""

    vectors = tuple(
        EmbeddingVector(
            index=int(_get_attr(item, "index", index)),
            embedding=_embedding_value(_get_attr(item, "embedding", [])),
            raw=item,
        )
        for index, item in enumerate(_get_attr(response, "data", []) or [])
    )
    dimensions = len(vectors[0].embedding) if vectors and isinstance(vectors[0].embedding, list) else None
    return EmbeddingResponse(
        provider=PROVIDER,
        model=_get_attr(response, "model", None),
        vectors=vectors,
        dimensions=dimensions,
        usage=usage_from_openai(_get_attr(response, "usage", None)),
        raw=response,
    )


def usage_from_openai(usage: Any | None) -> Usage | None:
    """Normalize usage from OpenAI-like usage objects or dictionaries."""

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
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_tokens=cached_tokens,
        reasoning_tokens=reasoning_tokens,
        raw=usage,
    )


def _openai_input_items(
    request: GenerationRequest,
    *,
    use_remote_context: bool,
) -> tuple[tuple[Item, ...], str | None]:
    if not use_remote_context or request.remote_context is None:
        return request.items, None
    remote_context = request.remote_context
    if not remote_context.enable_cache or remote_context.new_items_start_index is None:
        return request.items, None
    if remote_context.new_items_start_index == 0:
        return request.items, None
    anchor_item = request.items[remote_context.new_items_start_index - 1]
    previous_response_id = provider_response_id_for(
        anchor_item,
        provider=PROVIDER,
        api_family=API_FAMILY,
    )
    if previous_response_id is None:
        return request.items, None
    suffix = request.items[remote_context.new_items_start_index :]
    if not suffix:
        raise InvalidItemError("OpenAI response cache delta requires at least one new item.")
    return suffix, previous_response_id


def _item_to_openai_input(item: Item, replay_policy: ReplayPolicy | None = None) -> dict[str, Any]:
    mode = replay_policy.mode if replay_policy is not None else ReplayMode.PREFER_PROVIDER_NATIVE
    if mode != ReplayMode.NORMALIZED_ONLY:
        snapshot = provider_snapshot_for(item, provider=PROVIDER, api_family=API_FAMILY)
        if snapshot is not None:
            return dict(snapshot.payload)
        if mode == ReplayMode.REQUIRE_PROVIDER_NATIVE:
            raise InvalidItemError("Provider-native replay requires an OpenAI Responses item snapshot.")
    if isinstance(item, MessageItem):
        return _message_to_openai_input(item)
    if isinstance(item, FunctionResultItem):
        return {
            "type": _function_result_type_to_openai(item),
            "call_id": item.call_id,
            "output": item.output,
        }
    if isinstance(item, FunctionCallItem):
        payload = {
            "type": _function_call_type_to_openai(item),
            "name": item.name,
            "call_id": item.call_id,
        }
        if item.type == FunctionToolType.CUSTOM:
            payload["input"] = item.input if item.input is not None else item.arguments
        else:
            payload["arguments"] = item.arguments
        return payload
    raise InvalidItemError(f"Unsupported generation item: {item!r}")


def _message_to_openai_input(item: MessageItem) -> dict[str, Any]:
    content = []
    for part in item.parts:
        if isinstance(part, TextPart):
            content.append({"type": _text_type_for_role(item.role), "text": part.text})
        elif isinstance(part, ImagePart):
            content.append(_image_part_to_openai(part))
        else:
            raise InvalidItemError(f"Unsupported message part: {part!r}")
    payload: dict[str, Any] = {"type": "message", "role": item.role.value, "content": content}
    if item.assistant_phase is not None:
        payload["phase"] = (
            item.assistant_phase.value
            if isinstance(item.assistant_phase, AssistantMessagePhase)
            else item.assistant_phase
        )
    return payload


def _text_type_for_role(role: Role) -> str:
    return "output_text" if role == Role.ASSISTANT else "input_text"


def _image_part_to_openai(part: ImagePart) -> dict[str, Any]:
    image_url = part.url
    if image_url is None and part.data is not None:
        if part.data.startswith("data:"):
            image_url = part.data
        else:
            mime_type = part.mime_type or "image/png"
            image_url = f"data:{mime_type};base64,{part.data}"
    payload: dict[str, Any] = {"type": "input_image", "image_url": image_url}
    if part.detail is not None:
        payload["detail"] = part.detail
    return payload


def _tool_to_openai_tool(tool: ToolSpec) -> dict[str, Any]:
    if not isinstance(tool, FunctionToolSpec):
        raise UnsupportedCapabilityError("OpenAI adapter currently maps function tools only.")
    if tool.type == FunctionToolType.CUSTOM:
        payload: dict[str, Any] = {
            "type": "custom",
            "name": tool.name,
        }
        if tool.description is not None:
            payload["description"] = tool.description
        return payload
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


def _response_format_to_openai_text(response_format: ResponseFormat) -> dict[str, Any]:
    payload = {
        "type": "json_schema",
        "name": response_format.json_schema_name or "response",
        "schema": response_format.json_schema,
    }
    if response_format.json_schema_name is not None:
        payload["name"] = response_format.json_schema_name
    if response_format.json_schema_description is not None:
        payload["description"] = response_format.json_schema_description
    if response_format.json_schema_strict is not None:
        payload["strict"] = response_format.json_schema_strict
    return {"format": payload}


def _reasoning_to_openai(reasoning: ReasoningConfig) -> dict[str, Any]:
    params: dict[str, Any] = dict(reasoning.provider_options)
    if reasoning.mode is not None:
        params["mode"] = reasoning.mode
    if reasoning.effort is not None:
        params["effort"] = reasoning.effort
    if reasoning.budget_tokens is not None:
        params["budget_tokens"] = reasoning.budget_tokens
    if reasoning.summary is not None:
        params["summary"] = reasoning.summary
    if reasoning.include_trace is not None:
        params["include_trace"] = reasoning.include_trace
    return params


def _remote_context_to_openai(
    remote_context: RemoteContextHint,
    *,
    previous_response_id: str | None = None,
) -> dict[str, Any]:
    params = dict(remote_context.provider_options)
    if previous_response_id is not None:
        params["previous_response_id"] = previous_response_id
    params["store"] = remote_context.enable_cache
    return params


def _reject_remote_context_reserved_options(options: Mapping[str, Any], *, owner: str) -> None:
    reserved = sorted(_REMOTE_CONTEXT_RESERVED_OPTIONS.intersection(options))
    if reserved:
        names = ", ".join(reserved)
        raise UnsupportedCapabilityError(
            f"{owner} cannot set {names}; use RemoteContextHint.enable_cache and "
            "RemoteContextHint.new_items_start_index."
        )


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


def _openai_output_item_to_item(item: Any, *, response_id: str | None) -> Item:
    item_type = _get_attr(item, "type", None)
    try:
        if item_type == "message":
            return _openai_message_to_item(item, response_id=response_id)
        if item_type == "function_call":
            return FunctionCallItem(
                id=_get_attr(item, "id", None),
                name=_get_attr(item, "name", ""),
                arguments=_get_attr(item, "arguments", ""),
                call_id=_get_attr(item, "call_id", ""),
                status=_get_attr(item, "status", None),
                provider_snapshots=(_provider_snapshot(item, replayable=True, response_id=response_id),),
            )
        if item_type == "custom_tool_call":
            input_text = _get_attr(item, "input", "")
            return FunctionCallItem(
                id=_get_attr(item, "id", None),
                name=_get_attr(item, "name", ""),
                arguments=input_text,
                call_id=_get_attr(item, "call_id", ""),
                status=_get_attr(item, "status", None),
                type=FunctionToolType.CUSTOM,
                input=input_text,
                provider_snapshots=(_provider_snapshot(item, replayable=True, response_id=response_id),),
            )
    except Exception as exc:
        raise ProviderResponseMappingError(
            f"Malformed OpenAI output item: {item_type!r}",
            provider=PROVIDER,
            operation="responses.create",
            raw=item,
            cause=exc,
        ) from exc
    raise ProviderResponseMappingError(
        f"Unsupported OpenAI output item type: {item_type!r}",
        provider=PROVIDER,
        operation="responses.create",
        raw=item,
    )


def _openai_message_to_item(item: Any, *, response_id: str | None) -> MessageItem:
    parts: list[TextPart] = []
    for content_item in _get_attr(item, "content", []) or []:
        content_type = _get_attr(content_item, "type", None)
        if content_type in {"output_text", "input_text", "text"}:
            parts.append(TextPart(_get_attr(content_item, "text", "")))
    if not parts:
        parts.append(TextPart(""))
    return MessageItem(
        Role(_get_attr(item, "role", Role.ASSISTANT.value)),
        parts,
        assistant_phase=_get_attr(item, "phase", None),
        id=_get_attr(item, "id", None),
        provider_snapshots=(_provider_snapshot(item, replayable=True, response_id=response_id),),
    )


def _embedding_input_to_text(item: EmbeddingInput) -> str:
    texts: list[str] = []
    for part in item.parts:
        if isinstance(part, TextPart):
            texts.append(part.text)
        else:
            raise InvalidItemError("OpenAI adapter v0.1 supports text embedding inputs only.")
    return "\n".join(texts)


def _function_call_type_to_openai(item: FunctionCallItem) -> str:
    return "custom_tool_call" if item.type == FunctionToolType.CUSTOM else "function_call"


def _function_result_type_to_openai(item: FunctionResultItem) -> str:
    return (
        "custom_tool_call_output"
        if item.tool_type == FunctionToolType.CUSTOM
        else "function_call_output"
    )


def _embedding_value(value: Any) -> list[float] | str:
    if isinstance(value, str):
        return value
    return list(value)


def _detail_token(usage: Any, detail_name: str, token_name: str) -> int | None:
    details = _get_attr(usage, detail_name, None)
    if details is None:
        return None
    return _get_attr(details, token_name, None)


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _provider_snapshot(
    item: Any,
    *,
    replayable: bool,
    response_id: str | None = None,
) -> ProviderItemSnapshot:
    payload = _to_plain_data(item)
    item_type = str(_get_attr(item, "type", payload.get("type", "")))
    metadata = {"response_id": response_id} if response_id else {}
    return ProviderItemSnapshot(
        provider=PROVIDER,
        api_family=API_FAMILY,
        item_type=item_type,
        payload=payload,
        replayable=replayable,
        captured_from="response",
        metadata=metadata,
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
        dumped = value.model_dump(exclude_none=True)
        return _to_plain_data(dumped)
    if hasattr(value, "to_dict"):
        return _to_plain_data(value.to_dict())
    if hasattr(value, "__dict__"):
        return {
            str(key): _to_plain_data(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return value


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
