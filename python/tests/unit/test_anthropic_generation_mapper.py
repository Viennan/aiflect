from __future__ import annotations

from types import SimpleNamespace

import pytest

from whero.vatbrain import (
    FunctionCallItem,
    FunctionResultItem,
    FunctionToolType,
    GenerationConfig,
    GenerationRequest,
    ImagePart,
    MessageItem,
    RemoteContextHint,
    ResponseFormat,
    TextPart,
    ToolCallConfig,
    ToolChoice,
    ToolSpec,
    VideoPart,
)
from whero.vatbrain.core.errors import InvalidItemError, UnsupportedCapabilityError
from whero.vatbrain.core.items import ReasoningItem
from whero.vatbrain.providers.anthropic.mapper import (
    from_anthropic_generation_response,
    to_anthropic_generation_params,
)


def test_generation_request_maps_messages_images_tools_and_cache_hint() -> None:
    request = GenerationRequest(
        model="claude-test",
        items=[
            MessageItem.system("system policy"),
            MessageItem.developer("developer policy"),
            MessageItem.user(
                [
                    TextPart("describe"),
                    ImagePart(url="https://example.test/a.png"),
                    ImagePart(data="data:image/jpeg;base64,abc"),
                ]
            ),
        ],
        tools=[
            ToolSpec(
                name="lookup",
                description="Lookup data",
                parameters_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                strict=True,
                provider_options={"input_examples": [{"query": "weather"}]},
            )
        ],
        generation_config=GenerationConfig(temperature=0.2, top_p=0.8, max_output_tokens=128),
        tool_call_config=ToolCallConfig(
            parallel_tool_calls=False,
            tool_choice=ToolChoice.REQUIRED,
        ),
        remote_context=RemoteContextHint(
            previous_response_id="ignored",
            covered_item_count=2,
            store=True,
        ),
        provider_options={"top_k": 10},
    )

    params = to_anthropic_generation_params(request)

    assert params["model"] == "claude-test"
    assert params["max_tokens"] == 128
    assert params["temperature"] == 0.2
    assert params["top_p"] == 0.8
    assert params["top_k"] == 10
    assert params["cache_control"] == {"type": "ephemeral"}
    assert "previous_response_id" not in params
    assert params["system"] == [
        {"type": "text", "text": "system policy"},
        {"type": "text", "text": "developer policy"},
    ]
    assert params["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "describe"},
                {
                    "type": "image",
                    "source": {"type": "url", "url": "https://example.test/a.png"},
                },
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": "abc",
                    },
                },
            ],
        }
    ]
    assert params["tools"] == [
        {
            "name": "lookup",
            "description": "Lookup data",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            "strict": True,
            "input_examples": [{"query": "weather"}],
        }
    ]
    assert params["tool_choice"] == {"type": "any", "disable_parallel_tool_use": True}


def test_generation_mapper_replays_tool_use_and_tool_result_as_messages() -> None:
    request = GenerationRequest(
        model="claude-test",
        items=[
            MessageItem.user("need data"),
            FunctionCallItem(
                name="lookup",
                arguments='{"query":"vatbrain"}',
                call_id="toolu_1",
            ),
            FunctionResultItem(
                call_id="toolu_1",
                output='{"ok":true}',
                metadata={"is_error": False},
            ),
            MessageItem.user("continue"),
        ],
        generation_config=GenerationConfig(max_output_tokens=64),
    )

    params = to_anthropic_generation_params(request)

    assert params["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "need data"}]},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "lookup",
                    "input": {"query": "vatbrain"},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": '{"ok":true}',
                    "is_error": False,
                },
                {"type": "text", "text": "continue"},
            ],
        },
    ]


