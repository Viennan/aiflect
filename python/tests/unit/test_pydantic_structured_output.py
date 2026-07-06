from __future__ import annotations

from pydantic import BaseModel
import pytest

from whero.aiflect import GenerationResponse, MessageItem
from whero.aiflect.structured import (
    ParsedGenerationResponse,
    StructuredOutputParseError,
    pydantic_output,
)


class Address(BaseModel):
    city: str


class Contact(BaseModel):
    name: str
    email: str | None = None
    address: Address


def test_pydantic_output_builds_strict_json_schema_response_format() -> None:
    spec = pydantic_output(Contact, name="contact")

    response_format = spec.response_format
    schema = response_format.json_schema

    assert response_format.json_schema_name == "contact"
    assert response_format.json_schema_strict is True
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["name", "email", "address"]
    assert "default" not in schema["properties"]["email"]
    assert schema["$defs"]["Address"]["additionalProperties"] is False
    assert schema["$defs"]["Address"]["required"] == ["city"]


def test_pydantic_output_can_keep_non_strict_schema() -> None:
    spec = pydantic_output(Contact, strict=False)

    schema = spec.response_format.json_schema

    assert spec.response_format.json_schema_strict is False
    assert "additionalProperties" not in schema
    assert schema["required"] == ["name", "address"]


def test_pydantic_output_sanitizes_schema_name() -> None:
    spec = pydantic_output(Contact, name="contact result/v1")

    assert spec.response_format.json_schema_name == "contact_result_v1"


def test_parse_text_returns_typed_output() -> None:
    spec = pydantic_output(Contact)

    contact = spec.parse_text(
        '{"name":"Ada","email":"ada@example.test","address":{"city":"London"}}'
    )

    assert isinstance(contact, Contact)
    assert contact.address.city == "London"


def test_parse_response_extracts_assistant_text() -> None:
    spec = pydantic_output(Contact)
    response = GenerationResponse(
        id="resp_1",
        provider="test",
        model="model",
        output_items=(
            MessageItem.assistant('{"name":"Ada",'),
            MessageItem.assistant('"email":null,"address":{"city":"London"}}'),
        ),
    )

    parsed = spec.parse_response(response)

    assert isinstance(parsed, ParsedGenerationResponse)
    assert parsed.response is response
    assert parsed.output_parsed.email is None
    assert parsed.output_text == '{"name":"Ada","email":null,"address":{"city":"London"}}'


def test_parse_response_requires_assistant_text() -> None:
    spec = pydantic_output(Contact)
    response = GenerationResponse(
        id="resp_1",
        provider="test",
        model="model",
        output_items=(MessageItem.user("not output"),),
    )

    with pytest.raises(StructuredOutputParseError) as raised:
        spec.parse_response(response)

    assert raised.value.response is response
    assert raised.value.output_text is None


def test_parse_text_wraps_validation_error() -> None:
    spec = pydantic_output(Contact)

    with pytest.raises(StructuredOutputParseError) as raised:
        spec.parse_text('{"name":"Ada"}')

    assert raised.value.output_text == '{"name":"Ada"}'
    assert raised.value.cause is not None
