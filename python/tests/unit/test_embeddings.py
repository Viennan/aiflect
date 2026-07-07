from __future__ import annotations

import pytest

from whero.aiflect import EmbeddingInput, EmbeddingRequest, EmbeddingVector, ImagePart, SparseEmbedding


def test_embedding_input_accepts_modality() -> None:
    image = ImagePart(url="https://example.test/a.png")
    metadata = {"source": "fixture"}

    item = EmbeddingInput([image], modality="image", metadata=metadata)
    metadata["source"] = "mutated"

    assert item.parts == (image,)
    assert item.modality == "image"
    assert item.metadata == {"source": "fixture"}


def test_embedding_request_accepts_instructions_and_sparse_flag() -> None:
    request = EmbeddingRequest(
        model="embed-test",
        inputs=["hello"],
        instructions="query: retrieve images",
        sparse_embedding=True,
    )

    assert request.instructions == "query: retrieve images"
    assert request.sparse_embedding is True


def test_sparse_embedding_validates_shape() -> None:
    sparse = SparseEmbedding(indices=[1, 3], values=[0.2, 0.8], dimensions=8)

    assert sparse.indices == (1, 3)
    assert sparse.values == (0.2, 0.8)
    assert sparse.dimensions == 8

    with pytest.raises(ValueError, match="same length"):
        SparseEmbedding(indices=[1], values=[0.2, 0.4])


def test_embedding_vector_keeps_embedding_compatibility_and_dense_alias() -> None:
    vector = EmbeddingVector(index=0, embedding=[1.0, 2.0])

    assert vector.embedding == [1.0, 2.0]
    assert vector.dense == [1.0, 2.0]
    assert vector.dimensions == 2

    sparse = SparseEmbedding(indices=[4], values=[0.5])
    sparse_only = EmbeddingVector(index=1, sparse=sparse)

    assert sparse_only.embedding is None
    assert sparse_only.sparse is sparse
