"""Volcengine Ark media generation mapping."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from whero.vatbrain.core.errors import InvalidItemError, UnsupportedCapabilityError
from whero.vatbrain.core.items import (
    AudioPart,
    FilePart,
    ImagePart,
    MessageItem,
    TextPart,
    VideoPart,
)
from whero.vatbrain.core.media import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageGenerationStreamEvent,
    MediaArtifact,
    MediaGenerationTask,
    MediaKind,
    TaskStatus,
    VideoGenerationRequest,
)
from whero.vatbrain.core.usage import Usage
from whero.vatbrain.providers.volcengine.mapper import PROVIDER


def to_volcengine_image_params(
    request: ImageGenerationRequest,
    *,
    stream: bool = False,
) -> dict[str, Any]:
    """Convert a vatbrain image request into Ark Images API parameters."""

    params: dict[str, Any] = {
        "model": request.model,
        "prompt": request.prompt,
        "watermark": request.watermark,
    }
    images = _image_references(request)
    if images:
        params["image"] = images[0] if len(images) == 1 else images
    if request.response_format is not None:
        params["response_format"] = request.response_format
    if request.output_format is not None:
        params["output_format"] = request.output_format
    if stream:
        params["stream"] = True

    provider_options = dict(request.provider_options)
    if request.count is not None:
        sequential_options = dict(
            provider_options.get("sequential_image_generation_options", {}) or {}
        )
        sequential_options.setdefault("max_images", request.count)
        provider_options["sequential_image_generation_options"] = sequential_options
    params.update(provider_options)
    return params


def from_volcengine_image_response(response: Any) -> ImageGenerationResponse:
    """Convert an Ark Images API response into a vatbrain response."""

    artifacts = tuple(
        _image_item_to_artifact(item, response=response)
        for item in (_get_attr(response, "data", None) or ())
    )
    return ImageGenerationResponse(
        provider=PROVIDER,
        model=_get_attr(response, "model", None),
        artifacts=artifacts,
        usage=usage_from_volcengine_image(_get_attr(response, "usage", None)),
        metadata=_image_response_metadata(response),
        raw=response,
    )


def from_volcengine_image_stream_event(
    event: Any,
    *,
    sequence: int,
) -> ImageGenerationStreamEvent:
    """Convert an Ark image stream event into a normalized event."""

    event_type = str(_get_attr(event, "type", "") or "")
    return ImageGenerationStreamEvent(
        type=_normalized_image_stream_type(event_type),
        sequence=sequence,
        provider=PROVIDER,
        artifact=_image_event_artifact(event),
        usage=usage_from_volcengine_image(_get_attr(event, "usage", None)),
        error=_error_message(_get_attr(event, "error", None)),
        metadata=_image_event_metadata(event),
        raw_event=event,
    )


def to_volcengine_video_task_create_params(request: VideoGenerationRequest) -> dict[str, Any]:
    """Convert a vatbrain video request into Ark content generation task parameters."""

    params: dict[str, Any] = {
        "model": request.model,
        "content": _video_content(request),
    }
    if request.duration_seconds is not None:
        params["duration"] = int(request.duration_seconds)
    if request.ratio is not None:
        params["ratio"] = request.ratio
    if request.resolution is not None:
        params["resolution"] = request.resolution
    if request.generate_audio is not None:
        params["generate_audio"] = request.generate_audio
    params["watermark"] = request.watermark
    params.update(request.provider_options)
    return params


def from_volcengine_video_task(task: Any) -> MediaGenerationTask:
    """Convert an Ark content generation task into a vatbrain task."""

    metadata = _video_task_metadata(task)
    error = _error_message(_get_attr(task, "error", None))
    return MediaGenerationTask(
        id=_get_attr(task, "id", ""),
        provider=PROVIDER,
        model=_get_attr(task, "model", None),
        status=_task_status(_get_attr(task, "status", None)),
        artifacts=_video_task_artifacts(task),
        error=error,
        created_at=_timestamp_to_datetime(_get_attr(task, "created_at", None)),
        updated_at=_timestamp_to_datetime(_get_attr(task, "updated_at", None)),
        metadata=metadata,
        raw=task,
    )


def from_volcengine_video_task_create_response(
    response: Any,
    *,
    model: str | None,
) -> MediaGenerationTask:
    """Convert an Ark task-create id response into a queued vatbrain task."""

    return MediaGenerationTask(
        id=_get_attr(response, "id", ""),
        provider=PROVIDER,
        model=model,
        status=TaskStatus.QUEUED,
        metadata=_task_create_metadata(response),
        raw=response,
    )


def usage_from_volcengine_image(usage: Any | None) -> Usage | None:
    """Normalize Ark image usage objects or dictionaries."""

    if usage is None:
        return None
    metadata: dict[str, Any] = {}
    generated_images = _get_attr(usage, "generated_images", None)
    if generated_images is not None:
        metadata["generated_images"] = generated_images
    tool_usage = _get_attr(usage, "tool_usage", None)
    if tool_usage is not None:
        metadata["tool_usage"] = _to_plain_data(tool_usage)
    return Usage(
        output_tokens=_get_attr(usage, "output_tokens", None),
        total_tokens=_get_attr(usage, "total_tokens", None),
        raw=usage,
        metadata=metadata,
    )


def usage_from_volcengine_video(usage: Any | None) -> Usage | None:
    """Normalize Ark video task usage objects or dictionaries."""

    if usage is None:
        return None
    return Usage(
        output_tokens=_get_attr(usage, "completion_tokens", None),
        total_tokens=_get_attr(usage, "total_tokens", None),
        raw=usage,
    )


def _image_references(request: ImageGenerationRequest) -> list[str]:
    images: list[str] = []
    for item in request.input_items:
        if not isinstance(item, MessageItem):
            raise InvalidItemError(f"Unsupported Volcengine image input item: {item!r}")
        for part in item.parts:
            if isinstance(part, ImagePart):
                images.append(_image_reference_value(part))
            else:
                raise InvalidItemError(f"Unsupported Volcengine image reference part: {part!r}")
    return images


def _image_reference_value(part: ImagePart) -> str:
    if part.data is not None:
        return _data_url(part.data, part.mime_type or "image/png")
    if part.url is not None:
        return part.url
    raise InvalidItemError("ImagePart requires url or data.")


def _image_item_to_artifact(item: Any, *, response: Any) -> MediaArtifact:
    size = _get_attr(item, "size", None)
    width, height = _parse_size(size)
    metadata: dict[str, Any] = {}
    if size is not None:
        metadata["size"] = size
    return MediaArtifact(
        kind=MediaKind.IMAGE,
        url=_get_attr(item, "url", None),
        data=_get_attr(item, "b64_json", None),
        format=_get_attr(response, "output_format", None),
        width=width,
        height=height,
        provider=PROVIDER,
        metadata=metadata,
        raw=item,
    )


def _image_event_artifact(event: Any) -> MediaArtifact | None:
    url = _get_attr(event, "url", None)
    b64_json = _get_attr(event, "b64_json", None)
    if url is None and b64_json is None:
        return None
    size = _get_attr(event, "size", None)
    width, height = _parse_size(size)
    metadata: dict[str, Any] = {}
    image_index = _get_attr(event, "image_index", None)
    if image_index is not None:
        metadata["image_index"] = image_index
    if size is not None:
        metadata["size"] = size
    return MediaArtifact(
        kind=MediaKind.IMAGE,
        url=url,
        data=b64_json,
        width=width,
        height=height,
        provider=PROVIDER,
        metadata=metadata,
        raw=event,
    )


def _video_content(request: VideoGenerationRequest) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": request.prompt}]
    for item in request.input_items:
        if not isinstance(item, MessageItem):
            raise InvalidItemError(f"Unsupported Volcengine video input item: {item!r}")
        for part in item.parts:
            if isinstance(part, TextPart):
                content.append({"type": "text", "text": part.text})
            elif isinstance(part, ImagePart):
                content.append(_media_content_part(part, "image_url", "image", "reference_image"))
            elif isinstance(part, VideoPart):
                content.append(_media_content_part(part, "video_url", "video", "reference_video"))
            elif isinstance(part, AudioPart):
                content.append(_media_content_part(part, "audio_url", "audio", "reference_audio"))
            elif isinstance(part, FilePart):
                content.append(_file_content_part(part))
            else:
                raise InvalidItemError(f"Unsupported Volcengine video reference part: {part!r}")
    return content


def _media_content_part(part: Any, content_type: str, attr_prefix: str, default_role: str) -> dict[str, Any]:
    if _get_attr(part, "file_id", None) is not None or _get_attr(part, "local_path", None) is not None:
        raise UnsupportedCapabilityError(
            "Volcengine video generation accepts URL/base64 media references; "
            "upload local/provider files and pass an asset:// URL through the part URL."
        )
    url = _part_url_or_data(part, default_mime_type=_default_mime_type(attr_prefix))
    payload: dict[str, Any] = {"url": url}
    if attr_prefix == "video" and _get_attr(part, "fps", None) is not None:
        payload["fps"] = _get_attr(part, "fps", None)
    metadata = dict(_get_attr(part, "metadata", {}) or {})
    role = metadata.pop("role", default_role)
    item = {"type": content_type, content_type: payload, "role": role}
    item.update(metadata)
    return item


def _file_content_part(part: FilePart) -> dict[str, Any]:
    media_type = (part.media_type or part.mime_type or "").lower()
    if media_type.startswith("image"):
        return _file_content_part_for_media(part, "image_url", "image", "reference_image")
    if media_type.startswith("video"):
        return _file_content_part_for_media(part, "video_url", "video", "reference_video")
    if media_type.startswith("audio"):
        return _file_content_part_for_media(part, "audio_url", "audio", "reference_audio")
    raise InvalidItemError(
        "Volcengine video generation FilePart requires image, video, or audio media_type/mime_type."
    )


def _file_content_part_for_media(
    part: FilePart,
    content_type: str,
    attr_prefix: str,
    default_role: str,
) -> dict[str, Any]:
    if part.file_id is not None or part.local_path is not None:
        raise UnsupportedCapabilityError(
            "Volcengine video generation FilePart references must be URL/base64 data in v0.5."
        )
    url = _part_url_or_data(part, default_mime_type=_default_mime_type(attr_prefix))
    metadata = dict(part.metadata)
    role = metadata.pop("role", default_role)
    item = {"type": content_type, content_type: {"url": url}, "role": role}
    item.update(metadata)
    return item


def _part_url_or_data(part: Any, *, default_mime_type: str) -> str:
    data = _get_attr(part, "data", None)
    if data is not None:
        return _data_url(data, _get_attr(part, "mime_type", None) or default_mime_type)
    url = _get_attr(part, "url", None)
    if url is not None:
        return url
    raise InvalidItemError("Media reference part requires url or data.")


def _video_task_artifacts(task: Any) -> tuple[MediaArtifact, ...]:
    content = _get_attr(task, "content", None)
    artifacts: list[MediaArtifact] = []
    video_url = _get_attr(content, "video_url", None)
    file_url = _get_attr(content, "file_url", None)
    last_frame_url = _get_attr(content, "last_frame_url", None)
    duration = _get_attr(task, "duration", None)
    resolution = _get_attr(task, "resolution", None)
    width, height = _parse_size(resolution)
    video_format = _get_attr(task, "fileformat", None)
    if video_url is not None:
        artifacts.append(
            MediaArtifact(
                kind=MediaKind.VIDEO,
                url=video_url,
                format=video_format,
                width=width,
                height=height,
                duration_seconds=float(duration) if duration is not None else None,
                provider=PROVIDER,
                metadata={"source": "video_url"},
                raw=content,
            )
        )
    if file_url is not None and file_url != video_url:
        artifacts.append(
            MediaArtifact(
                kind=MediaKind.VIDEO,
                url=file_url,
                format=video_format,
                width=width,
                height=height,
                duration_seconds=float(duration) if duration is not None else None,
                provider=PROVIDER,
                metadata={"source": "file_url"},
                raw=content,
            )
        )
    if last_frame_url is not None:
        artifacts.append(
            MediaArtifact(
                kind=MediaKind.IMAGE,
                url=last_frame_url,
                provider=PROVIDER,
                metadata={"source": "last_frame_url"},
                raw=content,
            )
        )
    return tuple(artifacts)


def _task_status(status: Any) -> TaskStatus:
    normalized = str(status or "").lower()
    if normalized in {"queued", "pending"}:
        return TaskStatus.QUEUED
    if normalized in {"running", "processing"}:
        return TaskStatus.RUNNING
    if normalized in {"succeeded", "completed", "success"}:
        return TaskStatus.COMPLETED
    if normalized in {"failed", "failure", "error"}:
        return TaskStatus.FAILED
    if normalized in {"canceled", "cancelled"}:
        return TaskStatus.CANCELED
    if normalized == "expired":
        return TaskStatus.EXPIRED
    return TaskStatus.UNKNOWN


def _normalized_image_stream_type(event_type: str) -> str:
    if (
        event_type.endswith(".generating")
        or event_type.endswith(".partial_succeeded")
        or event_type == "image_generation.generating"
    ):
        return "image.partial"
    if event_type.endswith(".partial_failed") or event_type.endswith(".failed") or "error" in event_type:
        return "image.failed"
    if event_type.endswith(".completed") or event_type == "image_generation.completed":
        return "image.completed"
    return event_type or "unknown"


def _image_event_metadata(event: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("type", "model", "created_at", "image_index", "size"):
        value = _get_attr(event, key, None)
        if value is not None:
            metadata[key] = value
    return metadata


def _image_response_metadata(response: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("created_at", "tool"):
        value = _get_attr(response, key, None)
        if value is not None:
            metadata[key] = _to_plain_data(value)
    error = _get_attr(response, "error", None)
    if error is not None:
        metadata["error"] = _to_plain_data(error)
    return metadata


def _video_task_metadata(task: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    usage = usage_from_volcengine_video(_get_attr(task, "usage", None))
    if usage is not None:
        metadata["usage"] = usage
    for key in (
        "subdivisionlevel",
        "frames",
        "framespersecond",
        "seed",
        "revised_prompt",
        "service_tier",
        "execution_expires_after",
        "priority",
        "generate_audio",
        "duration",
        "ratio",
        "resolution",
        "draft",
        "draft_task_id",
        "tools",
        "safety_identifier",
    ):
        value = _get_attr(task, key, None)
        if value is not None:
            metadata[key] = _to_plain_data(value)
    return metadata


def _task_create_metadata(response: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    safety_identifier = _get_attr(response, "safety_identifier", None)
    if safety_identifier is not None:
        metadata["safety_identifier"] = safety_identifier
    return metadata


def _error_message(error: Any) -> str | None:
    if error is None:
        return None
    message = _get_attr(error, "message", None)
    code = _get_attr(error, "code", None)
    if code and message:
        return f"{code}: {message}"
    return str(message or code or error)


def _data_url(data: str, mime_type: str) -> str:
    if data.startswith("data:"):
        return data
    return f"data:{mime_type};base64,{data}"


def _default_mime_type(prefix: str) -> str:
    if prefix == "image":
        return "image/png"
    if prefix == "audio":
        return "audio/mpeg"
    if prefix == "video":
        return "video/mp4"
    return "application/octet-stream"


def _parse_size(value: Any) -> tuple[int | None, int | None]:
    if not isinstance(value, str) or "x" not in value:
        return None, None
    left, _, right = value.lower().partition("x")
    try:
        return int(left), int(right)
    except ValueError:
        return None, None


def _timestamp_to_datetime(value: Any) -> datetime | str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC)
    if isinstance(value, str):
        return value
    return None


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


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)
