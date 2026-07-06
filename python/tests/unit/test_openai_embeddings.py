from __future__ import annotations

from types import SimpleNamespace

import pytest

from whero.aiflect import EmbeddingInput, EmbeddingRequest, ImagePart, TextPart
from whero.aiflect.core.errors import InvalidItemError, UnsupportedCapabilityError
from whero.aiflect.providers.openai.mapper import (
    from_openai_embedding_response,
    to_openai_embedding_params,
)


def test_embedding_request_maps_text_inputs() -> None:
    request = EmbeddingRequest(
        model="text-embedding-test",
        inputs=[EmbeddingInput([TextPart("hello"), TextPart("world")]), "again"],
        dimensions=256,
        encoding_format="float",
    )

    params = to_openai_embedding_params(request)

    assert params == {
        "model": "text-embedding-test",
        "input": ["hello\nworld", "again"],
        "dimensions": 256,
        "encoding_format": "float",
    }


def test_openai_embedding_adapter_rejects_non_text_embedding_input() -> None:
    request = EmbeddingRequest(
        model="text-embedding-test",
        inputs=[EmbeddingInput([ImagePart(url="https://example.test/a.png")])],
    )

    with pytest.raises(InvalidItemError):
        to_openai_embedding_params(request)


def test_openai_embedding_adapter_rejects_instructions_and_sparse_embeddings() -> None:
    with pytest.raises(UnsupportedCapabilityError):
        to_openai_embedding_params(
            EmbeddingRequest(model="text-embedding-test", inputs=["hello"], instructions="query")
        )

    with pytest.raises(UnsupportedCapabilityError):
        to_openai_embedding_params(
            EmbeddingRequest(model="text-embedding-test", inputs=["hello"], sparse_embedding=True)
        )


def test_embedding_response_maps_vectors_and_usage() -> None:
    response = SimpleNamespace(
        model="text-embedding-test",
        data=[
            SimpleNamespace(index=0, embedding=[0.1, 0.2]),
            SimpleNamespace(index=1, embedding=[0.3, 0.4]),
        ],
        usage=SimpleNamespace(prompt_tokens=7, total_tokens=7),
    )

    mapped = from_openai_embedding_response(response)

    assert mapped.model == "text-embedding-test"
    assert mapped.dimensions == 2
    assert [vector.embedding for vector in mapped.vectors] == [[0.1, 0.2], [0.3, 0.4]]
    assert [vector.dense for vector in mapped.vectors] == [[0.1, 0.2], [0.3, 0.4]]
    assert mapped.usage is not None
    assert mapped.usage.input_tokens == 7
    assert mapped.usage.total_tokens == 7


def test_embedding_response_preserves_base64_embedding() -> None:
    response = SimpleNamespace(
        model="text-embedding-test",
        data=[SimpleNamespace(index=0, embedding="YWJj")],
        usage=None,
    )

    mapped = from_openai_embedding_response(response)

    assert mapped.dimensions is None
    assert mapped.vectors[0].embedding == "YWJj"
