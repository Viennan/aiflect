"""OpenAI Images API media generation mapping."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any

from whero.aiflect.core.errors import InvalidItemError, UnsupportedCapabilityError
from whero.aiflect.core.items import FilePart, ImagePart, MessageItem
from whero.aiflect.core.media import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageGenerationStreamEvent,
    MediaArtifact,
    MediaKind,
)
from whero.aiflect.core.usage import Usage

PROVIDER = "openai"


def to_openai_image_params(
    request: ImageGenerationRequest,
    *,
    stream: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Convert an aiflect image request into OpenAI Images API parameters."""

    images = _reference_images(request)
    operation = "images.edit" if images else "images.generate"
    params: dict[str, Any] = {
        "model": request.model,
        "prompt": request.prompt,
    }
    if images:
        params["image"] = images[0] if len(images) == 1 else images
    if request.quality is not None:
        params["quality"] = request.quality
    if request.background is not None:
        params["background"] = request.background
    if request.output_format is not None:
        params["output_format"] = request.output_format
    if request.response_format is not None:
        params["response_format"] = request.response_format
    if request.count is not None:
        params["n"] = request.count
    if stream:
        params["stream"] = True
    provider_options = dict(request.provider_options)
    provider_options.pop("watermark", None)
    params.update(provider_options)
    return operation, params


def from_openai_image_response(response: Any) -> ImageGenerationResponse:
    """Convert an OpenAI Images API response into an aiflect response."""

    artifacts = tuple(
        _image_item_to_artifact(item, response=response)
        for item in (_get_attr(response, "data", None) or ())
    )
    return ImageGenerationResponse(
        provider=PROVIDER,
        model=_get_attr(response, "model", None),
        artifacts=artifacts,
        usage=usage_from_openai_image(_get_attr(response, "usage", None)),
        metadata=_image_response_metadata(response),
        raw=response,
    )


def from_openai_image_stream_event(
    event: Any,
    *,
    sequence: int,
) -> ImageGenerationStreamEvent:
    """Convert an OpenAI Images API stream event into a normalized event."""

    event_type = str(_get_attr(event, "type", "") or "")
    usage = usage_from_openai_image(_get_attr(event, "usage", None))
    artifact = _event_artifact(event)
    error = _event_error(event)
    normalized_type = _normalized_stream_type(event_type)
    return ImageGenerationStreamEvent(
        type=normalized_type,
        sequence=sequence,
        provider=PROVIDER,
        artifact=artifact,
        usage=usage,
        error=error,
        metadata=_event_metadata(event),
        raw_event=event,
    )


def usage_from_openai_image(usage: Any | None) -> Usage | None:
    """Normalize OpenAI image usage objects or dictionaries."""

    if usage is None:
        return None
    input_tokens = _get_attr(usage, "input_tokens", None)
    output_tokens = _get_attr(usage, "output_tokens", None)
    total_tokens = _get_attr(usage, "total_tokens", None)
    metadata: dict[str, Any] = {}
    details = _get_attr(usage, "input_tokens_details", None)
    if details is not None:
        image_tokens = _get_attr(details, "image_tokens", None)
        text_tokens = _get_attr(details, "text_tokens", None)
        if image_tokens is not None:
            metadata["image_tokens"] = image_tokens
        if text_tokens is not None:
            metadata["text_tokens"] = text_tokens
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        raw=usage,
        metadata=metadata,
    )


def _reference_images(request: ImageGenerationRequest) -> list[Any]:
    images: list[Any] = []
    for item in request.input_items:
        if not isinstance(item, MessageItem):
            raise InvalidItemError(f"Unsupported OpenAI image input item: {item!r}")
        for part in item.parts:
            if isinstance(part, ImagePart):
                images.append(_image_part_to_openai_file(part, index=len(images)))
            elif isinstance(part, FilePart):
                raise UnsupportedCapabilityError(
                    "OpenAI image edit mapping does not support FilePart references."
                )
            else:
                raise InvalidItemError(f"Unsupported OpenAI image reference part: {part!r}")
    return images


def _image_part_to_openai_file(part: ImagePart, *, index: int) -> tuple[str, bytes, str]:
    if part.url is not None:
        raise UnsupportedCapabilityError(
            "OpenAI image edit requires file content; aiflect does not download image URLs implicitly."
        )
    if part.data is None:
        raise InvalidItemError("ImagePart.data is required for OpenAI image edit references.")
    mime_type, content = _decode_image_data(part.data, default_mime_type=part.mime_type or "image/png")
    extension = _extension_for_mime_type(mime_type)
    return (f"image_{index}.{extension}", content, mime_type)


def _decode_image_data(data: str, *, default_mime_type: str) -> tuple[str, bytes]:
    mime_type = default_mime_type
    payload = data
    if data.startswith("data:"):
        header, separator, encoded = data.partition(",")
        if not separator:
            raise InvalidItemError("Invalid image data URL.")
        payload = encoded
        media_type = header.removeprefix("data:").split(";", 1)[0]
        if media_type:
            mime_type = media_type
    try:
        return mime_type, base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise InvalidItemError("ImagePart.data must contain base64 image data.") from exc


def _image_item_to_artifact(item: Any, *, response: Any) -> MediaArtifact:
    metadata: dict[str, Any] = {}
    revised_prompt = _get_attr(item, "revised_prompt", None)
    if revised_prompt is not None:
        metadata["revised_prompt"] = revised_prompt
    return MediaArtifact(
        kind=MediaKind.IMAGE,
        url=_get_attr(item, "url", None),
        data=_get_attr(item, "b64_json", None),
        format=_get_attr(response, "output_format", None),
        provider=PROVIDER,
        metadata=metadata,
        raw=item,
    )


def _event_artifact(event: Any) -> MediaArtifact | None:
    b64_json = _get_attr(event, "b64_json", None)
    url = _get_attr(event, "url", None)
    if b64_json is None and url is None:
        return None
    metadata: dict[str, Any] = {}
    partial_index = _get_attr(event, "partial_image_index", None)
    if partial_index is not None:
        metadata["partial_image_index"] = partial_index
    size = _get_attr(event, "size", None)
    if size is not None:
        metadata["size"] = size
    return MediaArtifact(
        kind=MediaKind.IMAGE,
        url=url,
        data=b64_json,
        format=_get_attr(event, "output_format", None),
        provider=PROVIDER,
        metadata=metadata,
        raw=event,
    )


def _event_error(event: Any) -> str | None:
    error = _get_attr(event, "error", None)
    if error is None:
        return None
    message = _get_attr(error, "message", None)
    code = _get_attr(error, "code", None)
    if message and code:
        return f"{code}: {message}"
    return str(message or code or error)


def _normalized_stream_type(event_type: str) -> str:
    if event_type.endswith(".partial_image"):
        return "image.partial"
    if event_type.endswith(".completed"):
        return "image.completed"
    if event_type.endswith(".failed") or "error" in event_type:
        return "image.failed"
    return event_type or "unknown"


def _event_metadata(event: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("type", "created_at", "background", "quality", "size"):
        value = _get_attr(event, key, None)
        if value is not None:
            metadata[key] = value
    return metadata


def _image_response_metadata(response: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("created", "background", "quality", "size", "output_format"):
        value = _get_attr(response, key, None)
        if value is not None:
            metadata[key] = value
    return metadata


def _extension_for_mime_type(mime_type: str) -> str:
    if mime_type == "image/jpeg":
        return "jpg"
    if mime_type == "image/webp":
        return "webp"
    return "png"


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)
