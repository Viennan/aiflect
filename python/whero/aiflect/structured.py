"""Structured output helpers for Python users."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from inspect import cleandoc
import re
from typing import Any, Generic, TypeVar

from whero.aiflect.core.errors import AiflectError
from whero.aiflect.core.generation import GenerationResponse, ResponseFormat
from whero.aiflect.core.items import MessageItem, Role, TextPart

T = TypeVar("T")


class StructuredOutputParseError(AiflectError):
    """Raised when structured output text cannot be parsed into the requested type."""

    def __init__(
        self,
        message: str,
        *,
        output_text: str | None = None,
        response: GenerationResponse | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.output_text = output_text
        self.response = response
        self.cause = cause


@dataclass(frozen=True, slots=True)
class ParsedGenerationResponse(Generic[T]):
    """A generation response paired with parsed structured output."""

    response: GenerationResponse
    output_text: str
    output_parsed: T


@dataclass(frozen=True, slots=True)
class PydanticOutputSpec(Generic[T]):
    """Reusable Pydantic structured output request and parser."""

    output_type: Any
    response_format: ResponseFormat
    _type_adapter: Any = field(repr=False, compare=False)

    def parse_text(self, text: str) -> T:
        """Parse JSON text into the configured Pydantic output type."""

        try:
            return self._type_adapter.validate_json(text)
        except Exception as exc:
            raise StructuredOutputParseError(
                "Failed to parse structured output text.",
                output_text=text,
                cause=exc,
            ) from exc

    def parse_response(self, response: GenerationResponse) -> ParsedGenerationResponse[T]:
        """Parse assistant text from a generation response."""

        output_text = _output_text_from_response(response)
        try:
            output_parsed = self._type_adapter.validate_json(output_text)
        except Exception as exc:
            raise StructuredOutputParseError(
                "Failed to parse structured output response.",
                output_text=output_text,
                response=response,
                cause=exc,
            ) from exc
        return ParsedGenerationResponse(
            response=response,
            output_text=output_text,
            output_parsed=output_parsed,
        )


def pydantic_output(
    output_type: Any,
    *,
    name: str | None = None,
    description: str | None = None,
    strict: bool = True,
) -> PydanticOutputSpec[Any]:
    """Build a JSON Schema response format and parser from a Pydantic v2 type."""

    type_adapter = _type_adapter(output_type)
    json_schema = type_adapter.json_schema(mode="validation")
    if strict:
        json_schema = _strict_json_schema(json_schema)
    schema_name = _schema_name(output_type, name)
    schema_description = description if description is not None else _schema_description(output_type)
    return PydanticOutputSpec(
        output_type=output_type,
        response_format=ResponseFormat(
            json_schema=json_schema,
            json_schema_name=schema_name,
            json_schema_description=schema_description,
            json_schema_strict=strict,
        ),
        _type_adapter=type_adapter,
    )


def _type_adapter(output_type: Any) -> Any:
    try:
        from pydantic import TypeAdapter
    except ModuleNotFoundError as exc:
        raise ImportError(
            "Pydantic structured output helpers require pydantic>=2,<3. "
            "Install with 'whero-aiflect[pydantic]'."
        ) from exc
    return TypeAdapter(output_type)


def _strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(schema)
    _normalize_schema_node(normalized)
    return normalized


def _normalize_schema_node(node: Any) -> None:
    if isinstance(node, list):
        for item in node:
            _normalize_schema_node(item)
        return
    if not isinstance(node, dict):
        return

    if node.get("default") is None:
        node.pop("default", None)

    properties = node.get("properties")
    if node.get("type") == "object" or isinstance(properties, dict):
        node.setdefault("additionalProperties", False)
        if isinstance(properties, dict):
            node["required"] = list(properties.keys())
            for property_schema in properties.values():
                _normalize_schema_node(property_schema)

    for defs_key in ("$defs", "definitions"):
        defs = node.get(defs_key)
        if isinstance(defs, dict):
            for definition in defs.values():
                _normalize_schema_node(definition)

    items = node.get("items")
    if isinstance(items, (dict, list)):
        _normalize_schema_node(items)

    for union_key in ("anyOf", "allOf", "oneOf"):
        choices = node.get(union_key)
        if isinstance(choices, list):
            for choice in choices:
                _normalize_schema_node(choice)


def _schema_name(output_type: Any, explicit_name: str | None) -> str:
    raw_name = explicit_name or getattr(output_type, "__name__", None) or "response"
    schema_name = re.sub(r"[^A-Za-z0-9_-]+", "_", raw_name).strip("_")
    return schema_name or "response"


def _schema_description(output_type: Any) -> str | None:
    raw_doc = getattr(output_type, "__doc__", None)
    if not raw_doc:
        return None
    description = cleandoc(raw_doc)
    return description or None


def _output_text_from_response(response: GenerationResponse) -> str:
    text_parts: list[str] = []
    for item in response.output_items:
        if isinstance(item, MessageItem) and item.role == Role.ASSISTANT:
            for part in item.parts:
                if isinstance(part, TextPart):
                    text_parts.append(part.text)
    if not text_parts:
        raise StructuredOutputParseError(
            "Generation response does not contain assistant text to parse.",
            response=response,
        )
    return "".join(text_parts)


__all__ = [
    "ParsedGenerationResponse",
    "PydanticOutputSpec",
    "StructuredOutputParseError",
    "pydantic_output",
]
