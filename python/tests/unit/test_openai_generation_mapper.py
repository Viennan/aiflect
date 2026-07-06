from __future__ import annotations

from types import SimpleNamespace

import pytest

from whero.aiflect import (
    AssistantMessagePhase,
    FunctionResultItem,
    FunctionToolType,
    GenerationConfig,
    GenerationRequest,
    MessageItem,
    ProviderItemSnapshot,
    ReasoningConfig,
    RemoteContextHint,
    ReplayMode,
    ReplayPolicy,
    ResponseFormat,
    Role,
    StreamOptions,
    TextPart,
    ToolCallConfig,
    ToolChoice,
    ToolSpec,
    VideoPart,
)
from whero.aiflect.core.errors import InvalidItemError, ProviderResponseMappingError, UnsupportedCapabilityError
from whero.aiflect.core.items import FunctionCallItem
from whero.aiflect.providers.openai.mapper import (
    from_openai_generation_response,
    to_openai_generation_params,
)


def _openai_anchor(response_id: str = "resp_1") -> MessageItem:
    return MessageItem(
        Role.ASSISTANT,
        "covered",
        provider_snapshots=[
            ProviderItemSnapshot(
                provider="openai",
                api_family="responses",
                item_type="message",
                payload={
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "covered"}],
                },
                metadata={"response_id": response_id},
            )
        ],
    )


def test_generation_request_maps_common_reasoning_and_tool_config() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[
            MessageItem.system("be terse"),
            MessageItem.user([TextPart("hello")]),
            FunctionResultItem(call_id="call_1", output='{"ok":true}'),
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
        generation_config=GenerationConfig(temperature=0.2, max_output_tokens=128),
        reasoning=ReasoningConfig(mode="auto", effort="medium", budget_tokens=1024, summary="auto"),
        tool_call_config=ToolCallConfig(
            parallel_tool_calls=False,
            tool_choice=ToolChoice.AUTO,
        ),
        provider_options={"metadata": {"trace_id": "t-1"}},
    )

    params = to_openai_generation_params(request)

    assert params["model"] == "gpt-test"
    assert params["input"][0]["type"] == "message"
    assert params["input"][0]["role"] == "system"
    assert params["input"][1]["content"] == [{"type": "input_text", "text": "hello"}]
    assert params["input"][2] == {
        "type": "function_call_output",
        "call_id": "call_1",
        "output": '{"ok":true}',
    }
    assert params["tools"] == [
        {
            "type": "function",
            "name": "lookup",
            "description": "Lookup data",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            "strict": True,
        }
    ]
    assert params["temperature"] == 0.2
    assert params["max_output_tokens"] == 128
    assert params["reasoning"] == {
        "mode": "auto",
        "effort": "medium",
        "budget_tokens": 1024,
        "summary": "auto",
    }
    assert params["parallel_tool_calls"] is False
    assert params["tool_choice"] == "auto"
    assert params["metadata"] == {"trace_id": "t-1"}


def test_generation_request_maps_custom_tool_without_parameters() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[
            MessageItem.user("run code"),
            FunctionResultItem(call_id="call_1", output="hello\n", tool_type="custom"),
        ],
        tools=[
            ToolSpec(
                name="run_code",
                description="Run Python code.",
                type="custom",
                parameters_schema={
                    "type": "object",
                    "properties": {"ignored": {"type": "string"}},
                },
                strict=True,
            )
        ],
    )

    params = to_openai_generation_params(request)

    assert params["tools"] == [
        {
            "type": "custom",
            "name": "run_code",
            "description": "Run Python code.",
        }
    ]
    assert params["input"][1] == {
        "type": "custom_tool_call_output",
        "call_id": "call_1",
        "output": "hello\n",
    }


def test_assistant_phase_maps_to_openai_message_phase() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[MessageItem.assistant("working", assistant_phase=AssistantMessagePhase.COMMENTARY)],
    )

    params = to_openai_generation_params(request)

    assert params["input"][0]["phase"] == "commentary"


def test_generation_request_maps_remote_context_hint() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[_openai_anchor(), MessageItem.user("hello")],
        remote_context=RemoteContextHint(
            enable_cache=True,
            session_key="cache-key",
            new_items_start_index=1,
        ),
    )

    params = to_openai_generation_params(request)

    assert params["previous_response_id"] == "resp_1"
    assert len(params["input"]) == 1
    assert params["input"][0]["content"] == [{"type": "input_text", "text": "hello"}]
    assert params["store"] is True
    assert params["prompt_cache_key"] == "cache-key"


def test_openai_generation_mapper_rejects_explicit_prompt_cache_key() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[MessageItem.user("hello")],
        remote_context=RemoteContextHint(
            enable_cache=True,
            provider_options={"prompt_cache_key": "cache-key"},
        ),
    )

    with pytest.raises(UnsupportedCapabilityError, match="prompt_cache_key"):
        to_openai_generation_params(request)


