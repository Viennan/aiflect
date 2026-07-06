"""Embedding request and response models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from whero.aiflect.core.items import ContentPart, MessageItem, TextPart
from whero.aiflect.core.usage import Usage


@dataclass(frozen=True, slots=True)
class EmbeddingInput:
    """One embedding sample made of embedding-compatible content."""

    parts: tuple[ContentPart, ...]
    modality: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        parts: Iterable[ContentPart] | str,
        *,
        modality: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if isinstance(parts, str):
            normalized_parts: tuple[ContentPart, ...] = (TextPart(parts),)
        else:
            normalized_parts = tuple(parts)
        if not normalized_parts:
            raise ValueError("EmbeddingInput.parts must not be empty.")
        object.__setattr__(self, "parts", normalized_parts)
        object.__setattr__(self, "modality", modality)
        object.__setattr__(self, "metadata", dict(metadata or {}))

    @classmethod
    def text(cls, text: str) -> EmbeddingInput:
        return cls(text)

    @classmethod
    def from_message(cls, item: MessageItem) -> EmbeddingInput:
        return cls(item.parts, metadata=item.metadata)


@dataclass(frozen=True, slots=True)
class SparseEmbedding:
    """Sparse embedding coordinates."""

    indices: tuple[int, ...]
    values: tuple[float, ...]
    dimensions: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        indices: Iterable[int],
        values: Iterable[float],
        *,
        dimensions: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        normalized_indices = tuple(indices)
        normalized_values = tuple(float(value) for value in values)
        if len(normalized_indices) != len(normalized_values):
            raise ValueError("SparseEmbedding.indices and values must have the same length.")
        object.__setattr__(self, "indices", normalized_indices)
        object.__setattr__(self, "values", normalized_values)
        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(self, "metadata", dict(metadata or {}))


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    """Embedding request."""

    model: str
    inputs: tuple[EmbeddingInput, ...]
    instructions: str | None = None
    dimensions: int | None = None
    encoding_format: str | None = None
    sparse_embedding: bool | None = None
    provider_options: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        model: str,
        inputs: Iterable[EmbeddingInput | str],
        *,
        instructions: str | None = None,
        dimensions: int | None = None,
        encoding_format: str | None = None,
        sparse_embedding: bool | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> None:
        if not model:
            raise ValueError("EmbeddingRequest.model is required.")
        normalized_inputs = tuple(
            EmbeddingInput.text(item) if isinstance(item, str) else item
            for item in inputs
        )
        if not normalized_inputs:
            raise ValueError("EmbeddingRequest.inputs must not be empty.")
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "inputs", normalized_inputs)
        object.__setattr__(self, "instructions", instructions)
        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(self, "encoding_format", encoding_format)
        object.__setattr__(self, "sparse_embedding", sparse_embedding)
        object.__setattr__(self, "provider_options", dict(provider_options or {}))


class EmbeddingVector:
    """One embedding vector result."""

    index: int
    dense: list[float] | str | None
    sparse: SparseEmbedding | None
    embedding: list[float] | str | None
    encoding_format: str | None
    dimensions: int | None
    metadata: dict[str, Any]
    raw: Any | None

    def __init__(
        self,
        index: int,
        embedding: list[float] | str | None = None,
        *,
        dense: Iterable[float] | str | None = None,
        sparse: SparseEmbedding | None = None,
        encoding_format: str | None = None,
        dimensions: int | None = None,
        metadata: dict[str, Any] | None = None,
        raw: Any | None = None,
    ) -> None:
        normalized_dense: list[float] | str | None
        if dense is None:
            normalized_dense = embedding
        elif isinstance(dense, str):
            normalized_dense = dense
        else:
            normalized_dense = [float(value) for value in dense]
        normalized_embedding = embedding if embedding is not None else normalized_dense
        if dimensions is None and isinstance(normalized_dense, list):
            dimensions = len(normalized_dense)
        object.__setattr__(self, "index", index)
        object.__setattr__(self, "dense", normalized_dense)
        object.__setattr__(self, "sparse", sparse)
        object.__setattr__(self, "embedding", normalized_embedding)
        object.__setattr__(self, "encoding_format", encoding_format)
        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(self, "metadata", dict(metadata or {}))
        object.__setattr__(self, "raw", raw)


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    """Normalized embedding response."""

    provider: str
    model: str | None
    vectors: tuple[EmbeddingVector, ...]
    dimensions: int | None = None
    usage: Usage | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: Any | None = None
