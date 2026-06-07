from __future__ import annotations

from types import SimpleNamespace

import pytest

from whero.vatbrain import (
    AudioPart,
    FilePart,
    FunctionCallItem,
    FunctionResultItem,
    FunctionToolType,
    GenerationConfig,
    GenerationRequest,
    ImagePart,
    MessageItem,
    ReasoningConfig,
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
from whero.vatbrain.providers.deepseek.mapper import (
    from_deepseek_generation_response,
    to_deepseek_generation_params,
)


def test_generation_request_maps_text_tools_reasoning_and_cache_hint_compatibility() -> None:
    request = GenerationRequest(
        model="deepseek-reasoner",
        items=[
            MessageItem.system("system policy"),
            MessageItem.developer("developer policy"),
            MessageItem.user("find data"),
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
            )
        ],
        generation_config=GenerationConfig(temperature=0.2, top_p=0.8, max_output_tokens=128),
        reasoning=ReasoningConfig(mode="enabled", effort="high"),
        tool_call_config=ToolCallConfig(tool_choice=ToolChoice.REQUIRED),
        remote_context=RemoteContextHint(
            enable_cache=True,
            new_items_start_index=2,
        ),
        provider_options={"top_k": 10},
    )

    params = to_deepseek_generation_params(request)

    assert params["model"] == "deepseek-reasoner"
    assert params["max_tokens"] == 128
    assert params["temperature"] == 0.2
    assert params["top_p"] == 0.8
    assert params["top_k"] == 10
    assert "cache_control" not in params
    assert "previous_response_id" not in params
    assert params["thinking"] == {"type": "enabled"}
    assert params["output_config"] == {"effort": "high"}
    assert params["system"] == [
        {"type": "text", "text": "system policy"},
        {"type": "text", "text": "developer policy"},
    ]
    assert params["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "find data"}]}
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
        }
    ]
    assert params["tool_choice"] == {"type": "any"}


def test_generation_mapper_replays_tool_use_and_tool_result_as_messages() -> None:
    request = GenerationRequest(
        model="deepseek-chat",
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

    params = to_deepseek_generation_params(request)

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
                },
                {"type": "text", "text": "continue"},
            ],
        },
    ]