def test_openai_generation_mapper_uses_full_input_without_anchor_response_id() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[MessageItem.assistant("covered"), MessageItem.user("hello")],
        remote_context=RemoteContextHint(enable_cache=True, new_items_start_index=1),
    )

    params = to_openai_generation_params(request)

    assert "previous_response_id" not in params
    assert params["store"] is True
    assert len(params["input"]) == 2


def test_openai_generation_mapper_rejects_empty_remote_context_suffix() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[_openai_anchor()],
        remote_context=RemoteContextHint(enable_cache=True, new_items_start_index=1),
    )

    with pytest.raises(InvalidItemError, match="at least one new item"):
        to_openai_generation_params(request)


def test_openai_generation_mapper_can_build_full_input_without_remote_context() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[_openai_anchor(), MessageItem.user("hello")],
        remote_context=RemoteContextHint(
            enable_cache=True,
            new_items_start_index=1,
        ),
    )

    params = to_openai_generation_params(request, use_remote_context=False)

    assert "previous_response_id" not in params
    assert params["store"] is True
    assert len(params["input"]) == 2
    assert params["input"][0]["role"] == "assistant"
    assert params["input"][1]["role"] == "user"


def test_openai_generation_mapper_rejects_unsupported_new_parts() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[MessageItem.user([VideoPart(url="https://example.test/a.mp4")])],
    )

    with pytest.raises(InvalidItemError):
        to_openai_generation_params(request)



def test_stream_options_include_usage_is_not_mapped_to_openai_stream_options() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[MessageItem.user("hello")],
        stream_options=StreamOptions(include_usage=True),
    )

    params = to_openai_generation_params(request, stream=True)

    assert params["stream"] is True
    assert "stream_options" not in params


def test_provider_specific_stream_options_are_passthrough() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[MessageItem.user("hello")],
        provider_options={"stream_options": {"include_obfuscation": True}},
    )

    params = to_openai_generation_params(request, stream=True)

    assert params["stream_options"] == {"include_obfuscation": True}


def test_provider_options_override_default_params() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[MessageItem.user("hello")],
        generation_config=GenerationConfig(temperature=0.2),
        provider_options={"temperature": 0.7},
    )

    params = to_openai_generation_params(request)

    assert params["temperature"] == 0.7


def test_json_schema_response_format_maps_to_openai_text_format() -> None:
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "additionalProperties": False,
    }
    request = GenerationRequest(
        model="gpt-test",
        items=[MessageItem.user("extract")],
        response_format=ResponseFormat(
            json_schema=schema,
            json_schema_name="person",
            json_schema_description="A person record.",
            json_schema_strict=True,
        ),
    )

    params = to_openai_generation_params(request)

    assert params["text"] == {
        "format": {
            "type": "json_schema",
            "name": "person",
            "description": "A person record.",
            "schema": schema,
            "strict": True,
        }
    }


def test_response_format_does_not_expose_json_mode_selector() -> None:
    with pytest.raises(TypeError):
        ResponseFormat(type="json_object", json_schema={"type": "object"})  # type: ignore[call-arg]


def test_response_format_rejects_provider_json_schema_wrapper() -> None:
    wrapper = {
        "type": "json_schema",
        "name": "wrapped",
        "schema": {"type": "object", "properties": {}},
        "strict": False,
    }

    with pytest.raises(ValueError):
        ResponseFormat(json_schema=wrapper)


def test_openai_response_maps_message_function_call_and_usage() -> None:
    response = SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                id="msg_1",
                role="assistant",
                phase="final_answer",
                content=[
                    SimpleNamespace(type="output_text", text="hello there"),
                ],
            ),
            SimpleNamespace(
                type="function_call",
                id="fc_1",
                name="lookup",
                arguments='{"query":"x"}',
                call_id="call_1",
                status="completed",
            ),
        ],
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            input_tokens_details=SimpleNamespace(cached_tokens=3),
            output_tokens_details=SimpleNamespace(reasoning_tokens=2),
        ),
    )

    mapped = from_openai_generation_response(response)

    assert mapped.id == "resp_1"
    assert mapped.model == "gpt-test"
    assert mapped.stop_reason == "completed"
    assert isinstance(mapped.output_items[0], MessageItem)
    assert mapped.output_items[0].role.value == "assistant"
    assert mapped.output_items[0].assistant_phase == AssistantMessagePhase.FINAL_ANSWER
    assert mapped.output_items[0].parts == (TextPart("hello there"),)
    assert mapped.output_items[0].provider_snapshots[0].payload["phase"] == "final_answer"
    assert mapped.output_items[0].provider_snapshots[0].metadata["response_id"] == "resp_1"
    assert isinstance(mapped.output_items[1], FunctionCallItem)
    assert mapped.output_items[1].name == "lookup"
    assert mapped.output_items[1].call_id == "call_1"
    assert mapped.output_items[1].type == FunctionToolType.FUNCTION
    assert mapped.output_items[1].provider_snapshots[0].payload["type"] == "function_call"
    assert mapped.output_items[1].provider_snapshots[0].metadata["response_id"] == "resp_1"
    assert mapped.usage is not None
    assert mapped.usage.input_tokens == 10
    assert mapped.usage.output_tokens == 5
    assert mapped.usage.cached_tokens == 3
    assert mapped.usage.reasoning_tokens == 2


