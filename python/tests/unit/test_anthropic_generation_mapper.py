from __future__ import annotations

from types import SimpleNamespace

import pytest

from whero.aiflect import (
    FunctionCallItem,
    FunctionResultItem,
    FunctionToolType,
    GenerationConfig,
    GenerationRequest,
    ImagePart,
    MessageItem,
    RemoteContextHint,
    ResponseFormat,
    ReasoningConfig,
    TextPart,
    ToolCallConfig,
    ToolChoice,
    ToolSpec,
    VideoPart,
)
from whero.aiflect.core.errors import InvalidItemError, UnsupportedCapabilityError
from whero.aiflect.core.items import ReasoningItem
from whero.aiflect.providers.anthropic.mapper import (
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
            enable_cache=True,
            new_items_start_index=2,
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
                arguments='{"query":"aiflect"}',
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
                    "input": {"query": "aiflect"},
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


def test_generation_mapper_maps_response_format_to_output_config() -> None:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "email": {"type": "string"},
        },
        "required": ["name", "email"],
        "additionalProperties": False,
    }
    request = GenerationRequest(
        model="claude-test",
        items=[MessageItem.user("extract")],
        response_format=ResponseFormat(
            json_schema=schema,
            json_schema_name="contact",
            json_schema_description="Extracted contact.",
            json_schema_strict=True,
        ),
        generation_config=GenerationConfig(max_output_tokens=64),
    )

    params = to_anthropic_generation_params(request)

    assert params["output_config"] == {
        "format": {
            "type": "json_schema",
            "schema": schema,
        }
    }


def test_generation_mapper_maps_reasoning_to_thinking_and_merges_output_config() -> None:
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
    }
    request = GenerationRequest(
        model="claude-test",
        items=[MessageItem.user("answer as json")],
        response_format=ResponseFormat(json_schema=schema),
        reasoning=ReasoningConfig(mode="auto", effort="high", summary="auto"),
        generation_config=GenerationConfig(top_p=0.96, max_output_tokens=2048),
    )

    params = to_anthropic_generation_params(request)

    assert params["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert params["output_config"] == {
        "format": {
            "type": "json_schema",
            "schema": schema,
        },
        "effort": "high",
    }


def test_generation_mapper_maps_reasoning_budget_and_disabled_mode() -> None:
    budgeted = to_anthropic_generation_params(
        GenerationRequest(
            model="claude-test",
            items=[MessageItem.user("think carefully")],
            reasoning=ReasoningConfig(budget_tokens=1024, effort="high", summary="omitted"),
            generation_config=GenerationConfig(max_output_tokens=2048),
        )
    )
    disabled = to_anthropic_generation_params(
        GenerationRequest(
            model="claude-test",
            items=[MessageItem.user("plain answer")],
            reasoning=ReasoningConfig(mode="disabled"),
            generation_config=GenerationConfig(temperature=0.2, max_output_tokens=64),
            provider_options={"top_k": 10},
        )
    )

    assert budgeted["thinking"] == {
        "type": "enabled",
        "budget_tokens": 1024,
        "display": "omitted",
    }
    assert budgeted["output_config"] == {"effort": "high"}
    assert disabled["thinking"] == {"type": "disabled"}
    assert disabled["temperature"] == 0.2
    assert disabled["top_k"] == 10


