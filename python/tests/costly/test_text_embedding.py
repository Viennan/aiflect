from __future__ import annotations

from typing import Any

import pytest

from whero.aiflect import EmbeddingInput, ImagePart, TextPart


pytestmark = pytest.mark.costly


@pytest.mark.provider("openai")
@pytest.mark.provider("volcengine")
@pytest.mark.feature("embedding")
def test_costly_text_embedding_dense_vector(costly_client: Any, costly_model_case: Any) -> None:
    if not costly_model_case.supports("supports_text_embedding"):
        pytest.skip("model does not declare text embedding support")

    response = costly_client.embed(
        model=costly_model_case.model_id,
        inputs=["AIFLECT costly text embedding smoke test."],
    )

    _assert_embedding_response(response, costly_model_case)


@pytest.mark.provider("openai")
@pytest.mark.provider("volcengine")
@pytest.mark.feature("embedding")
def test_costly_text_embedding_structured_input(costly_client: Any, costly_model_case: Any) -> None:
    if not costly_model_case.supports("supports_text_embedding"):
        pytest.skip("model does not declare text embedding support")

    kwargs: dict[str, Any] = {
        "model": costly_model_case.model_id,
        "inputs": [
            EmbeddingInput(
                [
                    TextPart("AIFLECT costly embedding structured input."),
                    TextPart("Return a dense float embedding."),
                ]
            )
        ],
        "encoding_format": "float",
    }
    if costly_model_case.provider == "volcengine":
        kwargs["instructions"] = "Represent the input for retrieval."
        kwargs["sparse_embedding"] = False

    response = costly_client.embed(**kwargs)

    _assert_embedding_response(response, costly_model_case)


@pytest.mark.provider("openai")
@pytest.mark.provider("volcengine")
@pytest.mark.feature("embedding")
def test_costly_image_embedding_dense_vector(
    costly_client: Any,
    costly_model_case: Any,
    costly_image_asset: Any,
) -> None:
    if not costly_model_case.supports("supports_multimodal_embedding"):
        pytest.skip("model does not declare multimodal embedding support")
    input_modalities = costly_model_case.capabilities.get("input_modalities")
    if input_modalities is not None and not costly_model_case.supports_modality(
        "input_modalities",
        "image",
    ):
        pytest.skip("model does not declare image embedding input support")

    response = costly_client.embed(
        model=costly_model_case.model_id,
        inputs=[
            EmbeddingInput(
                [
                    TextPart("Represent this image for visual retrieval."),
                    ImagePart(
                        data=costly_image_asset.data,
                        mime_type=costly_image_asset.mime_type,
                    ),
                ],
                modality="image",
            )
        ],
    )

    _assert_embedding_response(response, costly_model_case)


def _assert_embedding_response(response: Any, costly_model_case: Any) -> None:
    assert response.provider == costly_model_case.provider
    assert response.vectors
    vector = response.vectors[0]
    assert isinstance(vector.embedding, list)
    assert vector.embedding
    assert all(isinstance(value, float) for value in vector.embedding[:8])

    expected_dimensions = costly_model_case.capability_int("output_dimensions")
    if expected_dimensions is not None:
        assert vector.dimensions == expected_dimensions
