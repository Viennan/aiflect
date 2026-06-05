from __future__ import annotations

import pytest

from whero.vatbrain import CapabilitySource
from whero.vatbrain.core.capabilities import CapabilityValue, GenerationCapability
from whero.vatbrain.providers.anthropic import AnthropicClient
from whero.vatbrain.providers.openai import OpenAIClient
from whero.vatbrain.providers.volcengine import VolcengineClient


def test_openai_adapter_capability_is_provider_level() -> None:
    client = OpenAIClient(client=object(), async_client=object())

    capability = client.get_adapter_capability()

    assert capability.provider == "openai"
    assert capability.supports_generation is True
    assert capability.supports_stream_generation is True
    assert capability.supports_text_embedding is True
    assert capability.supports_multimodal_embedding is False
    assert capability.generation is not None
    assert capability.generation.input_modalities.value == ("text", "image")
    assert capability.generation.supported_reasoning_efforts.value == (
        "none",
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
    )
    assert capability.embedding is not None
    assert capability.embedding.sparse.value is False
    assert capability.media_generation is not None
    assert capability.media_generation.image_generation.value is True
    assert capability.media_generation.video_generation.value is False
    assert capability.media_generation.streaming.value is True
    assert capability.media_generation.image_background_control.value is True
    assert capability.media_generation.image_background_values.value == (
        "auto",
        "transparent",
        "opaque",
    )
    assert capability.tools is not None
    assert capability.tools.user_function_tools.value is True
    assert capability.tools.custom_tools.value is True


def test_volcengine_adapter_capability_declares_media_generation() -> None:
    client = VolcengineClient(client=object(), async_client=object())

    capability = client.get_adapter_capability()

    assert capability.provider == "volcengine"
    assert capability.media_generation is not None
    assert capability.media_generation.image_generation.value is True
    assert capability.media_generation.video_generation.value is True
    assert capability.media_generation.streaming.value is True
    assert capability.media_generation.async_task.value is True
    assert capability.media_generation.output_formats.value == ("png", "jpeg")
    assert capability.media_generation.image_background_control.value is False
    assert capability.media_generation.image_background_values.value == ()


def test_anthropic_adapter_capability_declares_generation_only_surface() -> None:
    client = AnthropicClient(client=object(), async_client=object())

    capability = client.get_adapter_capability()

    assert capability.provider == "anthropic"
    assert capability.supports_generation is True
    assert capability.supports_stream_generation is True
    assert capability.supports_async is True
    assert capability.supports_text_embedding is False
    assert capability.supports_multimodal_embedding is False
    assert capability.supports_function_tools is True
    assert capability.generation is not None
    assert capability.generation.input_modalities.value == ("text", "image")
    assert capability.generation.remote_context.value is True
    assert capability.generation.metadata["remote_context_semantics"].startswith("store maps")
    assert capability.tools is not None
    assert capability.tools.user_function_tools.value is True
    assert capability.tools.custom_tools.value is False


def test_model_capability_defaults_to_unknown_and_accepts_overrides() -> None:
    client = OpenAIClient(
        client=object(),
        async_client=object(),
        model_capability_overrides={
            "gpt-test": {
                "supports_streaming": True,
                "supported_reasoning_efforts": ("low", "medium"),
            },
        },
    )

    capability = client.get_model_capability(
        "gpt-test",
        overrides={"max_context_tokens": 128000},
    )

    assert capability.max_context_tokens.value == 128000
    assert capability.max_context_tokens.source == CapabilitySource.USER_CONFIG
    assert capability.supports_streaming.value is True
    assert capability.supported_reasoning_efforts.value == ("low", "medium")
    assert capability.output_dimensions.value is None
    assert capability.output_dimensions.source == CapabilitySource.UNKNOWN
    assert capability.supports_sparse_embedding.value is None


def test_model_capability_overrides_cannot_replace_identity() -> None:
    client = OpenAIClient(client=object(), async_client=object())

    with pytest.raises(ValueError):
        client.get_model_capability("gpt-test", overrides={"model": "other"})


def test_generation_capability_defaults_to_unknown() -> None:
    capability = GenerationCapability()

    assert capability.supported.value is None
    assert capability.supported.source == CapabilitySource.UNKNOWN
    assert capability.supported_reasoning_efforts.value is None
    assert CapabilityValue.adapter_builtin(True).value is True
