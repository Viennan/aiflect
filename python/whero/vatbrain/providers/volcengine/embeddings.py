"""Volcengine multimodal embedding request and response mapping."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from whero.vatbrain.core.embeddings import (
    EmbeddingInput,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingVector,
    SparseEmbedding,
)
from whero.vatbrain.core.errors import InvalidItemError, UnsupportedCapabilityError
from whero.vatbrain.core.items import ImagePart, TextPart, VideoPart
from whero.vatbrain.core.usage import Usage
from whero.vatbrain.providers.volcengine.mapper import PROVIDER

_EMBEDDING_SDK_PARAMS = {
    "input",
    "model",
    "encoding_format",
    "dimensions",
    "sparse_embedding",
    "extra_headers",
    "extra_query",
    "extra_body",
    "timeout",
}


def to_volcengine_embedding_params(request: EmbeddingRequest) -> dict[str, Any]:
    """Convert a vatbrain embedding request into Ark multimodal embedding parameters."""

    if len(request.inputs) != 1:
        raise UnsupportedCapabilityError(
            "Volcengine multimodal embeddings return one vector per request; "
            "submit one EmbeddingInput at a time."
        )

    provider_options = dict(request.provider_options)
    extra_body = dict(provider_options.pop("extra_body", {}) or {})
    if request.instructions is not None:
        extra_body = {"instructions": request.instructions, **extra_body}

    params: dict[str, Any] = {
        "model": request.model,
        "input": _embedding_input_to_volcengine_parts(request.inputs[0]),
        "encoding_format": request.encoding_format or "float",
    }
    if request.dimensions is not None:
        params["dimensions"] = request.dimensions
    if request.sparse_embedding is not None:
        if not _is_text_only_input(request.inputs[0]):
            raise UnsupportedCapabilityError(
                "Volcengine sparse embeddings are supported only for text-only input."
            )
        params["sparse_embedding"] = {
            "type": "enabled" if request.sparse_embedding else "disabled"
        }
    if extra_body:
        params["extra_body"] = extra_body
    _merge_sdk_provider_options(params, provider_options, sdk_params=_EMBEDDING_SDK_PARAMS)
    return params


def from_volcengine_embedding_response(response: Any) -> EmbeddingResponse:
    """Convert an Ark multimodal embedding response into a vatbrain response."""

    data_items = _embedding_data_items(_get_attr(response, "data", None))
    vectors = tuple(
        EmbeddingVector(
            index=index,
            embedding=_embedding_value(_get_attr(item, "embedding", None)),
            sparse=_sparse_embedding(_get_attr(item, "sparse_embedding", None)),
            raw=item,
        )
        for index, item in enumerate(data_items)
    )
    dimensions = None
    if vectors:
        dimensions = vectors[0].dimensions
    return EmbeddingResponse(
        provider=PROVIDER,
        model=_get_attr(response, "model", None),
        vectors=vectors,
        dimensions=dimensions,
        usage=usage_from_volcengine_embedding(_get_attr(response, "usage", None)),
        raw=response,
    )


def usage_from_volcengine_embedding(usage: Any | None) -> Usage | None:
    """Normalize Ark multimodal embedding usage objects or dictionaries."""

    if usage is None:
        return None
    input_tokens = _get_attr(usage, "input_tokens", None)
    if input_tokens is None:
        input_tokens = _get_attr(usage, "prompt_tokens", None)
    total_tokens = _get_attr(usage, "total_tokens", None)
    details = _get_attr(usage, "prompt_tokens_details", None)
    metadata: dict[str, Any] = {}
    if details is not None:
        metadata["prompt_tokens_details"] = _to_plain_data(details)
    return Usage(input_tokens=input_tokens, total_tokens=total_tokens, raw=usage, metadata=metadata)


def _embedding_input_to_volcengine_parts(item: EmbeddingInput) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for part in item.parts:
        if isinstance(part, TextPart):
            parts.append({"type": "text", "text": part.text})
        elif isinstance(part, ImagePart):
            image_url = _data_url(part.data, part.mime_type or "image/png") if part.data else part.url
            parts.append({"type": "image_url", "image_url": {"url": image_url}})
        elif isinstance(part, VideoPart):
            if part.file_id is not None or part.local_path is not None:
                raise InvalidItemError(
                    "Volcengine multimodal embeddings accept video URL/base64 data only."
                )
            video_url = _data_url(part.data, part.mime_type or "video/mp4") if part.data else part.url
            payload: dict[str, Any] = {"url": video_url}
            if part.fps is not None:
                payload["fps"] = part.fps
            parts.append({"type": "video_url", "video_url": payload})
        else:
            raise InvalidItemError(f"Unsupported Volcengine embedding part: {part!r}")
    return parts


def _is_text_only_input(item: EmbeddingInput) -> bool:
    return all(isinstance(part, TextPart) for part in item.parts)


def _embedding_data_items(data: Any) -> tuple[Any, ...]:
    if data is None:
        return ()
    if isinstance(data, list):
        return tuple(data)
    if isinstance(data, tuple):
        return data
    return (data,)


def _embedding_value(value: Any) -> list[float] | str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return [float(item) for item in value]


def _sparse_embedding(value: Any) -> SparseEmbedding | None:
    if value is None:
        return None
    items = _sparse_items(value)
    indices: list[int] = []
    values: list[float] = []
    for item in items:
        index = _get_attr(item, "index", None)
        sparse_value = _get_attr(item, "value", None)
        if index is None or sparse_value is None:
            continue
        indices.append(int(index))
        values.append(float(sparse_value))
    if not indices and not values:
        return None
    return SparseEmbedding(indices, values, metadata={"provider_shape": _sparse_shape(value)})


def _sparse_items(value: Any) -> tuple[Any, ...]:
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, tuple):
        return value
    if isinstance(value, Mapping) and "index" not in value and "value" not in value:
        return tuple({"index": key, "value": item} for key, item in value.items())
    return (value,)


def _sparse_shape(value: Any) -> str:
    if isinstance(value, list):
        return "list"
    if isinstance(value, tuple):
        return "tuple"
    if isinstance(value, Mapping):
        return "mapping"
    return "object"


def _merge_sdk_provider_options(
    params: dict[str, Any],
    options: Mapping[str, Any],
    *,
    sdk_params: set[str],
) -> None:
    extra_body = dict(params.get("extra_body", {}) or {})
    for key, value in options.items():
        if key == "extra_body":
            extra_body.update(dict(value or {}))
        elif key in sdk_params:
            params[key] = value
        else:
            extra_body[key] = value
    if extra_body:
        params["extra_body"] = extra_body


def _to_plain_data(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain_data(item) for item in value]
    if isinstance(value, tuple):
        return [_to_plain_data(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "model_dump"):
        return _to_plain_data(value.model_dump(exclude_none=True))
    if hasattr(value, "to_dict"):
        return _to_plain_data(value.to_dict())
    if hasattr(value, "__dict__"):
        return {
            str(key): _to_plain_data(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return value


def _data_url(data: str | None, mime_type: str) -> str | None:
    if data is None:
        return None
    if data.startswith("data:"):
        return data
    return f"data:{mime_type};base64,{data}"


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)