def test_openai_response_maps_custom_tool_call() -> None:
    response = SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status="completed",
        output=[
            SimpleNamespace(
                type="custom_tool_call",
                id="ctc_1",
                name="run_code",
                input="print('hello')",
                call_id="call_1",
                status="completed",
            )
        ],
        usage=None,
    )

    mapped = from_openai_generation_response(response)

    assert isinstance(mapped.output_items[0], FunctionCallItem)
    assert mapped.output_items[0].type == FunctionToolType.CUSTOM
    assert mapped.output_items[0].name == "run_code"
    assert mapped.output_items[0].input == "print('hello')"
    assert mapped.output_items[0].arguments == "print('hello')"
    assert mapped.output_items[0].provider_snapshots[0].payload["type"] == "custom_tool_call"
    assert mapped.output_items[0].provider_snapshots[0].metadata["response_id"] == "resp_1"


def test_openai_generation_mapper_maps_custom_tool_call_input() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[
            FunctionCallItem(
                name="run_code",
                arguments="print('hello')",
                call_id="call_1",
                type="custom",
            )
        ],
    )

    params = to_openai_generation_params(request)

    assert params["input"][0] == {
        "type": "custom_tool_call",
        "name": "run_code",
        "input": "print('hello')",
        "call_id": "call_1",
    }


def test_openai_generation_mapper_replays_provider_snapshot_payload() -> None:
    response = SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                id="msg_1",
                role="assistant",
                phase="commentary",
                content=[SimpleNamespace(type="output_text", text="working")],
                status="completed",
            )
        ],
        usage=None,
    )
    replay_item = from_openai_generation_response(response).output_items[0]

    params = to_openai_generation_params(
        GenerationRequest(model="gpt-test", items=[replay_item])
    )

    assert params["input"][0] == {
        "type": "message",
        "id": "msg_1",
        "role": "assistant",
        "phase": "commentary",
        "content": [{"type": "output_text", "text": "working"}],
        "status": "completed",
    }


def test_openai_generation_mapper_can_skip_provider_snapshot_replay() -> None:
    response = SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                id="msg_1",
                role="assistant",
                phase="commentary",
                content=[SimpleNamespace(type="output_text", text="working")],
                status="completed",
            )
        ],
        usage=None,
    )
    replay_item = from_openai_generation_response(response).output_items[0]

    params = to_openai_generation_params(
        GenerationRequest(
            model="gpt-test",
            items=[replay_item],
            replay_policy=ReplayPolicy(mode=ReplayMode.NORMALIZED_ONLY),
        )
    )

    assert params["input"][0] == {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "working"}],
        "phase": "commentary",
    }


def test_openai_generation_mapper_requires_provider_snapshot_when_configured() -> None:
    request = GenerationRequest(
        model="gpt-test",
        items=[MessageItem.user("hello")],
        replay_policy=ReplayPolicy(mode=ReplayMode.REQUIRE_PROVIDER_NATIVE),
    )

    with pytest.raises(InvalidItemError):
        to_openai_generation_params(request)


def test_openai_response_records_unsupported_output_items_when_other_items_map() -> None:
    response = SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                id="msg_1",
                role="assistant",
                content=[SimpleNamespace(type="output_text", text="hello")],
            ),
            SimpleNamespace(type="reasoning", id="rs_1", status="completed"),
        ],
        usage=None,
    )

    mapped = from_openai_generation_response(response)

    assert len(mapped.output_items) == 1
    assert mapped.metadata["unsupported_output_items"] == [
        {"id": "rs_1", "type": "reasoning", "status": "completed"}
    ]


def test_openai_response_raises_when_only_unsupported_items_are_returned() -> None:
    response = SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status="completed",
        output=[SimpleNamespace(type="reasoning", id="rs_1", status="completed")],
        usage=None,
    )

    with pytest.raises(ProviderResponseMappingError) as exc_info:
        from_openai_generation_response(response)

    assert exc_info.value.details.provider == "openai"
    assert exc_info.value.details.operation == "responses.create"


def test_openai_response_raises_mapping_error_for_malformed_supported_item() -> None:
    response = SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status="completed",
        output=[SimpleNamespace(type="message", id="msg_1", role="not-a-role", content=[])],
        usage=None,
    )

    with pytest.raises(ProviderResponseMappingError) as exc_info:
        from_openai_generation_response(response)

    assert exc_info.value.details.provider == "openai"
    assert exc_info.value.details.raw is response
