"""Generation request, response, and event models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterable

from whero.vatbrain.core.items import FunctionCallItem, Item, MessageItem, Role, TextPart
from whero.vatbrain.core.tools import FunctionToolType
from whero.vatbrain.core.tools import ToolChoice, ToolSpec
from whero.vatbrain.core.usage import Usage


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    """Common generation controls."""

    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ResponseFormat:
    """JSON Schema structured output request."""

    json_schema: dict[str, Any]
    json_schema_name: str | None = None
    json_schema_description: str | None = None
    json_schema_strict: bool | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.json_schema, dict):
            raise ValueError("ResponseFormat.json_schema must be a JSON schema dictionary.")
        if self.json_schema.get("type") == "json_schema" and "schema" in self.json_schema:
            raise ValueError("ResponseFormat.json_schema must be the schema body, not a provider wrapper.")
        object.__setattr__(self, "json_schema", dict(self.json_schema))


@dataclass(frozen=True, slots=True)
class ReasoningConfig:
    """Common reasoning behavior controls."""

    mode: str | None = None
    effort: str | None = None
    budget_tokens: int | None = None
    summary: str | None = None
    include_trace: bool | None = None
    provider_options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RemoteContextHint:
    """Provider-side cache/delta hints that do not replace full context."""

    enable_cache: bool = False
    new_items_start_index: int | None = None
    provider_options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.new_items_start_index is not None and self.new_items_start_index < 0:
            raise ValueError("RemoteContextHint.new_items_start_index must be non-negative.")
        object.__setattr__(self, "provider_options", dict(self.provider_options))


class ReplayMode(StrEnum):
    """How provider-native item snapshots are used for replay."""

    NORMALIZED_ONLY = "normalized_only"
    PREFER_PROVIDER_NATIVE = "prefer_provider_native"
    REQUIRE_PROVIDER_NATIVE = "require_provider_native"


@dataclass(frozen=True, slots=True)
class ReplayPolicy:
    """Controls same-provider replay from normalized items and native snapshots."""

    mode: ReplayMode | str = ReplayMode.PREFER_PROVIDER_NATIVE
    cross_provider: str = "unsupported"

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", ReplayMode(self.mode))
        if self.cross_provider != "unsupported":
            raise ValueError("ReplayPolicy.cross_provider currently supports 'unsupported' only.")


@dataclass(frozen=True, slots=True)
class ToolCallConfig:
    """Common tool-call behavior controls."""

    parallel_tool_calls: bool | None = None
    tool_choice: ToolChoice | str | dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class StreamOptions:
    """Common streaming options."""

    include_usage: bool | None = None


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """A full-context generation request."""

    model: str
    items: tuple[Item, ...]
    tools: tuple[ToolSpec, ...] = ()
    generation_config: GenerationConfig | None = None
    response_format: ResponseFormat | None = None
    reasoning: ReasoningConfig | None = None
    tool_call_config: ToolCallConfig | None = None
    stream_options: StreamOptions | None = None
    remote_context: RemoteContextHint | None = None
    replay_policy: ReplayPolicy | None = None
    provider_options: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        model: str,
        items: Iterable[Item],
        *,
        tools: Iterable[ToolSpec] = (),
        generation_config: GenerationConfig | None = None,
        response_format: ResponseFormat | None = None,
        reasoning: ReasoningConfig | None = None,
        tool_call_config: ToolCallConfig | None = None,
        stream_options: StreamOptions | None = None,
        remote_context: RemoteContextHint | None = None,
        replay_policy: ReplayPolicy | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> None:
        if not model:
            raise ValueError("GenerationRequest.model is required.")
        normalized_items = tuple(items)
        if not normalized_items:
            raise ValueError("GenerationRequest.items must not be empty.")
        if (
            remote_context is not None
            and remote_context.new_items_start_index is not None
            and remote_context.new_items_start_index > len(normalized_items)
        ):
            raise ValueError(
                "RemoteContextHint.new_items_start_index must be less than or equal to "
                "GenerationRequest.items length."
            )
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "items", normalized_items)
        object.__setattr__(self, "tools", tuple(tools))
        object.__setattr__(self, "generation_config", generation_config)
        object.__setattr__(self, "response_format", response_format)
        object.__setattr__(self, "reasoning", reasoning)
        object.__setattr__(self, "tool_call_config", tool_call_config)
        object.__setattr__(self, "stream_options", stream_options)
        object.__setattr__(self, "remote_context", remote_context)
        object.__setattr__(self, "replay_policy", replay_policy)
        object.__setattr__(self, "provider_options", dict(provider_options or {}))


@dataclass(frozen=True, slots=True)
class GenerationResponse:
    """Normalized generation response."""

    id: str | None
    provider: str
    model: str | None
    output_items: tuple[Item, ...] = ()
    stop_reason: str | None = None
    usage: Usage | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: Any | None = None


class StreamEventType(StrEnum):
    """Known normalized stream event types."""

    RESPONSE_CREATED = "response.created"
    RESPONSE_STARTED = "response.started"
    RESPONSE_INCOMPLETE = "response.incomplete"
    ITEM_CREATED = "item.created"
    ITEM_DELTA = "item.delta"
    ITEM_COMPLETED = "item.completed"
    CONTENT_PART_CREATED = "content_part.created"
    CONTENT_PART_COMPLETED = "content_part.completed"
    TEXT_DELTA = "text.delta"
    TEXT_COMPLETED = "text.completed"
    TOOL_CALL_CREATED = "tool_call.created"
    TOOL_CALL_DELTA = "tool_call.delta"
    TOOL_CALL_COMPLETED = "tool_call.completed"
    REASONING_CREATED = "reasoning.created"
    REASONING_DELTA = "reasoning.delta"
    REASONING_COMPLETED = "reasoning.completed"
    USAGE_UPDATED = "usage.updated"
    RESPONSE_COMPLETED = "response.completed"
    RESPONSE_FAILED = "response.failed"
    RESPONSE_ERROR = "response.error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class GenerationStreamEvent:
    """Normalized generation streaming event."""

    type: str
    sequence: int
    provider: str
    response_id: str | None = None
    item_id: str | None = None
    delta: Any | None = None
    item: Item | None = None
    usage: Usage | None = None
    response: GenerationResponse | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_event: Any | None = None


class GenerationStreamAccumulator:
    """Rebuild a minimal generation response from normalized stream events."""

    def __init__(self, *, provider: str) -> None:
        self.provider = provider
        self.response_id: str | None = None
        self.model: str | None = None
        self.stop_reason: str | None = None
        self.usage: Usage | None = None
        self.final_response: GenerationResponse | None = None
        self.metadata: dict[str, Any] = {}
        self._text_parts: dict[tuple[int, int], str] = {}
        self._function_calls: dict[Any, dict[str, Any]] = {}
        self._item_order: list[tuple[str, Any]] = []

    def add(self, event: GenerationStreamEvent) -> None:
        """Add one normalized stream event to the accumulator."""

        if event.response_id is not None:
            self.response_id = event.response_id
        if event.usage is not None:
            self.usage = event.usage
        if event.response is not None:
            self._merge_response(event.response)
        self._merge_metadata(event)

        if event.type == StreamEventType.TEXT_DELTA.value:
            key = self._text_key(event)
            self._remember_order("text", key)
            self._text_parts[key] = self._text_parts.get(key, "") + str(event.delta or "")
        elif event.type == StreamEventType.TEXT_COMPLETED.value:
            text = self._text_from_completed_event(event)
            if text is not None:
                key = self._text_key(event)
                self._remember_order("text", key)
                self._text_parts[key] = text
        elif event.type == StreamEventType.ITEM_CREATED.value and isinstance(event.item, FunctionCallItem):
            key = self._function_key(event)
            self._remember_order("function_call", key)
            self._function_calls[key] = {
                "id": event.item.id,
                "name": event.item.name,
                "arguments": event.item.arguments,
                "call_id": event.item.call_id,
                "status": event.item.status,
                "type": event.item.type,
                "input": event.item.input,
                "metadata": dict(event.item.metadata),
            }
        elif event.type == StreamEventType.TOOL_CALL_DELTA.value:
            key = self._function_key(event)
            self._remember_order("function_call", key)
            tool_type = self._tool_type_from_event(event)
            function_call = self._function_calls.setdefault(
                key,
                {
                    "id": event.item_id,
                    "name": event.metadata.get("name", ""),
                    "arguments": "",
                    "call_id": event.metadata.get("call_id", ""),
                    "status": None,
                    "type": tool_type,
                    "input": "",
                    "metadata": {},
                },
            )
            function_call["arguments"] = str(function_call.get("arguments") or "") + str(event.delta or "")
            if tool_type == FunctionToolType.CUSTOM:
                function_call["type"] = tool_type
                function_call["input"] = str(function_call.get("input") or "") + str(event.delta or "")
            if event.metadata.get("name") and not function_call.get("name"):
                function_call["name"] = event.metadata["name"]
            if event.metadata.get("call_id") and not function_call.get("call_id"):
                function_call["call_id"] = event.metadata["call_id"]
        elif event.type == StreamEventType.TOOL_CALL_COMPLETED.value:
            key = self._function_key(event)
            self._remember_order("function_call", key)
            tool_type = self._tool_type_from_event(event)
            function_call = self._function_calls.setdefault(
                key,
                {
                    "id": event.item_id,
                    "name": event.metadata.get("name", ""),
                    "arguments": "",
                    "call_id": event.metadata.get("call_id", ""),
                    "status": None,
                    "type": tool_type,
                    "input": "",
                    "metadata": {},
                },
            )
            if event.delta is not None:
                function_call["arguments"] = str(event.delta)
                if tool_type == FunctionToolType.CUSTOM:
                    function_call["input"] = str(event.delta)
            if tool_type == FunctionToolType.CUSTOM:
                function_call["type"] = tool_type
            if event.metadata.get("name"):
                function_call["name"] = event.metadata["name"]
            if event.metadata.get("call_id"):
                function_call["call_id"] = event.metadata["call_id"]
            function_call["status"] = event.metadata.get("status", function_call.get("status"))

        if event.type in {
            StreamEventType.RESPONSE_COMPLETED.value,
            StreamEventType.RESPONSE_INCOMPLETE.value,
            StreamEventType.RESPONSE_FAILED.value,
            StreamEventType.RESPONSE_ERROR.value,
        }:
            self.stop_reason = event.type
        if event.error is not None:
            self.metadata["terminal_error"] = event.error

    def to_response(self) -> GenerationResponse:
        """Return the best-known response after accumulated events."""

        if self.final_response is not None:
            metadata = dict(self.final_response.metadata)
            metadata.update(self.metadata)
            return GenerationResponse(
                id=self.final_response.id,
                provider=self.final_response.provider,
                model=self.final_response.model,
                output_items=self.final_response.output_items,
                stop_reason=self.final_response.stop_reason or self.stop_reason,
                usage=self.final_response.usage or self.usage,
                metadata=metadata,
                raw=self.final_response.raw,
            )

        output_items: list[Item] = []
        emitted_text_keys: set[tuple[int, int]] = set()
        emitted_function_keys: set[Any] = set()
        for kind, key in self._item_order:
            if kind == "text" and key not in emitted_text_keys and key in self._text_parts:
                output_items.append(MessageItem(Role.ASSISTANT, [TextPart(self._text_parts[key])]))
                emitted_text_keys.add(key)
            elif kind == "function_call" and key not in emitted_function_keys and key in self._function_calls:
                call = self._function_calls[key]
                output_items.append(
                    FunctionCallItem(
                        id=call.get("id"),
                        name=str(call.get("name") or ""),
                        arguments=str(call.get("arguments") or ""),
                        call_id=str(call.get("call_id") or ""),
                        status=call.get("status"),
                        type=call.get("type", FunctionToolType.FUNCTION),
                        input=call.get("input"),
                        metadata=dict(call.get("metadata") or {}),
                    )
                )
                emitted_function_keys.add(key)

        return GenerationResponse(
            id=self.response_id,
            provider=self.provider,
            model=self.model,
            output_items=tuple(output_items),
            stop_reason=self.stop_reason,
            usage=self.usage,
            metadata=dict(self.metadata),
        )

    def _merge_response(self, response: GenerationResponse) -> None:
        if response.id is not None:
            self.response_id = response.id
        if response.model is not None:
            self.model = response.model
        if response.stop_reason is not None:
            self.stop_reason = response.stop_reason
        if response.usage is not None:
            self.usage = response.usage
        if response.output_items:
            self.final_response = response

    def _merge_metadata(self, event: GenerationStreamEvent) -> None:
        provider_event_type = event.metadata.get("provider_event_type")
        if provider_event_type is not None:
            self.metadata["last_provider_event_type"] = provider_event_type
        if event.type in {
            StreamEventType.RESPONSE_INCOMPLETE.value,
            StreamEventType.RESPONSE_FAILED.value,
            StreamEventType.RESPONSE_ERROR.value,
        }:
            self.metadata["terminal_event_type"] = event.type

    def _remember_order(self, kind: str, key: Any) -> None:
        entry = (kind, key)
        if entry not in self._item_order:
            self._item_order.append(entry)

    @staticmethod
    def _text_key(event: GenerationStreamEvent) -> tuple[int, int]:
        return (
            int(event.metadata.get("output_index", 0) or 0),
            int(event.metadata.get("content_index", 0) or 0),
        )

    @staticmethod
    def _function_key(event: GenerationStreamEvent) -> Any:
        output_index = event.metadata.get("output_index")
        if output_index is not None:
            return ("output_index", output_index)
        return ("item_id", event.item_id)

    @staticmethod
    def _text_from_completed_event(event: GenerationStreamEvent) -> str | None:
        if event.delta is not None:
            return str(event.delta)
        text = event.metadata.get("text")
        return str(text) if text is not None else None

    @staticmethod
    def _tool_type_from_event(event: GenerationStreamEvent) -> FunctionToolType:
        raw_type = event.metadata.get("tool_type", FunctionToolType.FUNCTION)
        try:
            return FunctionToolType(raw_type)
        except ValueError:
            return FunctionToolType.FUNCTION
