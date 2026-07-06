"""Capability description models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class CapabilitySource(StrEnum):
    """Where a capability value came from."""

    PROVIDER_API = "provider_api"
    PROVIDER_SDK = "provider_sdk"
    PROVIDER_DOCS = "provider_docs"
    USER_CONFIG = "user_config"
    ADAPTER_BUILTIN = "adapter_builtin"
    RUNTIME_OBSERVED = "runtime_observed"
    UNKNOWN = "unknown"


class CapabilityReliability(StrEnum):
    """Reliability of a capability value."""

    AUTHORITATIVE = "authoritative"
    DECLARED = "declared"
    USER_SUPPLIED = "user_supplied"
    BEST_EFFORT = "best_effort"
    OBSERVED = "observed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CapabilityValue(Generic[T]):
    """A capability value with source and reliability annotations."""

    value: T | None = None
    source: CapabilitySource = CapabilitySource.UNKNOWN
    reliability: CapabilityReliability = CapabilityReliability.UNKNOWN
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_known(self) -> bool:
        return self.value is not None

    @classmethod
    def unknown(cls) -> CapabilityValue[Any]:
        return cls()

    @classmethod
    def adapter_builtin(cls, value: T) -> CapabilityValue[T]:
        return cls(
            value=value,
            source=CapabilitySource.ADAPTER_BUILTIN,
            reliability=CapabilityReliability.DECLARED,
        )

    @classmethod
    def user_supplied(cls, value: T) -> CapabilityValue[T]:
        return cls(
            value=value,
            source=CapabilitySource.USER_CONFIG,
            reliability=CapabilityReliability.USER_SUPPLIED,
        )


@dataclass(frozen=True, slots=True)
class GenerationCapability:
    """Generation API family capability."""

    supported: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    streaming: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    input_modalities: CapabilityValue[tuple[str, ...]] = field(default_factory=CapabilityValue.unknown)
    output_modalities: CapabilityValue[tuple[str, ...]] = field(default_factory=CapabilityValue.unknown)
    structured_output: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    reasoning_config: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supported_reasoning_efforts: CapabilityValue[tuple[str, ...]] = field(default_factory=CapabilityValue.unknown)
    reasoning_output: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    remote_context: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    function_tools: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmbeddingCapability:
    """Embedding API family capability."""

    supported: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    input_modalities: CapabilityValue[tuple[str, ...]] = field(default_factory=CapabilityValue.unknown)
    dense: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    sparse: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    dimensions: CapabilityValue[tuple[int, ...]] = field(default_factory=CapabilityValue.unknown)
    instructions: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResourceCapability:
    """Resource/file API family capability."""

    file_upload: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    file_retrieve: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    file_list: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    file_delete: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    preprocessing: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MediaGenerationCapability:
    """Media generation API family capability."""

    image_generation: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    video_generation: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    streaming: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    async_task: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    output_formats: CapabilityValue[tuple[str, ...]] = field(default_factory=CapabilityValue.unknown)
    image_background_control: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    image_background_values: CapabilityValue[tuple[str, ...]] = field(default_factory=CapabilityValue.unknown)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolCapability:
    """Tool API family capability."""

    user_function_tools: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    custom_tools: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    parallel_tool_calls: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    tool_choice: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AdapterCapability:
    """Capabilities reliably implemented by one provider adapter."""

    provider: str
    supports_generation: bool = False
    supports_stream_generation: bool = False
    supports_async: bool = False
    supports_text_embedding: bool = False
    supports_multimodal_embedding: bool = False
    supports_function_tools: bool = False
    supports_usage_mapping: bool = False
    generation: GenerationCapability | None = None
    embedding: EmbeddingCapability | None = None
    resources: ResourceCapability | None = None
    media_generation: MediaGenerationCapability | None = None
    tools: ToolCapability | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelCapability:
    """Best-known capability profile for a concrete provider/model."""

    provider: str
    model: str
    max_context_tokens: CapabilityValue[int] = field(default_factory=CapabilityValue.unknown)
    max_output_tokens: CapabilityValue[int] = field(default_factory=CapabilityValue.unknown)
    output_dimensions: CapabilityValue[int] = field(default_factory=CapabilityValue.unknown)
    supports_streaming: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supports_tools: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supports_parallel_tool_calls: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supports_tool_choice: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supports_structured_output: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supports_reasoning_config: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supported_reasoning_efforts: CapabilityValue[tuple[str, ...]] = field(default_factory=CapabilityValue.unknown)
    supports_reasoning_budget: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supports_reasoning_summary: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supports_text_embedding: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supports_multimodal_embedding: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    input_modalities: CapabilityValue[tuple[str, ...]] = field(default_factory=CapabilityValue.unknown)
    output_modalities: CapabilityValue[tuple[str, ...]] = field(default_factory=CapabilityValue.unknown)
    supports_remote_context: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supports_sparse_embedding: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supports_file_resources: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supports_image_generation: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    supports_video_generation: CapabilityValue[bool] = field(default_factory=CapabilityValue.unknown)
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_overrides(self, **values: Any) -> ModelCapability:
        fields = self.__dataclass_fields__
        capability_fields = set(fields) - {"provider", "model", "metadata"}
        updates: dict[str, Any] = {
            field_name: getattr(self, field_name)
            for field_name in fields
            if field_name != "metadata"
        }
        updates["metadata"] = dict(self.metadata)
        for key, value in values.items():
            if key not in capability_fields:
                raise ValueError(f"Unknown capability field: {key}")
            updates[key] = (
                value
                if isinstance(value, CapabilityValue)
                else CapabilityValue.user_supplied(value)
            )
        return ModelCapability(**updates)
