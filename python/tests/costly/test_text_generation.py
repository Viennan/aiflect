from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from whero.aiflect import (
    GenerationConfig,
    GenerationStreamAccumulator,
    ImagePart,
    MessageItem,
    ReasoningConfig,
    RemoteContextHint,
    TextPart,
    provider_response_id_for,
)
from whero.aiflect.core.errors import ProviderRequestError
from whero.aiflect.core.generation import StreamEventType


pytestmark = pytest.mark.costly
_SMOKE_TOKEN = "VBTOKEN42"
_CACHE_MARKER = "AIFLECT-CACHE-42"
_CACHE_SESSION_KEY = "aiflect-costly-cache-session"
_STRUCTURED_CODE = "ALPHA42"
_REASONING_MAX_OUTPUT_TOKENS = 2048


class StructuredAnswer(BaseModel):
    code: str
    count: int
    status: str


@pytest.mark.provider("openai")
@pytest.mark.provider("volcengine")
@pytest.mark.provider("anthropic")
@pytest.mark.provider("deepseek")
@pytest.mark.feature("generation")
def test_costly_text_generation_response(costly_client: Any, costly_model_case: Any) -> None:
    _require_text_to_text_generation(costly_model_case)

    response = _generate_or_skip_provider_unavailable(
        costly_client,
        model=costly_model_case.model_id,
        items=[
            MessageItem.system("Answer briefly in plain text."),
            MessageItem.user(
                f"Reply with one short plain-text sentence that includes the token {_SMOKE_TOKEN}."
            ),
        ],
        generation_config=GenerationConfig(max_output_tokens=128),
        reasoning=_reasoning_for(costly_model_case),
    )

    assert response.provider == costly_model_case.provider
    text = _response_text(response)
    assert text.strip()
    assert _SMOKE_TOKEN.lower() in text.lower()
    if response.usage is not None:
        assert response.usage.total_tokens is None or response.usage.total_tokens > 0


@pytest.mark.provider("openai")
@pytest.mark.provider("volcengine")
@pytest.mark.provider("anthropic")
@pytest.mark.provider("deepseek")
@pytest.mark.feature("generation")
def test_costly_text_generation_stream(costly_client: Any, costly_model_case: Any) -> None:
    _require_text_to_text_generation(costly_model_case)
    if not costly_model_case.supports("supports_streaming"):
        pytest.skip("model does not declare streaming support")

    accumulator = GenerationStreamAccumulator(provider=costly_model_case.provider)
    saw_text_event = False
    saw_terminal_event = False
    try:
        for event in costly_client.stream_generate(
            model=costly_model_case.model_id,
            items=[
                MessageItem.user(
                    f"Stream one short plain-text sentence that includes the token {_SMOKE_TOKEN}."
                )
            ],
            generation_config=GenerationConfig(max_output_tokens=128),
            reasoning=_reasoning_for(costly_model_case),
        ):
            assert event.provider == costly_model_case.provider
            accumulator.add(event)
            if event.type in {
                StreamEventType.TEXT_DELTA.value,
                StreamEventType.TEXT_COMPLETED.value,
            }:
                saw_text_event = True
            if event.type in {
                StreamEventType.RESPONSE_COMPLETED.value,
                StreamEventType.RESPONSE_INCOMPLETE.value,
                StreamEventType.RESPONSE_FAILED.value,
                StreamEventType.RESPONSE_ERROR.value,
            }:
                saw_terminal_event = True
    except ProviderRequestError as exc:
        _skip_provider_unavailable(exc)
        raise

    response = accumulator.to_response()
    text = _response_text(response)
    assert saw_text_event
    assert saw_terminal_event
    assert text.strip()


@pytest.mark.provider("openai")
@pytest.mark.provider("volcengine")
@pytest.mark.provider("anthropic")
@pytest.mark.provider("deepseek")
@pytest.mark.feature("generation")
def test_costly_image_to_text_generation(
    costly_client: Any,
    costly_model_case: Any,
    costly_image_asset: Any,
) -> None:
    if not costly_model_case.supports_modality("input_modalities", "image"):
        pytest.skip("model does not declare image input support")
    if not costly_model_case.supports_modality("output_modalities", "text"):
        pytest.skip("model does not declare text output support")

    response = _generate_or_skip_provider_unavailable(
        costly_client,
        model=costly_model_case.model_id,
        items=[
            MessageItem.user(
                [
                    TextPart(
                        "Name one visible animal category in this image. "
                        "Answer with a short word or phrase."
                    ),
                    ImagePart(
                        data=costly_image_asset.data,
                        mime_type=costly_image_asset.mime_type,
                        detail="low",
                    ),
                ]
            )
        ],
        generation_config=GenerationConfig(max_output_tokens=128),
        reasoning=_reasoning_for(costly_model_case),
    )

    assert response.provider == costly_model_case.provider
    text = _response_text(response)
    assert text.strip()
    assert any(token in text.lower() for token in ("seagull", "gull", "bird", "birds", "海鸥", "鸟"))