def test_generation_mapper_rejects_invalid_reasoning_options() -> None:
    base_request = {
        "model": "claude-test",
        "items": [MessageItem.user("hello")],
        "generation_config": GenerationConfig(max_output_tokens=2048),
    }

    rejection_cases = [
        (ReasoningConfig(mode="unknown"), UnsupportedCapabilityError, "mode"),
        (ReasoningConfig(effort="minimal"), UnsupportedCapabilityError, "effort"),
        (ReasoningConfig(budget_tokens=512), InvalidItemError, "budget_tokens"),
        (ReasoningConfig(budget_tokens=2048), InvalidItemError, "less than max_tokens"),
        (ReasoningConfig(mode="adaptive", budget_tokens=1024), UnsupportedCapabilityError, "adaptive"),
        (ReasoningConfig(mode="disabled", effort="low"), UnsupportedCapabilityError, "conflicts"),
        (ReasoningConfig(summary="detailed"), UnsupportedCapabilityError, "summary"),
        (ReasoningConfig(include_trace=True), UnsupportedCapabilityError, "include_trace"),
        (
            ReasoningConfig(provider_options={"display": "summarized"}),
            UnsupportedCapabilityError,
            "provider_options",
        ),
    ]
    for reasoning, error_type, message in rejection_cases:
        with pytest.raises(error_type, match=message):
            to_anthropic_generation_params(
                GenerationRequest(**base_request, reasoning=reasoning)
            )

    with pytest.raises(UnsupportedCapabilityError, match="thinking"):
        to_anthropic_generation_params(
            GenerationRequest(
                **base_request,
                reasoning=ReasoningConfig(mode="auto"),
                provider_options={"thinking": {"type": "adaptive"}},
            )
        )


def test_generation_mapper_rejects_active_reasoning_incompatibilities() -> None:
    base_request = {
        "model": "claude-test",
        "items": [MessageItem.user("hello")],
        "reasoning": ReasoningConfig(mode="auto"),
        "generation_config": GenerationConfig(max_output_tokens=2048),
    }

    with pytest.raises(UnsupportedCapabilityError, match="prefilling"):
        to_anthropic_generation_params(
            GenerationRequest(
                **{
                    **base_request,
                    "items": [MessageItem.user("hello"), MessageItem.assistant("partial")],
                }
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="temperature"):
        to_anthropic_generation_params(
            GenerationRequest(
                **{
                    **base_request,
                    "generation_config": GenerationConfig(temperature=0.1, max_output_tokens=2048),
                }
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="top_p"):
        to_anthropic_generation_params(
            GenerationRequest(
                **{
                    **base_request,
                    "generation_config": GenerationConfig(top_p=0.8, max_output_tokens=2048),
                }
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="top_k"):
        to_anthropic_generation_params(
            GenerationRequest(**base_request, provider_options={"top_k": 10})
        )

    with pytest.raises(UnsupportedCapabilityError, match="forced tool_choice"):
        to_anthropic_generation_params(
            GenerationRequest(
                **base_request,
                tool_call_config=ToolCallConfig(tool_choice=ToolChoice.REQUIRED),
            )
        )


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
                    enable_cache=True,
                    new_items_start_index=1,
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


def test_anthropic_mapper_rejects_explicit_structured_output_options() -> None:
    base_request = {
        "model": "claude-test",
        "items": [MessageItem.user("hello")],
        "generation_config": GenerationConfig(max_output_tokens=32),
    }

    with pytest.raises(UnsupportedCapabilityError, match="output_config"):
        to_anthropic_generation_params(
            GenerationRequest(
                **base_request,
                provider_options={"output_config": {"format": {"type": "json_schema"}}},
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="output_format"):
        to_anthropic_generation_params(
            GenerationRequest(
                **base_request,
                remote_context=RemoteContextHint(
                    enable_cache=True,
                    provider_options={"output_format": {"type": "json_schema"}},
                ),
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

    with pytest.raises(UnsupportedCapabilityError, match="prefilling"):
        to_anthropic_generation_params(
            GenerationRequest(
                model="claude-test",
                items=[MessageItem.user("json"), MessageItem.assistant("{")],
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
            output_tokens_details=SimpleNamespace(thinking_tokens=2),
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
    assert mapped.usage.reasoning_tokens == 2
    assert mapped.usage.metadata["provider_input_tokens"] == 3
    assert mapped.usage.metadata["cache_creation_input_tokens"] == 10
    assert mapped.usage.metadata["output_tokens_details"]["thinking_tokens"] == 2
    assert mapped.usage.metadata["service_tier"] == "standard"


def test_anthropic_mapper_replays_provider_native_snapshot() -> None:
    response = SimpleNamespace(
        id="msg_1",
        model="claude-test",
        stop_reason="end_turn",
        content=[
            SimpleNamespace(
                type="text",
                text="hello",
                cache_control={"type": "ephemeral"},
            )
        ],
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
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "hello",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
    ]
