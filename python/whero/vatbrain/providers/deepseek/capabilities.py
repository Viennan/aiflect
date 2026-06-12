"""DeepSeek adapter capability declarations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from whero.vatbrain.core.capabilities import (
    AdapterCapability,
    CapabilityValue,
    GenerationCapability,
    ModelCapability,
    ToolCapability,
)

PROVIDER = "deepseek"


def get_adapter_capability() -> AdapterCapability:
    """Return capabilities implemented by this adapter in Anthropic-compatible mode."""

    return AdapterCapability(
        provider=PROVIDER,
        supports_generation=True,
        supports_stream_generation=True,
        supports_async=True,
        supports_text_embedding=False,
        supports_multimodal_embedding=False,
        supports_function_tools=True,
        supports_usage_mapping=True,
        generation=GenerationCapability(
            supported=CapabilityValue.adapter_builtin(True),
            streaming=CapabilityValue.adapter_builtin(True),
            input_modalities=CapabilityValue.adapter_builtin(("text",)),
            output_modalities=CapabilityValue.adapter_builtin(("text",)),
            structured_output=CapabilityValue.adapter_builtin(False),
            reasoning_config=CapabilityValue.adapter_builtin(True),
            supported_reasoning_efforts=CapabilityValue.adapter_builtin(("high", "max")),
            reasoning_output=CapabilityValue.adapter_builtin(True),
            remote_context=CapabilityValue.adapter_builtin(False),
            function_tools=CapabilityValue.adapter_builtin(True),
            metadata={
                "api_family": "anthropic_messages",
                "api_format": "anthropic",
                "default_base_url": "https://api.deepseek.com/anthropic",
                "structured_output": "unsupported by DeepSeek Anthropic-compatible endpoint",
                "reasoning_effort_transport": "output_config.effort",
                "remote_context_semantics": (
                    "DeepSeek ignores Anthropic cache_control; session_key is accepted but "
                    "not transported; no remote context transport"
                ),
                "session_key_transport": "ignored",
            },
        ),
        tools=ToolCapability(
            user_function_tools=CapabilityValue.adapter_builtin(True),
            custom_tools=CapabilityValue.adapter_builtin(False),
            parallel_tool_calls=CapabilityValue.adapter_builtin(False),
            tool_choice=CapabilityValue.adapter_builtin(True),
        ),
        metadata={
            "files_api": False,
            "embedding": False,
            "media_generation": False,
            "explicit_cache_control": False,
            "api_formats": ("anthropic", "openai_completion"),
            "implemented_api_formats": ("anthropic",),
        },
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