@pytest.mark.provider("openai")
@pytest.mark.provider("volcengine")
@pytest.mark.provider("anthropic")
@pytest.mark.provider("deepseek")
@pytest.mark.feature("generation")
def test_costly_structured_output_generation(costly_client: Any, costly_model_case: Any) -> None:
    _require_structured_output_generation(costly_model_case)

    try:
        parsed = costly_client.generate_parsed(
            model=costly_model_case.model_id,
            items=[
                MessageItem.system(
                    "Return raw JSON only. Do not use markdown or code fences."
                ),
                MessageItem.user(
                    "Extract this record: code ALPHA42, count 3, status ok."
                ),
            ],
            output_type=StructuredAnswer,
            generation_config=GenerationConfig(max_output_tokens=128),
            reasoning=_reasoning_for(costly_model_case),
        )
    except ProviderRequestError as exc:
        _skip_provider_unavailable(exc)
        raise

    assert parsed.response.provider == costly_model_case.provider
    assert parsed.output_text.strip()
    assert parsed.output_parsed.code == _STRUCTURED_CODE
    assert parsed.output_parsed.count == 3
    assert parsed.output_parsed.status.lower() == "ok"


@pytest.mark.provider("anthropic")
@pytest.mark.feature("generation")
def test_costly_anthropic_reasoning_generation(
    costly_client: Any,
    costly_model_case: Any,
) -> None:
    _require_text_to_text_generation(costly_model_case)
    if not costly_model_case.supports("supports_reasoning_config"):
        pytest.skip("model does not declare reasoning config support")

    response = _generate_or_skip_provider_unavailable(
        costly_client,
        model=costly_model_case.model_id,
        items=[
            MessageItem.system("Answer briefly in plain text."),
            MessageItem.user(
                "Use reasoning if helpful, then reply with one short sentence "
                f"that includes the token {_SMOKE_TOKEN}."
            ),
        ],
        generation_config=GenerationConfig(max_output_tokens=_REASONING_MAX_OUTPUT_TOKENS),
        reasoning=ReasoningConfig(
            mode="auto",
            effort=_reasoning_effort_for(costly_model_case),
            summary="omitted",
        ),
    )

    assert response.provider == "anthropic"
    text = _response_text(response)
    assert text.strip()
    assert _SMOKE_TOKEN.lower() in text.lower()
    if response.usage is not None and response.usage.reasoning_tokens is not None:
        assert response.usage.reasoning_tokens >= 0


@pytest.mark.provider("volcengine")
@pytest.mark.feature("generation")
def test_costly_response_style_cached_multiturn_generation(
    costly_client: Any,
    costly_model_case: Any,
) -> None:
    first_response, second_response = _run_cached_multiturn_generation(
        costly_client,
        costly_model_case,
    )

    assert any(
        provider_response_id_for(
            item,
            provider=costly_model_case.provider,
            api_family="responses",
        )
        for item in first_response.output_items
    )
    remote_context = second_response.metadata.get("remote_context", {})
    assert remote_context.get("attempted_previous_response_id") is True
    assert remote_context.get("final_request_used_previous_response_id") is True
    assert remote_context.get("refreshed_after_invalid_context") is False
    assert _CACHE_MARKER.lower() in _response_text(second_response).lower()


@pytest.mark.provider("volcengine")
@pytest.mark.feature("generation")
def test_costly_volcengine_session_cache_multiturn_generation(
    costly_client: Any,
    costly_model_case: Any,
) -> None:
    if not costly_model_case.supports("supports_session_cache"):
        pytest.skip("model does not declare Volcengine Session cache support")

    _first_response, second_response = _run_cached_multiturn_generation(
        costly_client,
        costly_model_case,
        session_key=_CACHE_SESSION_KEY,
    )

    remote_context = second_response.metadata.get("remote_context", {})
    assert remote_context.get("session_cache_enabled") is True
    assert remote_context.get("session_key_present") is True
    assert remote_context.get("attempted_previous_response_id") is True
    assert remote_context.get("final_request_used_previous_response_id") is True
    assert remote_context.get("refreshed_after_invalid_context") is False
    assert remote_context.get("refreshed_before_expiry") is False
    assert _CACHE_MARKER.lower() in _response_text(second_response).lower()
    if second_response.usage is not None and second_response.usage.cached_tokens is not None:
        assert second_response.usage.cached_tokens >= 0


@pytest.mark.provider("openai")
@pytest.mark.feature("generation")
def test_costly_openai_full_context_cached_multiturn_generation(
    costly_client: Any,
    costly_model_case: Any,
) -> None:
    _first_response, second_response = _run_cached_multiturn_generation(
        costly_client,
        costly_model_case,
        use_new_items_start_index=False,
        session_key=_CACHE_SESSION_KEY,
    )

    remote_context = second_response.metadata.get("remote_context", {})
    assert remote_context.get("session_cache_enabled") is True
    assert remote_context.get("session_key_present") is True
    assert remote_context.get("attempted_previous_response_id") is False
    assert remote_context.get("final_request_used_previous_response_id") is False
    assert remote_context.get("refreshed_after_invalid_context") is False
    assert _CACHE_MARKER.lower() in _response_text(second_response).lower()


