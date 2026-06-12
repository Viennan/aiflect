"""OpenAI adapter capability declarations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from whero.vatbrain.core.capabilities import (
    AdapterCapability,
    CapabilityValue,
    EmbeddingCapability,
    GenerationCapability,
    MediaGenerationCapability,
    ModelCapability,
    ToolCapability,
)

PROVIDER = "openai"


def get_adapter_capability() -> AdapterCapability:
    """Return capabilities implemented by this adapter, independent of model choice."""

    return AdapterCapability(
        provider=PROVIDER,
        supports_generation=True,
        supports_stream_generation=True,
        supports_async=True,
        supports_text_embedding=True,
        supports_multimodal_embedding=False,
        supports_function_tools=True,
        supports_usage_mapping=True,
        generation=GenerationCapability(
            supported=CapabilityValue.adapter_builtin(True),
            streaming=CapabilityValue.adapter_builtin(True),
            input_modalities=CapabilityValue.adapter_builtin(("text", "image")),
            output_modalities=CapabilityValue.adapter_builtin(("text",)),
            structured_output=CapabilityValue.adapter_builtin(True),
            reasoning_config=CapabilityValue.adapter_builtin(True),
            supported_reasoning_efforts=CapabilityValue.adapter_builtin(
                ("none", "minimal", "low", "medium", "high", "xhigh")
            ),
            reasoning_output=CapabilityValue.adapter_builtin(False),
            remote_context=CapabilityValue.adapter_builtin(True),
            function_tools=CapabilityValue.adapter_builtin(True),
            metadata={
                "api_family": "responses",
                "remote_context_semantics": (
                    "enable_cache stores responses; session_key maps to prompt_cache_key; "
                    "new_items_start_index can use previous_response_id"
                ),
                "session_key_transport": "prompt_cache_key",
            },
        ),
        embedding=EmbeddingCapability(
            supported=CapabilityValue.adapter_builtin(True),
            input_modalities=CapabilityValue.adapter_builtin(("text",)),
            dense=CapabilityValue.adapter_builtin(True),
            sparse=CapabilityValue.adapter_builtin(False),
            instructions=CapabilityValue.adapter_builtin(False),
        ),
        media_generation=MediaGenerationCapability(
            image_generation=CapabilityValue.adapter_builtin(True),
            video_generation=CapabilityValue.adapter_builtin(False),
            streaming=CapabilityValue.adapter_builtin(True),
            async_task=CapabilityValue.adapter_builtin(False),
            output_formats=CapabilityValue.adapter_builtin(("png", "jpeg", "webp")),
            image_background_control=CapabilityValue.adapter_builtin(True),
            image_background_values=CapabilityValue.adapter_builtin(
                ("auto", "transparent", "opaque")
            ),
        ),
        tools=ToolCapability(
            user_function_tools=CapabilityValue.adapter_builtin(True),
            custom_tools=CapabilityValue.adapter_builtin(True),
            parallel_tool_calls=CapabilityValue.adapter_builtin(True),
            tool_choice=CapabilityValue.adapter_builtin(True),
        ),
    )


def get_model_capability(
    model: str,
    *,
    overrides: Mapping[str, Any] | None = None,
) -> ModelCapability:
    """Return best-known model capabilities, defaulting volatile model facts to unknown."""

    capability = ModelCapability(provider=PROVIDER, model=model)
    if overrides:
        capability = capability.with_overrides(**dict(overrides))
    return capability