def test_deepseek_mapper_rejects_response_format_and_explicit_cache_control() -> None:
    base_request = {
        "model": "deepseek-chat",
        "items": [MessageItem.user("hello")],
        "generation_config": GenerationConfig(max_output_tokens=32),
    }

    with pytest.raises(UnsupportedCapabilityError, match="ResponseFormat"):
        to_deepseek_generation_params(
            GenerationRequest(
                **base_request,
                response_format=ResponseFormat(json_schema={"type": "object"}),
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="cache_control"):
        to_deepseek_generation_params(
            GenerationRequest(
                **base_request,
                provider_options={"cache_control": {"type": "ephemeral"}},
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="cache_control"):
        to_deepseek_generation_params(
            GenerationRequest(
                **base_request,
                remote_context=RemoteContextHint(
                    enable_cache=True,
                    provider_options={"cache_control": {"type": "ephemeral"}},
                ),
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="cache_control"):
        to_deepseek_generation_params(
            GenerationRequest(
                **base_request,
                tools=[ToolSpec(name="lookup", provider_options={"cache_control": {"type": "ephemeral"}})],
            )
        )


def test_deepseek_mapper_rejects_unsupported_inputs_and_options() -> None:
    with pytest.raises(InvalidItemError, match="max_tokens"):
        to_deepseek_generation_params(
            GenerationRequest(model="deepseek-chat", items=[MessageItem.user("hello")])
        )

    with pytest.raises(InvalidItemError, match="initial instruction prefix"):
        to_deepseek_generation_params(
            GenerationRequest(
                model="deepseek-chat",
                items=[MessageItem.user("hello"), MessageItem.system("late")],
                generation_config=GenerationConfig(max_output_tokens=32),
            )
        )

    unsupported_parts = (
        ImagePart(url="https://example.test/a.png"),
        AudioPart(url="https://example.test/a.mp3"),
        VideoPart(url="https://example.test/a.mp4"),
        FilePart(url="https://example.test/a.pdf"),
    )
    for part in unsupported_parts:
        with pytest.raises(InvalidItemError, match=type(part).__name__):
            to_deepseek_generation_params(
                GenerationRequest(
                    model="deepseek-chat",
                    items=[MessageItem.user([part])],
                    generation_config=GenerationConfig(max_output_tokens=32),
                )
            )

    with pytest.raises(UnsupportedCapabilityError, match="custom tools"):
        to_deepseek_generation_params(
            GenerationRequest(
                model="deepseek-chat",
                items=[MessageItem.user("run code")],
                tools=[ToolSpec(name="run_code", type=FunctionToolType.CUSTOM)],
                generation_config=GenerationConfig(max_output_tokens=32),
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="parallel_tool_calls=False"):
        to_deepseek_generation_params(
            GenerationRequest(
                model="deepseek-chat",
                items=[MessageItem.user("hello")],
                generation_config=GenerationConfig(max_output_tokens=32),
                tool_call_config=ToolCallConfig(parallel_tool_calls=False),
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="output_format"):
        to_deepseek_generation_params(
            GenerationRequest(
                model="deepseek-chat",
                items=[MessageItem.user("hello")],
                generation_config=GenerationConfig(max_output_tokens=32),
                provider_options={"output_format": {"type": "json_schema"}},
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="output_config.format"):
        to_deepseek_generation_params(
            GenerationRequest(
                model="deepseek-chat",
                items=[MessageItem.user("hello")],
                generation_config=GenerationConfig(max_output_tokens=32),
                provider_options={"output_config": {"format": {"type": "json_schema"}}},
            )
        )


def test_deepseek_reasoning_mapping_and_rejections() -> None:
    params = to_deepseek_generation_params(
        GenerationRequest(
            model="deepseek-reasoner",
            items=[MessageItem.user("think")],
            generation_config=GenerationConfig(max_output_tokens=32),
            reasoning=ReasoningConfig(mode="auto", effort="max"),
        )
    )

    assert params["thinking"] == {"type": "enabled"}
    assert params["output_config"] == {"effort": "max"}

    disabled = to_deepseek_generation_params(
        GenerationRequest(
            model="deepseek-chat",
            items=[MessageItem.user("no thinking")],
            generation_config=GenerationConfig(max_output_tokens=32),
            reasoning=ReasoningConfig(mode="disabled"),
        )
    )

    assert disabled["thinking"] == {"type": "disabled"}
    assert "output_config" not in disabled

    rejection_cases = (
        (ReasoningConfig(budget_tokens=1024), "budget_tokens"),
        (ReasoningConfig(summary="auto"), "summary"),
        (ReasoningConfig(include_trace=True), "include_trace"),
        (ReasoningConfig(provider_options={"x": True}), "provider_options"),
        (ReasoningConfig(effort="low"), "effort"),
        (ReasoningConfig(mode="disabled", effort="high"), "conflicts"),
    )
    for reasoning, message in rejection_cases:
        with pytest.raises(UnsupportedCapabilityError, match=message):
            to_deepseek_generation_params(
                GenerationRequest(
                    model="deepseek-chat",
                    items=[MessageItem.user("hello")],
                    generation_config=GenerationConfig(max_output_tokens=32),
                    reasoning=reasoning,
                )
            )

    with pytest.raises(UnsupportedCapabilityError, match="thinking"):
        to_deepseek_generation_params(
            GenerationRequest(
                model="deepseek-chat",
                items=[MessageItem.user("hello")],
                generation_config=GenerationConfig(max_output_tokens=32),
                reasoning=ReasoningConfig(mode="enabled"),
                provider_options={"thinking": {"type": "enabled"}},
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="output_config"):
        to_deepseek_generation_params(
            GenerationRequest(
                model="deepseek-chat",
                items=[MessageItem.user("hello")],
                generation_config=GenerationConfig(max_output_tokens=32),
                reasoning=ReasoningConfig(effort="high"),
                provider_options={"output_config": {"effort": "max"}},
            )
        )


def test_deepseek_response_maps_content_blocks_usage_and_snapshots() -> None:
    response = SimpleNamespace(
        id="msg_1",
        model="deepseek-reasoner",
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

    mapped = from_deepseek_generation_response(response)

    assert mapped.id == "msg_1"
    assert mapped.provider == "deepseek"
    assert mapped.stop_reason == "tool_use"
    assert isinstance(mapped.output_items[0], MessageItem)
    assert mapped.output_items[0].parts == (TextPart("I will look."),)
    assert isinstance(mapped.output_items[1], FunctionCallItem)
    assert mapped.output_items[1].call_id == "toolu_1"
    assert mapped.output_items[1].arguments == '{"query":"x"}'
    assert isinstance(mapped.output_items[2], ReasoningItem)
    assert mapped.output_items[2].text == "checked options"
    assert mapped.output_items[0].provider_snapshots[0].provider == "deepseek"
    assert mapped.output_items[0].provider_snapshots[0].api_family == "anthropic_messages"
    assert mapped.usage is not None
    assert mapped.usage.input_tokens == 33
    assert mapped.usage.output_tokens == 5
    assert mapped.usage.total_tokens == 38
    assert mapped.usage.cached_tokens == 20
    assert mapped.usage.metadata["provider_input_tokens"] == 3
    assert mapped.usage.metadata["cache_creation_input_tokens"] == 10
    assert mapped.usage.metadata["service_tier"] == "standard"


def test_deepseek_mapper_replays_provider_native_snapshot() -> None:
    response = SimpleNamespace(
        id="msg_1",
        model="deepseek-chat",
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="hello")],
        usage=None,
    )
    mapped = from_deepseek_generation_response(response)

    params = to_deepseek_generation_params(
        GenerationRequest(
            model="deepseek-chat",
            items=[mapped.output_items[0]],
            generation_config=GenerationConfig(max_output_tokens=16),
        )
    )

    assert params["messages"] == [
        {"role": "assistant", "content": [{"type": "text", "text": "hello"}]}
    ]
