"""DeepSeek Anthropic-compatible Messages API request and response mapping."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from whero.aiflect.core.errors import InvalidItemError, ProviderResponseMappingError, UnsupportedCapabilityError
from whero.aiflect.core.generation import (
    GenerationConfig,
    GenerationRequest,
    GenerationResponse,
    ReasoningConfig,
    ReplayMode,
    ReplayPolicy,
    ResponseFormat,
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

PROVIDER = "deepseek"
API_FAMILY = "anthropic_messages"
_CACHE_CONTROL = "cache_control"
_OUTPUT_CONFIG = "output_config"
_OUTPUT_FORMAT = "output_format"
_SUPPORTED_REASONING_EFFORTS = {"high", "max"}


def to_deepseek_generation_params(
    request: GenerationRequest,
    *,
    stream: bool = False,
) -> dict[str, Any]:
    """Convert an aiflect generation request into DeepSeek Anthropic-compatible parameters."""

    _reject_unsupported_provider_options(
        request.provider_options,
        owner="GenerationRequest.provider_options",
    )
    if request.remote_context is not None:
        _reject_unsupported_provider_options(
            request.remote_context.provider_options,
            owner="RemoteContextHint.provider_options",
        )
    if request.response_format is not None:
        raise UnsupportedCapabilityError(
            "DeepSeek Anthropic-compatible API does not support ResponseFormat; "
            "output_config.format is not available."
        )
    if request.reasoning is not None:
        _reject_reasoning_provider_option_conflicts(request.provider_options)

    system, messages = _items_to_deepseek_messages(request.items, request.replay_policy)
    params: dict[str, Any] = {
        "model": request.model,
        "messages": messages,
    }
    if system:
        params["system"] = system
    if stream:
        params["stream"] = True
    if request.tools:
        params["tools"] = [_tool_to_deepseek_tool(tool) for tool in request.tools]
    if request.generation_config:
        params.update(_generation_config_to_params(request.generation_config))
    if request.reasoning:
        _merge_mapped_params(params, _reasoning_config_to_params(request.reasoning))
    if request.tool_call_config:
        params.update(_tool_call_config_to_params(request.tool_call_config))
    params.update(request.provider_options)
    if params.get("max_tokens") is None:
        raise InvalidItemError(
            "DeepSeek Anthropic-compatible API requires max_tokens; set "
            "GenerationConfig.max_output_tokens or provider_options['max_tokens']."
        )
    return params


def from_deepseek_generation_response(response: Any) -> GenerationResponse:
    """Convert a DeepSeek Anthropic-compatible response into an aiflect response."""

    output_items: list[Item] = []
    unsupported_blocks: list[dict[str, Any]] = []
    for index, block in enumerate(_get_attr(response, "content", []) or []):
        try:
            output_items.append(_deepseek_content_block_to_item(block, index=index))
        except ProviderResponseMappingError:
            unsupported_blocks.append(_unsupported_block_summary(block, index=index))
    if unsupported_blocks and not output_items:
        raise ProviderResponseMappingError(
            "DeepSeek response contains only unsupported content block types.",
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
        usage=usage_from_deepseek(_get_attr(response, "usage", None)),
        metadata=metadata,
        raw=response,
    )


def usage_from_deepseek(usage: Any | None) -> Usage | None:
    """Normalize DeepSeek Anthropic-compatible usage objects or dictionaries."""

    if usage is None:
        return None
    provider_input_tokens = _get_attr(usage, "input_tokens", None)
    output_tokens = _get_attr(usage, "output_tokens", None)
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
    for name in ("cache_creation", "server_tool_use", "service_tier"):
        value = _get_attr(usage, name, None)
        if value is not None:
            metadata[name] = _to_plain_data(value)
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_tokens=cache_read,
        raw=usage,
        metadata=metadata,
    )


def _items_to_deepseek_messages(
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
                    "DeepSeek adapter supports system/developer messages only "
                    "as the initial instruction prefix."
                )
            system_blocks.extend(_message_to_deepseek_system_blocks(item, replay_policy))
            continue
        in_initial_system_prefix = False
        role, blocks = _item_to_deepseek_message_blocks(item, replay_policy)
        if current_role != role:
            flush()
            current_role = role
            current_content = []
        current_content.extend(blocks)
    flush()
    if not messages:
        raise InvalidItemError("DeepSeek generation requires at least one non-system message item.")
    return system_blocks, messages


def _is_system_instruction_item(item: Item) -> bool:
    return isinstance(item, MessageItem) and item.role in {Role.SYSTEM, Role.DEVELOPER}


def _message_to_deepseek_system_blocks(
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
            raise InvalidItemError("DeepSeek system/developer messages support text parts only.")
    return result


def _item_to_deepseek_message_blocks(
    item: Item,
    replay_policy: ReplayPolicy | None,
) -> tuple[str, list[dict[str, Any]]]:
    blocks = _provider_snapshot_blocks(item, replay_policy)
    if blocks is not None:
        return _role_for_item(item), blocks
    if isinstance(item, MessageItem):
        if item.role == Role.USER:
            return "user", _message_to_deepseek_content_blocks(item)
        if item.role == Role.ASSISTANT:
            return "assistant", _message_to_deepseek_content_blocks(item)
        raise InvalidItemError(f"Unsupported DeepSeek message role: {item.role.value!r}")
    if isinstance(item, FunctionCallItem):
        return "assistant", [_function_call_to_deepseek_tool_use(item)]
    if isinstance(item, FunctionResultItem):
        return "user", [_function_result_to_deepseek_tool_result(item)]
    if isinstance(item, ReasoningItem):
        raise UnsupportedCapabilityError(
            "DeepSeek reasoning replay currently requires provider-native snapshots."
        )
    raise InvalidItemError(f"Unsupported DeepSeek generation item: {item!r}")


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
    raise InvalidItemError(f"Unsupported DeepSeek generation item: {item!r}")


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
        raise InvalidItemError("Provider-native replay requires a DeepSeek Anthropic-compatible snapshot.")
    return None


def _snapshot_payload_to_content_block(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("role") in {"user", "assistant"} and "content" in payload:
        raise InvalidItemError(
            "DeepSeek replay snapshots must contain content blocks, not full messages."
        )
    return dict(payload)


def _message_to_deepseek_content_blocks(item: MessageItem) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for part in item.parts:
        if isinstance(part, TextPart):
            blocks.append({"type": "text", "text": part.text})
        elif isinstance(part, (AudioPart, VideoPart, FilePart)):
            raise InvalidItemError(f"DeepSeek adapter does not support {type(part).__name__}.")
        elif isinstance(part, ImagePart):
            raise InvalidItemError("DeepSeek adapter does not support ImagePart.")
        else:
            raise InvalidItemError(f"Unsupported DeepSeek message part: {part!r}")
    return blocks


def _function_call_to_deepseek_tool_use(item: FunctionCallItem) -> dict[str, Any]:
    if item.type != FunctionToolType.FUNCTION:
        raise UnsupportedCapabilityError("DeepSeek adapter supports function tool calls only.")
    try:
        parsed_input = json.loads(item.arguments or "{}")
    except json.JSONDecodeError as exc:
        raise InvalidItemError("DeepSeek tool_use replay requires JSON object arguments.") from exc
    if not isinstance(parsed_input, Mapping):
        raise InvalidItemError("DeepSeek tool_use replay requires JSON object arguments.")
    return {
        "type": "tool_use",
        "id": item.call_id,
        "name": item.name,
        "input": dict(parsed_input),
    }


def _function_result_to_deepseek_tool_result(item: FunctionResultItem) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_use_id": item.call_id,
        "content": item.output,
    }


def _tool_to_deepseek_tool(tool: ToolSpec) -> dict[str, Any]:
    if not isinstance(tool, FunctionToolSpec):
        raise UnsupportedCapabilityError("DeepSeek adapter currently maps function tools only.")
    _reject_unsupported_provider_options(
        tool.provider_options,
        owner=f"ToolSpec({tool.name!r}).provider_options",
    )
    if tool.type != FunctionToolType.FUNCTION:
        raise UnsupportedCapabilityError("DeepSeek adapter does not support custom tools.")
    payload: dict[str, Any] = {
        "name": tool.name,
        "input_schema": tool.parameters_schema or {"type": "object", "properties": {}},
    }
    if tool.description is not None:
        payload["description"] = tool.description
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


def _reasoning_config_to_params(config: ReasoningConfig) -> dict[str, Any]:
    if config.budget_tokens is not None:
        raise UnsupportedCapabilityError("DeepSeek ignores reasoning budget_tokens; use effort instead.")
    if config.summary is not None:
        raise UnsupportedCapabilityError("DeepSeek Anthropic-compatible API does not support reasoning summary.")
    if config.include_trace is not None:
        raise UnsupportedCapabilityError("DeepSeek Anthropic-compatible API does not support include_trace.")
    if config.provider_options:
        raise UnsupportedCapabilityError("DeepSeek reasoning provider_options are not supported.")
    params: dict[str, Any] = {}
    if config.mode is not None:
        mode = config.mode.lower()
        if mode in {"disabled", "none"}:
            if config.effort is not None:
                raise UnsupportedCapabilityError("DeepSeek reasoning effort conflicts with disabled mode.")
            params["thinking"] = {"type": "disabled"}
            return params
        if mode not in {"enabled", "auto"}:
            raise UnsupportedCapabilityError(f"Unsupported DeepSeek reasoning mode: {config.mode!r}.")
        params["thinking"] = {"type": "enabled"}
    if config.effort is not None:
        effort = config.effort.lower()
        if effort not in _SUPPORTED_REASONING_EFFORTS:
            raise UnsupportedCapabilityError(
                "DeepSeek reasoning effort supports 'high' and 'max' only."
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
        params["tool_choice"] = _tool_choice_to_deepseek(config.tool_choice)
    if config.parallel_tool_calls is False:
        raise UnsupportedCapabilityError(
            "DeepSeek ignores Anthropic disable_parallel_tool_use; parallel_tool_calls=False is unsupported."
        )
    return params


def _tool_choice_to_deepseek(choice: ToolChoice | str | dict[str, Any]) -> dict[str, Any] | str:
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


def _deepseek_content_block_to_item(block: Any, *, index: int) -> Item:
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
        if block_type == "thinking":
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
            f"Malformed DeepSeek content block: {block_type!r}",
            provider=PROVIDER,
            operation="messages.create",
            raw=block,
            cause=exc,
        ) from exc
    raise ProviderResponseMappingError(
        f"Unsupported DeepSeek content block type: {block_type!r}",
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


def _reject_unsupported_provider_options(options: Mapping[str, Any], *, owner: str) -> None:
    if _CACHE_CONTROL in options:
        raise UnsupportedCapabilityError(
            f"{owner} cannot set DeepSeek cache_control explicitly; DeepSeek ignores it."
        )
    if _OUTPUT_FORMAT in options:
        raise UnsupportedCapabilityError(
            f"{owner} cannot set output_format; DeepSeek Anthropic-compatible API does not support it."
        )
    output_config = options.get(_OUTPUT_CONFIG)
    if isinstance(output_config, Mapping) and "format" in output_config:
        raise UnsupportedCapabilityError(
            f"{owner} cannot set output_config.format; DeepSeek Anthropic-compatible API "
            "supports output_config.effort only."
        )


def _reject_reasoning_provider_option_conflicts(options: Mapping[str, Any]) -> None:
    conflicts = sorted({"thinking", _OUTPUT_CONFIG}.intersection(options))
    if conflicts:
        joined = ", ".join(conflicts)
        raise UnsupportedCapabilityError(
            f"GenerationRequest.provider_options cannot set {joined} when ReasoningConfig is used."
        )


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
