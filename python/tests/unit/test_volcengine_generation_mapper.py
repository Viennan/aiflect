from __future__ import annotations

from types import SimpleNamespace

import pytest

from whero.aiflect import (
    FilePart,
    FunctionCallItem,
    FunctionResultItem,
    FunctionToolType,
    GenerationConfig,
    GenerationRequest,
    ImagePart,
    MessageItem,
    ProviderItemSnapshot,
    ReasoningConfig,
    ReasoningItem,
    RemoteContextHint,
    ReplayMode,
    ReplayPolicy,
    ResponseFormat,
    Role,
    TextPart,
    ToolCallConfig,
    ToolChoice,
    ToolSpec,
    VideoPart,
)
from whero.aiflect.core.errors import UnsupportedCapabilityError
from whero.aiflect.providers.volcengine.mapper import (
    from_volcengine_generation_response,
    to_volcengine_generation_params,
)


def _volcengine_anchor(
    response_id: str = "resp_old",
    *,
    response_expire_at: int | None = None,
) -> MessageItem:
    metadata = {"response_id": response_id}
    if response_expire_at is not None:
        metadata["response_expire_at"] = response_expire_at
    return MessageItem(
        Role.ASSISTANT,
        "covered",
        provider_snapshots=[
            ProviderItemSnapshot(
                provider="volcengine",
                api_family="responses",
                item_type="message",
                payload={
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "covered"}],
                },
                metadata=metadata,
            )
        ],
    )


def test_generation_request_maps_ark_responses_params() -> None:
    request = GenerationRequest(
        model="doubao-test",
        items=[
            _volcengine_anchor(),
            MessageItem.user(
                [
                    TextPart("describe"),
                    ImagePart(url="https://example.test/a.png"),
                    VideoPart(url="https://example.test/a.mp4", fps=0.5),
                    FilePart(file_id="file_1", media_type="application/pdf", filename="a.pdf"),
                ]
            ),
            FunctionResultItem(call_id="call_1", output='{"ok":true}'),
        ],
        tools=[
            ToolSpec(
                name="lookup",
                description="Lookup data",
                parameters_schema={"type": "object", "properties": {"q": {"type": "string"}}},
                strict=True,
            )
        ],
        generation_config=GenerationConfig(temperature=0.2, top_p=0.8, max_output_tokens=128),
        response_format=ResponseFormat(
            json_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
            json_schema_name="answer",
            json_schema_strict=True,
        ),
        reasoning=ReasoningConfig(mode="enabled", effort="low"),
        tool_call_config=ToolCallConfig(parallel_tool_calls=True, tool_choice=ToolChoice.AUTO),
        remote_context=RemoteContextHint(
            enable_cache=True,
            new_items_start_index=1,
        ),
    )

    params = to_volcengine_generation_params(request)

    assert params["model"] == "doubao-test"
    assert params["previous_response_id"] == "resp_old"
    assert params["store"] is True
    assert len(params["input"]) == 2
    assert params["input"][0]["role"] == "user"
    assert params["input"][0]["content"] == [
        {"type": "input_text", "text": "describe"},
        {"type": "input_image", "detail": "auto", "image_url": "https://example.test/a.png"},
        {"type": "input_video", "video_url": "https://example.test/a.mp4", "fps": 0.5},
        {"type": "input_file", "file_id": "file_1", "filename": "a.pdf"},
    ]
    assert params["input"][1] == {
        "type": "function_call_output",
        "call_id": "call_1",
        "output": '{"ok":true}',
    }
    assert params["tools"] == [
        {
            "type": "function",
            "name": "lookup",
            "description": "Lookup data",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
            "strict": True,
        }
    ]
    assert params["thinking"] == {"type": "enabled"}
    assert params["reasoning"] == {"effort": "low"}
    assert params["parallel_tool_calls"] is True
    assert params["tool_choice"] == "auto"
    assert params["text"]["format"]["name"] == "answer"
    assert params["text"]["format"]["strict"] is True


