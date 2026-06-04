from __future__ import annotations

from typing import Any

import pytest

from whero.vatbrain import (
    GenerationConfig,
    GenerationStreamAccumulator,
    ImagePart,
    MessageItem,
    ReasoningConfig,
    TextPart,
)
from whero.vatbrain.core.generation import StreamEventType


pytestmark = pytest.mark.costly


@pytest.mark.provider("openai")
@pytest.mark.provider("volcengine")
@pytest.mark.feature("generation")
def test_costly_text_generation_response(costly_client: Any, costly_model_case: Any) -> None:
    _require_text_to_text_generation(costly_model_case)

    response = costly_client.generate(
        model=costly_model_case.model_id,
        items=[
            MessageItem.system("Answer briefly in plain text."),
            MessageItem.user(
                "Reply with one short plain-text sentence that includes the word VATBRAIN."
            ),
        ],
        generation_config=GenerationConfig(max_output_tokens=128),
        reasoning=_reasoning_for(costly_model_case),
    )

    assert response.provider == costly_model_case.provider
    text = _response_text(response)
    assert text.strip()
    assert "vatbrain" in text.lower()
    if response.usage is not None:
        assert response.usage.total_tokens is None or response.usage.total_tokens > 0


@pytest.mark.provider("openai")
@pytest.mark.provider("volcengine")
@pytest.mark.feature("generation")
def test_costly_text_generation_stream(costly_client: Any, costly_model_case: Any) -> None:
    _require_text_to_text_generation(costly_model_case)
    if not costly_model_case.supports("supports_streaming"):
        pytest.skip("model does not declare streaming support")

    accumulator = GenerationStreamAccumulator(provider=costly_model_case.provider)
    saw_text_event = False
    saw_terminal_event = False
    for event in costly_client.stream_generate(
        model=costly_model_case.model_id,
        items=[
            MessageItem.user(
                "Stream one short plain-text sentence that includes the word VATBRAIN."
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

    response = accumulator.to_response()
    text = _response_text(response)
    assert saw_text_event
    assert saw_terminal_event
    assert text.strip()


@pytest.mark.provider("openai")
@pytest.mark.provider("volcengine")
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

    response = costly_client.generate(
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


def _require_text_to_text_generation(costly_model_case: Any) -> None:
    if not costly_model_case.supports_modality("input_modalities", "text"):
        pytest.skip("model does not declare text input support")
    if not costly_model_case.supports_modality("output_modalities", "text"):
        pytest.skip("model does not declare text output support")


def _reasoning_for(costly_model_case: Any) -> ReasoningConfig | None:
    if (
        costly_model_case.provider == "volcengine"
        and costly_model_case.supports("supports_reasoning_config")
    ):
        return ReasoningConfig(mode="disabled")
    return None


def _response_text(response: Any) -> str:
    chunks: list[str] = []
    for item in response.output_items:
        for part in getattr(item, "parts", ()):
            text = getattr(part, "text", None)
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)
