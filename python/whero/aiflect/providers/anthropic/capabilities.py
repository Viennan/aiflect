"""Anthropic adapter capability declarations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from whero.aiflect.core.capabilities import (
    AdapterCapability,
    CapabilityValue,
    GenerationCapability,
    ModelCapability,
    ToolCapability,
)

PROVIDER = "anthropic"


def get_adapter_capability() -> AdapterCapability:
    """Return capabilities implemented by this adapter, independent of model choice."""

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
            input_modalities=CapabilityValue.adapter_builtin(("text", "image")),
            output_modalities=CapabilityValue.adapter_builtin(("text",)),
            structured_output=CapabilityValue.adapter_builtin(True),
            reasoning_config=CapabilityValue.adapter_builtin(True),
            supported_reasoning_efforts=CapabilityValue.adapter_builtin(
                ("low", "medium", "high", "max", "xhigh")
            ),
            reasoning_output=CapabilityValue.adapter_builtin(True),
            remote_context=CapabilityValue.adapter_builtin(True),
            function_tools=CapabilityValue.adapter_builtin(True),
            metadata={
                "api_family": "messages",
                "reasoning_transport": "thinking",
                "reasoning_effort_transport": "output_config.effort",
                "reasoning_manual_budget_model_dependent": True,
                "structured_output_transport": "output_config.format",
                "structured_output_parse_helper": "pydantic_output",
                "structured_output_message_prefill_compatible": False,
                "remote_context_semantics": (
                    "enable_cache maps to Anthropic automatic prompt caching; "
                    "session_key is accepted but not transported; "
                    "new_items_start_index is ignored; no transport delta"
                ),
                "session_key_transport": "ignored",
            },
        ),
        tools=ToolCapability(
            user_function_tools=CapabilityValue.adapter_builtin(True),
            custom_tools=CapabilityValue.adapter_builtin(False),
            parallel_tool_calls=CapabilityValue.adapter_builtin(True),
            tool_choice=CapabilityValue.adapter_builtin(True),
        ),
        metadata={
            "files_api": False,
            "embedding": False,
            "media_generation": False,
            "explicit_cache_control": False,
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