def test_generation_request_routes_sdk_unknown_body_fields_to_extra_body() -> None:
    request = GenerationRequest(
        model="doubao-test",
        items=[MessageItem.user("hello")],
        remote_context=RemoteContextHint(
            provider_options={
                "context_management": {"edits": [{"type": "clear_thinking"}]},
            }
        ),
        provider_options={
            "include": ["reasoning.encrypted_content"],
            "metadata": {"trace_id": "trace-1"},
            "service_tier": "fast",
            "extra_body": {"custom_flag": True},
        },
    )

    params = to_volcengine_generation_params(request)

    assert params["service_tier"] == "fast"
    assert params["extra_body"] == {
        "context_management": {"edits": [{"type": "clear_thinking"}]},
        "include": ["reasoning.encrypted_content"],
        "metadata": {"trace_id": "trace-1"},
        "custom_flag": True,
    }


def test_generation_mapper_rejects_explicit_expire_at() -> None:
    request = GenerationRequest(
        model="doubao-test",
        items=[MessageItem.user("hello")],
        provider_options={"expire_at": 1_800_000_000},
    )

    with pytest.raises(UnsupportedCapabilityError, match="expire_at"):
        to_volcengine_generation_params(request)


def test_generation_mapper_maps_session_cache_params() -> None:
    request = GenerationRequest(
        model="doubao-test",
        items=[_volcengine_anchor(response_expire_at=1_800_003_700), MessageItem.user("hello")],
        remote_context=RemoteContextHint(
            enable_cache=True,
            session_key="session-1",
            new_items_start_index=1,
        ),
    )

    params = to_volcengine_generation_params(request, now=1_800_000_000)

    assert params["previous_response_id"] == "resp_old"
    assert params["store"] is True
    assert params["caching"] == {"type": "enabled"}
    assert params["expire_at"] == 1_800_003_600
    assert len(params["input"]) == 1


def test_generation_mapper_refreshes_session_cache_before_previous_response_expiry() -> None:
    request = GenerationRequest(
        model="doubao-test",
        items=[_volcengine_anchor(response_expire_at=1_800_000_299), MessageItem.user("hello")],
        remote_context=RemoteContextHint(
            enable_cache=True,
            session_key="session-1",
            new_items_start_index=1,
        ),
    )

    params = to_volcengine_generation_params(request, now=1_800_000_000)

    assert "previous_response_id" not in params
    assert params["caching"] == {"type": "enabled"}
    assert params["expire_at"] == 1_800_003_600
    assert len(params["input"]) == 2


def test_generation_mapper_rejects_session_cache_conflicting_fields() -> None:
    request = GenerationRequest(
        model="doubao-test",
        items=[MessageItem.user("hello")],
        remote_context=RemoteContextHint(
            enable_cache=True,
            session_key="session-1",
        ),
        provider_options={"caching": {"type": "enabled"}},
    )

    with pytest.raises(UnsupportedCapabilityError, match="caching"):
        to_volcengine_generation_params(request)


def test_generation_mapper_can_replay_without_remote_context() -> None:
    request = GenerationRequest(
        model="doubao-test",
        items=[_volcengine_anchor(), MessageItem.user("hello")],
        remote_context=RemoteContextHint(enable_cache=True, new_items_start_index=1),
    )

    params = to_volcengine_generation_params(request, use_remote_context=False)

    assert "previous_response_id" not in params
    assert params["store"] is True
    assert len(params["input"]) == 2
    assert params["input"][0]["role"] == "assistant"


def test_generation_mapper_rejects_custom_tools() -> None:
    custom_tool_request = GenerationRequest(
        model="doubao-test",
        items=[MessageItem.user("run code")],
        tools=[ToolSpec(name="run_code", type=FunctionToolType.CUSTOM)],
    )
    with pytest.raises(UnsupportedCapabilityError, match="custom tools"):
        to_volcengine_generation_params(custom_tool_request)


