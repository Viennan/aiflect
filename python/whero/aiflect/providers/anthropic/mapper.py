"""Anthropic Messages API request and response mapping."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from whero.aiflect.core.errors import InvalidItemError, ProviderResponseMappingError, UnsupportedCapabilityError
from whero.aiflect.core.generation import (
    GenerationConfig,
    GenerationRequest,
    GenerationResponse,
    ReplayMode,
    ReplayPolicy,
    ResponseFormat,
    ReasoningConfig,
    ToolCallConfig,
)
from whero.aiflect.core.items import (
    AudioPart,
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
from whero.aiflect.core.tools import FunctionToolSpec, FunctionToolType, ToolChoice, ToolSpec
from whero.aiflect.core.usage import Usage

PROVIDER = "anthropic"
API_FAMILY = "messages"
_CACHE_CONTROL = "cache_control"
_OUTPUT_CONFIG = "output_config"
_OUTPUT_FORMAT = "output_format"
_THINKING = "thinking"
_MIN_THINKING_BUDGET_TOKENS = 1024
_REASONING_MODES = {"enabled", "auto", "adaptive", "disabled", "none"}
_REASONING_EFFORTS = {"low", "medium", "high", "max", "xhigh"}


def to_anthropic_generation_params(
    request: GenerationRequest,
    *,
    stream: bool = False,
) -> dict[str, Any]:
    """Convert an aiflect generation request into Anthropic Messages API parameters."""

    _reject_explicit_cache_control(request.provider_options, owner="GenerationRequest.provider_options")
    _reject_explicit_structured_output_options(
        request.provider_options,
        owner="GenerationRequest.provider_options",
    )
    if request.remote_context is not None:
        _reject_explicit_cache_control(
            request.remote_context.provider_options,
            owner="RemoteContextHint.provider_options",
        )
        _reject_explicit_structured_output_options(
            request.remote_context.provider_options,
            owner="RemoteContextHint.provider_options",
        )
    if request.reasoning is not None:
        _reject_reasoning_provider_option_conflicts(request.provider_options)

    system, messages = _items_to_anthropic_messages(request.items, request.replay_policy)
    if request.response_format is not None:
        _reject_structured_output_prefill(messages)
    params: dict[str, Any] = {
        "model": request.model,
        "messages": messages,
    }
    if system:
        params["system"] = system
    if stream:
        params["stream"] = True
    if request.tools:
        params["tools"] = [_tool_to_anthropic_tool(tool) for tool in request.tools]
    if request.generation_config:
        params.update(_generation_config_to_params(request.generation_config))
    if request.response_format:
        _merge_mapped_params(
            params,
            {_OUTPUT_CONFIG: _response_format_to_anthropic_output_config(request.response_format)},
        )
    if request.tool_call_config:
        params.update(_tool_call_config_to_params(request.tool_call_config))
    params.update(request.provider_options)
    if request.remote_context is not None and request.remote_context.enable_cache is True:
        params[_CACHE_CONTROL] = {"type": "ephemeral"}
    if params.get("max_tokens") is None:
        raise InvalidItemError(
            "Anthropic Messages API requires max_tokens; set "
            "GenerationConfig.max_output_tokens or provider_options['max_tokens']."
        )
    if request.reasoning is not None:
        _reject_active_reasoning_incompatibilities(request.reasoning, messages=messages, params=params)
        _merge_mapped_params(
            params,
            _reasoning_config_to_anthropic_params(
                request.reasoning,
                max_tokens=params.get("max_tokens"),
            ),
        )
    return params


def from_anthropic_generation_response(response: Any) -> GenerationResponse:
    """Convert an Anthropic Messages API response into an aiflect response."""

    output_items: list[Item] = []
    unsupported_blocks: list[dict[str, Any]] = []
    for index, block in enumerate(_get_attr(response, "content", []) or []):
        try:
            output_items.append(_anthropic_content_block_to_item(block, index=index))
        except ProviderResponseMappingError:
            unsupported_blocks.append(_unsupported_block_summary(block, index=index))
    if unsupported_blocks and not output_items:
        raise ProviderResponseMappingError(
            "Anthropic response contains only unsupported content block types.",
            provider=PROVIDER,
            operation="messages.create",
            raw=response,
        )
    metadata: dict[str, Any] = {}
    if unsupported_blocks:
        metadata["unsupported_content_blocks"] = unsupported_blocks
    return GenerationResponse(
        id=_get_attr(response, "id", None),
        provider=PROVIDER,
        model=_get_attr(response, "model", None),
        output_items=tuple(output_items),
        stop_reason=_get_attr(response, "stop_reason", None),
        usage=usage_from_anthropic(_get_attr(response, "usage", None)),
        metadata=metadata,
        raw=response,
    )


def usage_from_anthropic(usage: Any | None) -> Usage | None:
    """Normalize Anthropic usage objects or dictionaries."""

    if usage is None:
        return None
    provider_input_tokens = _get_attr(usage, "input_tokens", None)
    output_tokens = _get_attr(usage, "output_tokens", None)
    output_token_details = _get_attr(usage, "output_tokens_details", None)
    reasoning_tokens = _get_attr(output_token_details, "thinking_tokens", None)
    cache_creation = _get_attr(usage, "cache_creation_input_tokens", None)
    cache_read = _get_attr(usage, "cache_read_input_tokens", None)
    input_tokens = _sum_known(provider_input_tokens, cache_creation, cache_read)
    total_tokens = _sum_known(input_tokens, output_tokens)
    metadata: dict[str, Any] = {}
    if provider_input_tokens is not None:
        metadata["provider_input_tokens"] = provider_input_tokens
    if cache_creation is not None:
        metadata["cache_creation_input_tokens"] = cache_creation
    if cache_read is not None:
        metadata["cache_read_input_tokens"] = cache_read
    if output_token_details is not None:
        metadata["output_tokens_details"] = _to_plain_data(output_token_details)
    for name in ("cache_creation", "server_tool_use", "service_tier"):
        value = _get_attr(usage, name, None)
        if value is not None:
            metadata[name] = _to_plain_data(value)
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_tokens=cache_read,
        reasoning_tokens=reasoning_tokens,
        raw=usage,
        metadata=metadata,
    )


def _items_to_anthropic_messages(
    items: tuple[Item, ...],
    replay_policy: ReplayPolicy | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    system_blocks: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []
    current_role: str | None = None
    current_content: list[dict[str, Any]] = []
    in_initial_system_prefix = True

    def flush() -> None:
        nonlocal current_role, current_content
        if current_role is not None:
            messages.append({"role": current_role, "content": current_content})
        current_role = None
        current_content = []

    for item in items:
        if _is_system_instruction_item(item):
            if not in_initial_system_prefix:
                raise InvalidItemError(
                    "Anthropic adapter supports system/developer messages only "
                    "as the initial instruction prefix."
                )
            system_blocks.extend(_message_to_anthropic_system_blocks(item, replay_policy))
            continue
        in_initial_system_prefix = False
        role, blocks = _item_to_anthropic_message_blocks(item, replay_policy)
        if current_role != role:
            flush()
            current_role = role
            current_content = []
        current_content.extend(blocks)
    flush()
    if not messages:
        raise InvalidItemError("Anthropic generation requires at least one non-system message item.")
    return system_blocks, messages


def _is_system_instruction_item(item: Item) -> bool:
    return isinstance(item, MessageItem) and item.role in {Role.SYSTEM, Role.DEVELOPER}


def _message_to_anthropic_system_blocks(
    item: MessageItem,
    replay_policy: ReplayPolicy | None,
) -> list[dict[str, Any]]:
    blocks = _provider_snapshot_blocks(item, replay_policy)
    if blocks is not None:
        return blocks
    result: list[dict[str, Any]] = []
    for part in item.parts:
        if isinstance(part, TextPart):
            result.append({"type": "text", "text": part.text})
        else:
            raise InvalidItemError("Anthropic system/developer messages support text parts only.")
    return result


def _item_to_anthropic_message_blocks(
    item: Item,
    replay_policy: ReplayPolicy | None,
) -> tuple[str, list[dict[str, Any]]]:
    blocks = _provider_snapshot_blocks(item, replay_policy)
    if blocks is not None:
        return _role_for_item(item), blocks
    if isinstance(item, MessageItem):
        if item.role == Role.USER:
            return "user", _message_to_anthropic_content_blocks(item)
        if item.role == Role.ASSISTANT:
            return "assistant", _message_to_anthropic_content_blocks(item)
        raise InvalidItemError(f"Unsupported Anthropic message role: {item.role.value!r}")
    if isinstance(item, FunctionCallItem):
        return "assistant", [_function_call_to_anthropic_tool_use(item)]
    if isinstance(item, FunctionResultItem):
        return "user", [_function_result_to_anthropic_tool_result(item)]
    if isinstance(item, ReasoningItem):
        raise UnsupportedCapabilityError(
            "Anthropic reasoning replay currently requires provider-native snapshots."
        )
    raise InvalidItemError(f"Unsupported Anthropic generation item: {item!r}")


def _role_for_item(item: Item) -> str:
    if isinstance(item, FunctionResultItem):
        return "user"
    if isinstance(item, MessageItem):
        if item.role == Role.USER:
            return "user"
        if item.role == Role.ASSISTANT:
            return "assistant"
    if isinstance(item, (FunctionCallItem, ReasoningItem)):
        return "assistant"
    raise InvalidItemError(f"Unsupported Anthropic generation item: {item!r}")


def _provider_snapshot_blocks(
    item: Item,
    replay_policy: ReplayPolicy | None,
) -> list[dict[str, Any]] | None:
    mode = replay_policy.mode if replay_policy is not None else ReplayMode.PREFER_PROVIDER_NATIVE
    if mode == ReplayMode.NORMALIZED_ONLY:
        return None
    snapshot = provider_snapshot_for(item, provider=PROVIDER, api_family=API_FAMILY)
    if snapshot is not None:
        return [_snapshot_payload_to_content_block(snapshot.payload)]
    if mode == ReplayMode.REQUIRE_PROVIDER_NATIVE:
        raise InvalidItemError("Provider-native replay requires an Anthropic Messages snapshot.")
    return None


def _snapshot_payload_to_content_block(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("role") in {"user", "assistant"} and "content" in payload:
        raise InvalidItemError(
            "Anthropic replay snapshots must contain content blocks, not full messages."
        )
    return dict(payload)


def _message_to_anthropic_content_blocks(item: MessageItem) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for part in item.parts:
        if isinstance(part, TextPart):
            blocks.append({"type": "text", "text": part.text})
        elif isinstance(part, ImagePart):
            if item.role != Role.USER:
                raise InvalidItemError("Anthropic image input is supported for user messages only.")
            blocks.append(_image_part_to_anthropic(part))
        elif isinstance(part, (AudioPart, VideoPart, FilePart)):
            raise InvalidItemError(f"Anthropic adapter does not support {type(part).__name__}.")
        else:
            raise InvalidItemError(f"Unsupported Anthropic message part: {part!r}")
    return blocks


def _image_part_to_anthropic(part: ImagePart) -> dict[str, Any]:
    if part.url is not None:
        return {"type": "image", "source": {"type": "url", "url": part.url}}
    if part.data is None:
        raise InvalidItemError("ImagePart requires url or data.")
    media_type, data = _split_data_url(part.data, part.mime_type or "image/png")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": data,
        },
    }


def _split_data_url(data: str, default_mime_type: str) -> tuple[str, str]:
    if not data.startswith("data:"):
        return default_mime_type, data
    header, _, payload = data.partition(",")
    if not payload:
        raise InvalidItemError("Malformed ImagePart data URL.")
    mime_type = header.removeprefix("data:").split(";", maxsplit=1)[0] or default_mime_type
    return mime_type, payload


def _function_call_to_anthropic_tool_use(item: FunctionCallItem) -> dict[str, Any]:
    if item.type != FunctionToolType.FUNCTION:
        raise UnsupportedCapabilityError("Anthropic adapter supports function tool calls only.")
    try:
        parsed_input = json.loads(item.arguments or "{}")
    except json.JSONDecodeError as exc:
        raise InvalidItemError("Anthropic tool_use replay requires JSON object arguments.") from exc
    if not isinstance(parsed_input, Mapping):
        raise InvalidItemError("Anthropic tool_use replay requires JSON object arguments.")
    return {
        "type": "tool_use",
        "id": item.call_id,
        "name": item.name,
        "input": dict(parsed_input),
    }


def _function_result_to_anthropic_tool_result(item: FunctionResultItem) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "tool_result",
        "tool_use_id": item.call_id,
        "content": item.output,
    }
    if "is_error" in item.metadata:
        payload["is_error"] = item.metadata["is_error"]
    return payload


def _tool_to_anthropic_tool(tool: ToolSpec) -> dict[str, Any]:
    if not isinstance(tool, FunctionToolSpec):
        raise UnsupportedCapabilityError("Anthropic adapter currently maps function tools only.")
    _reject_explicit_cache_control(tool.provider_options, owner=f"ToolSpec({tool.name!r}).provider_options")
    if tool.type != FunctionToolType.FUNCTION:
        raise UnsupportedCapabilityError("Anthropic adapter does not support custom tools.")
    payload: dict[str, Any] = {
        "name": tool.name,
        "input_schema": tool.parameters_schema or {"type": "object", "properties": {}},
    }
    if tool.description is not None:
        payload["description"] = tool.description
    if tool.strict is not None:
        payload["strict"] = tool.strict
    payload.update(tool.provider_options)
    return payload


def _generation_config_to_params(config: GenerationConfig) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if config.temperature is not None:
        params["temperature"] = config.temperature
    if config.top_p is not None:
        params["top_p"] = config.top_p
    if config.max_output_tokens is not None:
        params["max_tokens"] = config.max_output_tokens
    return params


def _response_format_to_anthropic_output_config(response_format: ResponseFormat) -> dict[str, Any]:
    return {
        "format": {
            "type": "json_schema",
            "schema": response_format.json_schema,
        }
    }


def _reasoning_config_to_anthropic_params(
    config: ReasoningConfig,
    *,
    max_tokens: Any,
) -> dict[str, Any]:
    if config.provider_options:
        raise UnsupportedCapabilityError("Anthropic reasoning provider_options are not supported.")
    if config.include_trace is not None:
        raise UnsupportedCapabilityError("Anthropic reasoning include_trace is not supported.")

    mode = _reasoning_mode(config)
    if mode in {"disabled", "none"}:
        _reject_disabled_reasoning_conflicts(config)
        return {_THINKING: {"type": "disabled"}}
    if not _has_reasoning_controls(config):
        return {}

    params: dict[str, Any] = {}
    thinking: dict[str, Any]
    if config.budget_tokens is not None:
        if mode == "adaptive":
            raise UnsupportedCapabilityError(
                "Anthropic adaptive thinking cannot use budget_tokens."
            )
        _validate_thinking_budget(config.budget_tokens, max_tokens=max_tokens)
        thinking = {"type": "enabled", "budget_tokens": config.budget_tokens}
    else:
        thinking = {"type": "adaptive"}

    if config.summary is not None:
        thinking["display"] = _reasoning_summary_to_display(config.summary)
    params[_THINKING] = thinking

    if config.effort is not None:
        effort = config.effort.lower()
        if effort not in _REASONING_EFFORTS:
            supported = ", ".join(sorted(_REASONING_EFFORTS))
            raise UnsupportedCapabilityError(
                f"Anthropic reasoning effort supports {supported} only."
            )
        params[_OUTPUT_CONFIG] = {"effort": effort}
    return params


def _merge_mapped_params(params: dict[str, Any], mapped: Mapping[str, Any]) -> None:
    for key, value in mapped.items():
        if key in params and isinstance(params[key], Mapping) and isinstance(value, Mapping):
            params[key] = {**params[key], **value}
        else:
            params[key] = value


def _tool_call_config_to_params(config: ToolCallConfig) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if config.tool_choice is not None:
        params["tool_choice"] = _tool_choice_to_anthropic(config.tool_choice)
    if config.parallel_tool_calls is False:
        tool_choice = dict(params.get("tool_choice", {"type": "auto"}))
        tool_choice["disable_parallel_tool_use"] = True
        params["tool_choice"] = tool_choice
    elif config.parallel_tool_calls is True and "tool_choice" in params:
        tool_choice = dict(params["tool_choice"])
        tool_choice.setdefault("disable_parallel_tool_use", False)
        params["tool_choice"] = tool_choice
    return params


def _tool_choice_to_anthropic(choice: ToolChoice | str | dict[str, Any]) -> dict[str, Any] | str:
    if isinstance(choice, Mapping):
        return dict(choice)
    try:
        normalized = ToolChoice(choice)
    except ValueError:
        return str(choice)
    if normalized == ToolChoice.AUTO:
        return {"type": "auto"}
    if normalized == ToolChoice.NONE:
        return {"type": "none"}
    if normalized == ToolChoice.REQUIRED:
        return {"type": "any"}
    return normalized.value


def _anthropic_content_block_to_item(block: Any, *, index: int) -> Item:
    block_type = _get_attr(block, "type", None)
    try:
        if block_type == "text":
            return MessageItem(
                Role.ASSISTANT,
                [TextPart(_get_attr(block, "text", ""))],
                id=_block_item_id(block, index),
                provider_snapshots=(_provider_snapshot(block, replayable=True),),
            )
        if block_type == "tool_use":
            return FunctionCallItem(
                id=_block_item_id(block, index),
                name=_get_attr(block, "name", ""),
                arguments=json_arguments(_get_attr(block, "input", {})),
                call_id=_get_attr(block, "id", ""),
                provider_snapshots=(_provider_snapshot(block, replayable=True),),
            )
        if block_type in {"thinking", "redacted_thinking"}:
            return ReasoningItem(
                text=_get_attr(block, "thinking", None),
                provider=PROVIDER,
                visibility="provider",
                can_be_replayed=True,
                id=_block_item_id(block, index),
                raw=block,
                provider_snapshots=(_provider_snapshot(block, replayable=True),),
            )
    except Exception as exc:
        raise ProviderResponseMappingError(
            f"Malformed Anthropic content block: {block_type!r}",
            provider=PROVIDER,
            operation="messages.create",
            raw=block,
            cause=exc,
        ) from exc
    raise ProviderResponseMappingError(
        f"Unsupported Anthropic content block type: {block_type!r}",
        provider=PROVIDER,
        operation="messages.create",
        raw=block,
    )


def _block_item_id(block: Any, index: int) -> str | None:
    block_id = _get_attr(block, "id", None)
    if block_id is not None:
        return block_id
    return f"content_block_{index}"


def _provider_snapshot(block: Any, *, replayable: bool) -> ProviderItemSnapshot:
    payload = _to_plain_data(block)
    block_type = str(_get_attr(block, "type", payload.get("type", "")))
    return ProviderItemSnapshot(
        provider=PROVIDER,
        api_family=API_FAMILY,
        item_type=block_type,
        payload=payload,
        replayable=replayable,
        captured_from="response",
    )


def _reject_explicit_cache_control(options: Mapping[str, Any], *, owner: str) -> None:
    if _CACHE_CONTROL in options:
        raise UnsupportedCapabilityError(
            f"{owner} cannot set Anthropic cache_control explicitly; "
            "use RemoteContextHint.enable_cache=True for automatic prompt caching."
        )


def _reject_explicit_structured_output_options(options: Mapping[str, Any], *, owner: str) -> None:
    reserved = sorted({_OUTPUT_CONFIG, _OUTPUT_FORMAT}.intersection(options))
    if reserved:
        joined = ", ".join(reserved)
        raise UnsupportedCapabilityError(
            f"{owner} cannot set Anthropic structured output options explicitly "
            f"({joined}); use ResponseFormat instead."
        )


def _reject_reasoning_provider_option_conflicts(options: Mapping[str, Any]) -> None:
    if _THINKING in options:
        raise UnsupportedCapabilityError(
            "GenerationRequest.provider_options cannot set Anthropic thinking "
            "when ReasoningConfig is used."
        )


def _reject_structured_output_prefill(messages: list[dict[str, Any]]) -> None:
    if messages and messages[-1].get("role") == "assistant":
        raise UnsupportedCapabilityError(
            "Anthropic structured output is incompatible with assistant message prefilling."
        )


def _reject_active_reasoning_incompatibilities(
    config: ReasoningConfig,
    *,
    messages: list[dict[str, Any]],
    params: Mapping[str, Any],
) -> None:
    if not _is_active_reasoning_config(config):
        return
    if messages and messages[-1].get("role") == "assistant":
        raise UnsupportedCapabilityError(
            "Anthropic extended thinking is incompatible with assistant message prefilling."
        )
    if "temperature" in params:
        raise UnsupportedCapabilityError(
            "Anthropic extended thinking is incompatible with temperature."
        )
    if "top_k" in params:
        raise UnsupportedCapabilityError("Anthropic extended thinking is incompatible with top_k.")
    top_p = params.get("top_p")
    if top_p is not None:
        try:
            normalized_top_p = float(top_p)
        except (TypeError, ValueError) as exc:
            raise UnsupportedCapabilityError(
                "Anthropic extended thinking requires numeric top_p when set."
            ) from exc
        if not 0.95 <= normalized_top_p <= 1.0:
            raise UnsupportedCapabilityError(
                "Anthropic extended thinking requires top_p between 0.95 and 1.0 when set."
            )
    if _is_forced_tool_choice(params.get("tool_choice")):
        raise UnsupportedCapabilityError(
            "Anthropic extended thinking is incompatible with forced tool_choice."
        )


def _is_active_reasoning_config(config: ReasoningConfig) -> bool:
    mode = _reasoning_mode(config)
    if mode in {"disabled", "none"}:
        return False
    return _has_reasoning_controls(config)


def _has_reasoning_controls(config: ReasoningConfig) -> bool:
    return (
        config.mode is not None
        or config.effort is not None
        or config.budget_tokens is not None
        or config.summary is not None
    )


def _reasoning_mode(config: ReasoningConfig) -> str | None:
    if config.mode is None:
        return None
    mode = config.mode.lower()
    if mode not in _REASONING_MODES:
        raise UnsupportedCapabilityError(f"Unsupported Anthropic reasoning mode: {config.mode!r}.")
    return mode


def _reject_disabled_reasoning_conflicts(config: ReasoningConfig) -> None:
    conflicts: list[str] = []
    if config.effort is not None:
        conflicts.append("effort")
    if config.budget_tokens is not None:
        conflicts.append("budget_tokens")
    if config.summary is not None:
        conflicts.append("summary")
    if conflicts:
        joined = ", ".join(conflicts)
        raise UnsupportedCapabilityError(
            f"Anthropic reasoning mode={config.mode!r} conflicts with {joined}."
        )


def _validate_thinking_budget(budget_tokens: int, *, max_tokens: Any) -> None:
    if not isinstance(budget_tokens, int) or isinstance(budget_tokens, bool):
        raise InvalidItemError("Anthropic reasoning budget_tokens must be an integer.")
    if budget_tokens < _MIN_THINKING_BUDGET_TOKENS:
        raise InvalidItemError(
            "Anthropic reasoning budget_tokens must be at least "
            f"{_MIN_THINKING_BUDGET_TOKENS}."
        )
    if not isinstance(max_tokens, int) or isinstance(max_tokens, bool):
        raise InvalidItemError(
            "Anthropic reasoning budget_tokens validation requires integer max_tokens."
        )
    if budget_tokens >= max_tokens:
        raise InvalidItemError(
            "Anthropic reasoning budget_tokens must be less than max_tokens."
        )


def _reasoning_summary_to_display(summary: str) -> str:
    normalized = summary.lower()
    if normalized in {"auto", "summarized"}:
        return "summarized"
    if normalized in {"none", "omitted"}:
        return "omitted"
    raise UnsupportedCapabilityError(
        "Anthropic reasoning summary supports 'auto', 'summarized', 'none', or 'omitted' only."
    )


def _is_forced_tool_choice(choice: Any) -> bool:
    if isinstance(choice, Mapping):
        return choice.get("type") in {"any", "tool"}
    if isinstance(choice, str):
        return choice in {"any", "tool", "required"}
    return False


def _sum_known(*values: int | None) -> int | None:
    known = [value for value in values if value is not None]
    if not known:
        return None
    return sum(known)


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


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


def _unsupported_block_summary(block: Any, *, index: int) -> dict[str, Any]:
    return {
        "index": index,
        "id": _get_attr(block, "id", None),
        "type": _get_attr(block, "type", None),
    }


def json_arguments(arguments: Mapping[str, Any] | str) -> str:
    """Serialize tool call arguments consistently."""

    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