@pytest.mark.provider("anthropic")
@pytest.mark.feature("generation")
def test_costly_anthropic_auto_cache_multiturn_generation(
    costly_client: Any,
    costly_model_case: Any,
) -> None:
    _first_response, second_response = _run_cached_multiturn_generation(
        costly_client,
        costly_model_case,
    )

    assert _CACHE_MARKER.lower() in _response_text(second_response).lower()
    if second_response.usage is not None and second_response.usage.cached_tokens is not None:
        assert second_response.usage.cached_tokens >= 0


def _require_text_to_text_generation(costly_model_case: Any) -> None:
    if not costly_model_case.supports_modality("input_modalities", "text"):
        pytest.skip("model does not declare text input support")
    if not costly_model_case.supports_modality("output_modalities", "text"):
        pytest.skip("model does not declare text output support")


def _require_structured_output_generation(costly_model_case: Any) -> None:
    _require_text_to_text_generation(costly_model_case)
    if not costly_model_case.supports("supports_structured_output"):
        pytest.skip("model does not declare structured output support")


def _reasoning_for(costly_model_case: Any) -> ReasoningConfig | None:
    if (
        costly_model_case.provider == "volcengine"
        and costly_model_case.supports("supports_reasoning_config")
    ):
        return ReasoningConfig(mode="disabled")
    if (
        costly_model_case.provider == "deepseek"
        and costly_model_case.supports("supports_reasoning_config")
    ):
        # Keep text smoke tests focused on text; some DeepSeek models spend small
        # max_tokens budgets on thinking unless it is explicitly disabled.
        return ReasoningConfig(mode="disabled")
    return None


def _reasoning_effort_for(costly_model_case: Any) -> str | None:
    efforts = costly_model_case.capabilities.get("supported_reasoning_efforts")
    if not isinstance(efforts, (list, tuple, set)):
        return None
    for effort in ("low", "medium", "high", "max", "xhigh"):
        if effort in efforts:
            return effort
    return None


def _run_cached_multiturn_generation(
    costly_client: Any,
    costly_model_case: Any,
    *,
    use_new_items_start_index: bool = True,
    session_key: str | None = None,
) -> tuple[Any, Any]:
    _require_text_to_text_generation(costly_model_case)

    first_items = [
        MessageItem.system("Answer briefly in plain text."),
        MessageItem.user(
            "Remember this exact marker for the next turn: "
            f"{_CACHE_MARKER}. Reply with exactly ACK."
        ),
    ]
    first_response = _generate_or_skip_provider_unavailable(
        costly_client,
        model=costly_model_case.model_id,
        items=first_items,
        generation_config=GenerationConfig(max_output_tokens=32),
        reasoning=_reasoning_for(costly_model_case),
        remote_context=RemoteContextHint(
            enable_cache=True,
            session_key=session_key,
        ),
    )
    assert first_response.provider == costly_model_case.provider
    assert first_response.output_items
    assert _response_text(first_response).strip()

    history = [*first_items, *first_response.output_items]
    second_remote_context = (
        RemoteContextHint(
            enable_cache=True,
            session_key=session_key,
            new_items_start_index=len(history),
        )
        if use_new_items_start_index
        else RemoteContextHint(
            enable_cache=True,
            session_key=session_key,
        )
    )
    second_response = _generate_or_skip_provider_unavailable(
        costly_client,
        model=costly_model_case.model_id,
        items=[
            *history,
            MessageItem.user(
                "What exact marker did I ask you to remember? Reply with the marker only."
            ),
        ],
        generation_config=GenerationConfig(max_output_tokens=48),
        reasoning=_reasoning_for(costly_model_case),
        remote_context=second_remote_context,
    )
    assert second_response.provider == costly_model_case.provider
    assert second_response.output_items
    assert _response_text(second_response).strip()
    return first_response, second_response


def _generate_or_skip_provider_unavailable(costly_client: Any, **kwargs: Any) -> Any:
    try:
        return costly_client.generate(**kwargs)
    except ProviderRequestError as exc:
        _skip_provider_unavailable(exc)
        raise


def _skip_provider_unavailable(exc: ProviderRequestError) -> None:
    details = exc.details
    status_code = details.status_code
    raw_text = str(details.raw or "").lower()
    cause_text = str(exc.cause or "").lower()
    haystack = f"{raw_text} {cause_text}"
    if status_code is not None and status_code >= 500:
        pytest.skip(
            f"{details.provider or 'provider'} {details.operation or 'request'} "
            f"returned transient status {status_code}"
        )
    if "temporarily unavailable" in haystack or "service unavailable" in haystack:
        pytest.skip(
            f"{details.provider or 'provider'} {details.operation or 'request'} "
            "is temporarily unavailable"
        )


def _response_text(response: Any) -> str:
    chunks: list[str] = []
    for item in response.output_items:
        for part in getattr(item, "parts", ()):
            text = getattr(part, "text", None)
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)