def test_anthropic_mapper_rejects_explicit_cache_control() -> None:
    base_request = {
        "model": "claude-test",
        "items": [MessageItem.user("hello")],
        "generation_config": GenerationConfig(max_output_tokens=32),
    }

    with pytest.raises(UnsupportedCapabilityError, match="cache_control"):
        to_anthropic_generation_params(
            GenerationRequest(**base_request, provider_options={"cache_control": {"type": "ephemeral"}})
        )

    with pytest.raises(UnsupportedCapabilityError, match="cache_control"):
        to_anthropic_generation_params(
            GenerationRequest(
                **base_request,
                remote_context=RemoteContextHint(
                    previous_response_id="ignored",
                    covered_item_count=1,
                    provider_options={"cache_control": {"type": "ephemeral"}},
                ),
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="cache_control"):
        to_anthropic_generation_params(
            GenerationRequest(
                **base_request,
                tools=[ToolSpec(name="lookup", provider_options={"cache_control": {"type": "ephemeral"}})],
            )
        )


def test_anthropic_mapper_rejects_unsupported_inputs_and_options() -> None:
    with pytest.raises(InvalidItemError, match="max_tokens"):
        to_anthropic_generation_params(
            GenerationRequest(model="claude-test", items=[MessageItem.user("hello")])
        )

    with pytest.raises(InvalidItemError, match="initial instruction prefix"):
        to_anthropic_generation_params(
            GenerationRequest(
                model="claude-test",
                items=[MessageItem.user("hello"), MessageItem.system("late")],
                generation_config=GenerationConfig(max_output_tokens=32),
            )
        )

    with pytest.raises(InvalidItemError, match="VideoPart"):
        to_anthropic_generation_params(
            GenerationRequest(
                model="claude-test",
                items=[MessageItem.user([VideoPart(url="https://example.test/a.mp4")])],
                generation_config=GenerationConfig(max_output_tokens=32),
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="custom tools"):
        to_anthropic_generation_params(
            GenerationRequest(
                model="claude-test",
                items=[MessageItem.user("run code")],
                tools=[ToolSpec(name="run_code", type=FunctionToolType.CUSTOM)],
                generation_config=GenerationConfig(max_output_tokens=32),
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="ResponseFormat"):
        to_anthropic_generation_params(
            GenerationRequest(
                model="claude-test",
                items=[MessageItem.user("json")],
                response_format=ResponseFormat(json_schema={"type": "object"}),
                generation_config=GenerationConfig(max_output_tokens=32),
            )
        )


def test_anthropic_response_maps_content_blocks_usage_and_snapshots() -> None:
    response = SimpleNamespace(
        id="msg_1",
        model="claude-test",
        stop_reason="tool_use",
        content=[
            SimpleNamespace(type="text", text="I will look."),
            SimpleNamespace(type="tool_use", id="toolu_1", name="lookup", input={"query": "x"}),
            SimpleNamespace(type="thinking", thinking="checked options"),
        ],
        usage=SimpleNamespace(
            input_tokens=3,
            cache_creation_input_tokens=10,
            cache_read_input_tokens=20,
            output_tokens=5,
            service_tier="standard",
        ),
    )

    mapped = from_anthropic_generation_response(response)

    assert mapped.id == "msg_1"
    assert mapped.provider == "anthropic"
    assert mapped.stop_reason == "tool_use"
    assert isinstance(mapped.output_items[0], MessageItem)
    assert mapped.output_items[0].parts == (TextPart("I will look."),)
    assert isinstance(mapped.output_items[1], FunctionCallItem)
    assert mapped.output_items[1].call_id == "toolu_1"
    assert mapped.output_items[1].arguments == '{"query":"x"}'
    assert isinstance(mapped.output_items[2], ReasoningItem)
    assert mapped.output_items[2].text == "checked options"
    assert mapped.output_items[0].provider_snapshots[0].provider == "anthropic"
    assert mapped.usage is not None
    assert mapped.usage.input_tokens == 33
    assert mapped.usage.output_tokens == 5
    assert mapped.usage.total_tokens == 38
    assert mapped.usage.cached_tokens == 20
    assert mapped.usage.metadata["provider_input_tokens"] == 3
    assert mapped.usage.metadata["cache_creation_input_tokens"] == 10
    assert mapped.usage.metadata["service_tier"] == "standard"


def test_anthropic_mapper_replays_provider_native_snapshot() -> None:
    response = SimpleNamespace(
        id="msg_1",
        model="claude-test",
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="hello")],
        usage=None,
    )
    mapped = from_anthropic_generation_response(response)

    params = to_anthropic_generation_params(
        GenerationRequest(
            model="claude-test",
            items=[mapped.output_items[0]],
            generation_config=GenerationConfig(max_output_tokens=16),
        )
    )

    assert params["messages"] == [
        {"role": "assistant", "content": [{"type": "text", "text": "hello"}]}
    ]
