"""Media generation request, artifact, stream, and task models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Iterable

from whero.vatbrain.core.generation import StreamOptions
from whero.vatbrain.core.items import Item
from whero.vatbrain.core.usage import Usage


class MediaKind(StrEnum):
    """Media artifact kind."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class TaskStatus(StrEnum):
    """Asynchronous media generation task status."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MediaArtifact:
    """A generated or referenced media artifact."""

    kind: MediaKind | str
    url: str | None = None
    data: str | None = None
    file_id: str | None = None
    mime_type: str | None = None
    format: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    provider: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: Any | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", MediaKind(self.kind))
        if not any((self.url, self.data, self.file_id, self.raw)):
            raise ValueError("MediaArtifact requires url, data, file_id, or raw.")


@dataclass(frozen=True, slots=True)
class ImageGenerationRequest:
    """Image generation request model."""

    model: str
    prompt: str
    input_items: tuple[Item, ...] = ()
    quality: str | None = None
    background: str | None = None
    output_format: str | None = None
    response_format: str | None = None
    count: int | None = None
    watermark: bool = True
    stream_options: StreamOptions | None = None
    provider_options: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        model: str,
        prompt: str,
        *,
        input_items: Iterable[Item] = (),
        quality: str | None = None,
        background: str | None = None,
        output_format: str | None = None,
        response_format: str | None = None,
        count: int | None = None,
        watermark: bool = True,
        stream_options: StreamOptions | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> None:
        if not model:
            raise ValueError("ImageGenerationRequest.model is required.")
        if not prompt:
            raise ValueError("ImageGenerationRequest.prompt is required.")
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "prompt", prompt)
        object.__setattr__(self, "input_items", tuple(input_items))
        object.__setattr__(self, "quality", quality)
        object.__setattr__(self, "background", background)
        object.__setattr__(self, "output_format", output_format)
        object.__setattr__(self, "response_format", response_format)
        object.__setattr__(self, "count", count)
        object.__setattr__(self, "watermark", watermark)
        object.__setattr__(self, "stream_options", stream_options)
        object.__setattr__(self, "provider_options", dict(provider_options or {}))


@dataclass(frozen=True, slots=True)
class ImageGenerationResponse:
    """Normalized image generation response."""

    provider: str
    model: str | None
    artifacts: tuple[MediaArtifact, ...]
    usage: Usage | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: Any | None = None


@dataclass(frozen=True, slots=True)
class VideoGenerationRequest:
    """Video generation request model."""

    model: str
    prompt: str
    input_items: tuple[Item, ...] = ()
    duration_seconds: float | None = None
    ratio: str | None = None
    resolution: str | None = None
    generate_audio: bool | None = None
    watermark: bool = True
    stream_options: StreamOptions | None = None
    provider_options: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        model: str,
        prompt: str,
        *,
        input_items: Iterable[Item] = (),
        duration_seconds: float | None = None,
        ratio: str | None = None,
        resolution: str | None = None,
        generate_audio: bool | None = None,
        watermark: bool = True,
        stream_options: StreamOptions | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> None:
        if not model:
            raise ValueError("VideoGenerationRequest.model is required.")
        if not prompt:
            raise ValueError("VideoGenerationRequest.prompt is required.")
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "prompt", prompt)
        object.__setattr__(self, "input_items", tuple(input_items))
        object.__setattr__(self, "duration_seconds", duration_seconds)
        object.__setattr__(self, "ratio", ratio)
        object.__setattr__(self, "resolution", resolution)
        object.__setattr__(self, "generate_audio", generate_audio)
        object.__setattr__(self, "watermark", watermark)
        object.__setattr__(self, "stream_options", stream_options)
        object.__setattr__(self, "provider_options", dict(provider_options or {}))


@dataclass(frozen=True, slots=True)
class ImageGenerationStreamEvent:
    """Normalized image generation stream event."""

    type: str
    sequence: int
    provider: str
    task_id: str | None = None
    artifact: MediaArtifact | None = None
    delta: Any | None = None
    usage: Usage | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_event: Any | None = None


@dataclass(frozen=True, slots=True)
class MediaGenerationTask:
    """Asynchronous media generation task."""

    id: str
    provider: str
    model: str | None
    status: TaskStatus | str = TaskStatus.UNKNOWN
    artifacts: tuple[MediaArtifact, ...] = ()
    error: str | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: Any | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("MediaGenerationTask.id is required.")
        if not self.provider:
            raise ValueError("MediaGenerationTask.provider is required.")
        if not isinstance(self.status, TaskStatus):
            object.__setattr__(self, "status", TaskStatus(self.status))