def test_generation_mapper_can_replay_normalized_reasoning_summary() -> None:
    request = GenerationRequest(
        model="doubao-test",
        items=[ReasoningItem(id="rs_1", summary="prior thinking", status="completed")],
        replay_policy=ReplayPolicy(mode=ReplayMode.NORMALIZED_ONLY),
    )

    params = to_volcengine_generation_params(request)

    assert params["input"] == [
        {
            "type": "reasoning",
            "summary": [{"type": "summary_text", "text": "prior thinking"}],
            "id": "rs_1",
            "status": "completed",
        }
    ]


def test_generation_mapper_maps_partial_assistant_message_metadata() -> None:
    request = GenerationRequest(
        model="doubao-test",
        items=[MessageItem("assistant", "def bubble_sort(arr):", metadata={"partial": True})],
    )

    params = to_volcengine_generation_params(request)

    assert params["input"][0]["role"] == "assistant"
    assert params["input"][0]["partial"] is True


def test_generation_mapper_maps_function_result_status_metadata() -> None:
    request = GenerationRequest(
        model="doubao-test",
        items=[
            FunctionResultItem(
                call_id="call_1",
                output='{"ok":true}',
                metadata={"status": "completed"},
            )
        ],
    )

    params = to_volcengine_generation_params(request)

    assert params["input"] == [
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": '{"ok":true}',
            "status": "completed",
        }
    ]


def test_generation_response_maps_reasoning_function_call_output_and_snapshots() -> None:
    response = SimpleNamespace(
        id="resp_1",
        model="doubao-test",
        status="completed",
        created_at=1_800_000_000,
        expire_at=1_800_003_600,
        caching=SimpleNamespace(type="enabled"),
        store=True,
        output=[
            SimpleNamespace(
                type="reasoning",
                id="rs_1",
                status="completed",
                summary=[SimpleNamespace(type="summary_text", text="I checked the premise.")],
            ),
            SimpleNamespace(
                type="message",
                id="msg_1",
                role="assistant",
                content=[SimpleNamespace(type="output_text", text="done")],
            ),
            SimpleNamespace(
                type="function_call",
                id="fc_1",
                name="lookup",
                arguments='{"q":"x"}',
                call_id="call_1",
                status="completed",
            ),
            SimpleNamespace(
                type="function_call_output",
                id="fco_1",
                call_id="call_1",
                output='{"ok":true}',
            ),
        ],
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            output_tokens_details=SimpleNamespace(reasoning_tokens=2),
            tool_usage=SimpleNamespace(function_calls=1),
        ),
    )

    mapped = from_volcengine_generation_response(response)

    assert mapped.id == "resp_1"
    assert isinstance(mapped.output_items[0], ReasoningItem)
    assert mapped.output_items[0].summary == "I checked the premise."
    assert mapped.output_items[0].provider_snapshots[0].payload["type"] == "reasoning"
    assert mapped.output_items[0].provider_snapshots[0].metadata["response_id"] == "resp_1"
    assert mapped.output_items[0].provider_snapshots[0].metadata["response_expire_at"] == 1_800_003_600
    assert mapped.output_items[0].provider_snapshots[0].metadata["response_caching"] == {"type": "enabled"}
    assert mapped.output_items[0].provider_snapshots[0].metadata["response_store"] is True
    assert mapped.output_items[1].provider_snapshots[0].metadata["response_id"] == "resp_1"
    assert isinstance(mapped.output_items[2], FunctionCallItem)
    assert mapped.output_items[2].name == "lookup"
    assert mapped.output_items[2].provider_snapshots[0].metadata["response_id"] == "resp_1"
    assert isinstance(mapped.output_items[3], FunctionResultItem)
    assert mapped.output_items[3].provider_snapshots[0].metadata["response_id"] == "resp_1"
    assert mapped.usage is not None
    assert mapped.usage.reasoning_tokens == 2
    assert mapped.usage.metadata["tool_usage"] == {"function_calls": 1}

    replay_params = to_volcengine_generation_params(
        GenerationRequest(model="doubao-test", items=[mapped.output_items[0]])
    )
    assert replay_params["input"][0]["type"] == "reasoning"
