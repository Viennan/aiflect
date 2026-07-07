from __future__ import annotations

from types import SimpleNamespace

import pytest

from whero.aiflect import EmbeddingInput, EmbeddingRequest, ImagePart, TextPart, VideoPart
from whero.aiflect.core.errors import InvalidItemError, UnsupportedCapabilityError
from whero.aiflect.providers.volcengine.embeddings import (
    from_volcengine_embedding_response,
    to_volcengine_embedding_params,
)


def test_embedding_request_maps_multimodal_parts_and_instructions() -> None:
    request = EmbeddingRequest(
        model="doubao-embedding-vision-test",
        inputs=[
            EmbeddingInput(
                [
                    TextPart("hello"),
                    ImagePart(data="aGVsbG8=", mime_type="image/jpeg"),
                    VideoPart(url="https://example.test/a.mp4", fps=0.2),
                ]
            )
        ],
        instructions="Target_modality: text.",
        dimensions=1024,
        provider_options={
            "trace_id": "trace-1",
            "extra_body": {"custom_flag": True},
        },
    )

    params = to_volcengine_embedding_params(request)

    assert params["model"] == "doubao-embedding-vision-test"
    assert params["encoding_format"] == "float"
    assert params["dimensions"] == 1024
    assert params["extra_body"] == {
        "instructions": "Target_modality: text.",
        "trace_id": "trace-1",
        "custom_flag": True,
    }
    assert params["input"] == [
        {"type": "text", "text": "hello"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,aGVsbG8="}},
        {
            "type": "video_url",
            "video_url": {"url": "https://example.test/a.mp4", "fps": 0.2},
        },
    ]


def test_embedding_request_maps_text_sparse_embedding() -> None:
    request = EmbeddingRequest(
        model="doubao-embedding-vision-test",
        inputs=["hello"],
        sparse_embedding=True,
    )

    params = to_volcengine_embedding_params(request)

    assert params == {
        "model": "doubao-embedding-vision-test",
        "input": [{"type": "text", "text": "hello"}],
        "encoding_format": "float",
        "sparse_embedding": {"type": "enabled"},
    }


def test_embedding_request_rejects_batch_video_file_id_and_sparse_multimodal() -> None:
    with pytest.raises(UnsupportedCapabilityError, match="one vector per request"):
        to_volcengine_embedding_params(
            EmbeddingRequest(model="doubao-embedding-vision-test", inputs=["a", "b"])
        )

    with pytest.raises(InvalidItemError, match="URL/base64"):
        to_volcengine_embedding_params(
            EmbeddingRequest(
                model="doubao-embedding-vision-test",
                inputs=[EmbeddingInput([VideoPart(file_id="file_1")])],
            )
        )

    with pytest.raises(UnsupportedCapabilityError, match="text-only"):
        to_volcengine_embedding_params(
            EmbeddingRequest(
                model="doubao-embedding-vision-test",
                inputs=[
                    EmbeddingInput(
                        [
                            TextPart("hello"),
                            ImagePart(url="https://example.test/a.png"),
                        ]
                    )
                ],
                sparse_embedding=True,
            )
        )


def test_embedding_response_maps_dense_sparse_and_usage() -> None:
    response = SimpleNamespace(
        id="emb_1",
        model="doubao-embedding-vision-test",
        data=SimpleNamespace(
            embedding=[0.1, 0.2],
            sparse_embedding=[
                {"index": 1, "value": 0.3},
                SimpleNamespace(index=3, value=0.4),
            ],
        ),
        usage=SimpleNamespace(
            prompt_tokens=7,
            total_tokens=7,
            prompt_tokens_details=SimpleNamespace(text_tokens=5, image_tokens=2),
        ),
    )

    mapped = from_volcengine_embedding_response(response)

    assert mapped.provider == "volcengine"
    assert mapped.model == "doubao-embedding-vision-test"
    assert mapped.dimensions == 2
    assert mapped.vectors[0].dense == [0.1, 0.2]
    assert mapped.vectors[0].sparse is not None
    assert mapped.vectors[0].sparse.indices == (1, 3)
    assert mapped.vectors[0].sparse.values == (0.3, 0.4)
    assert mapped.usage is not None
    assert mapped.usage.input_tokens == 7
    assert mapped.usage.total_tokens == 7
    assert mapped.usage.metadata["prompt_tokens_details"] == {
        "text_tokens": 5,
        "image_tokens": 2,
    }
