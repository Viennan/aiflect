"""Volcengine Ark Files API mapping helpers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from whero.vatbrain.core.errors import UnsupportedCapabilityError
from whero.vatbrain.core.resources import (
    FilePreprocessConfig,
    FileResource,
    FileStatus,
    FileUploadRequest,
)
from whero.vatbrain.providers.volcengine.mapper import PROVIDER


def to_volcengine_file_create_params(request: FileUploadRequest) -> dict[str, Any]:
    """Convert a vatbrain file upload request into Ark Files API parameters."""

    provider_options = dict(request.provider_options)
    purpose = provider_options.pop("purpose", None)
    params: dict[str, Any] = {
        "file": _file_for_sdk(request.file, filename=request.filename, mime_type=request.mime_type),
        "purpose": _purpose_to_volcengine(purpose),
    }
    preprocess_configs = _preprocess_configs(request.preprocess)
    if preprocess_configs:
        params["preprocess_configs"] = preprocess_configs
    params.update(provider_options)
    return params


def to_volcengine_file_list_params(
    *,
    purpose: str | None = None,
    limit: int | None = None,
    after: str | None = None,
    order: str | None = None,
    provider_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert common file-list controls into Ark Files API parameters."""

    params: dict[str, Any] = {}
    if purpose is not None:
        params["purpose"] = _purpose_to_volcengine(purpose)
    if limit is not None:
        params["limit"] = limit
    if after is not None:
        params["after"] = after
    if order is not None:
        params["order"] = order
    params.update(dict(provider_options or {}))
    return params


def from_volcengine_file_resource(file_obj: Any) -> FileResource:
    """Convert an Ark file object into a vatbrain file resource."""

    raw_purpose = _get_attr(file_obj, "purpose", None)
    metadata = {"raw_purpose": raw_purpose}
    error = _get_attr(file_obj, "error", None)
    if error is not None:
        metadata["error"] = _to_plain_data(error)
    return FileResource(
        id=_get_attr(file_obj, "id", ""),
        provider=PROVIDER,
        filename=_get_attr(file_obj, "filename", None),
        mime_type=_get_attr(file_obj, "mime_type", None),
        bytes=_get_attr(file_obj, "bytes", None),
        status=_status_from_volcengine(_get_attr(file_obj, "status", None)),
        created_at=_timestamp_to_datetime(_get_attr(file_obj, "created_at", None)),
        expires_at=_timestamp_to_datetime(_get_attr(file_obj, "expire_at", None)),
        preprocess=_preprocess_from_raw(_get_attr(file_obj, "preprocess_configs", None)),
        metadata=metadata,
        raw=file_obj,
    )


def from_volcengine_file_delete_response(response: Any, *, file_id: str) -> FileResource:
    """Convert an Ark file delete response into a tombstone resource."""

    deleted = bool(_get_attr(response, "deleted", False))
    return FileResource(
        id=_get_attr(response, "id", file_id),
        provider=PROVIDER,
        status=FileStatus.DELETED if deleted else FileStatus.UNKNOWN,
        metadata={"deleted": deleted},
        raw=response,
    )


def _file_for_sdk(file: Any, *, filename: str | None, mime_type: str | None) -> Any:
    content = Path(file) if isinstance(file, str) else file
    if filename is None and mime_type is None:
        return content
    if mime_type is None:
        return (filename, content)
    return (filename, content, mime_type)


def _purpose_to_volcengine(purpose: str | None) -> str:
    if purpose is None:
        return "user_data"
    if purpose == "user_data":
        return "user_data"
    raise UnsupportedCapabilityError(
        "Volcengine Files API currently supports purpose='user_data' only."
    )


def _preprocess_configs(preprocess: FilePreprocessConfig | None) -> dict[str, Any]:
    if preprocess is None:
        return {}
    configs = _deep_copy_mapping(preprocess.provider_options)
    if preprocess.video_fps is not None:
        video_config = dict(configs.get("video", {}) or {})
        video_config["fps"] = preprocess.video_fps
        configs["video"] = video_config
    return configs


def _preprocess_from_raw(value: Any) -> FilePreprocessConfig | None:
    if value is None:
        return None
    raw = _to_plain_data(value)
    video_fps = None
    if isinstance(raw, Mapping):
        video = raw.get("video")
        if isinstance(video, Mapping):
            fps = video.get("fps")
            if fps is not None:
                video_fps = float(fps)
    return FilePreprocessConfig(video_fps=video_fps, provider_options=raw if isinstance(raw, dict) else {})


def _status_from_volcengine(status: Any) -> FileStatus:
    if status in {"active", "processed", "ready", "success"}:
        return FileStatus.READY
    if status == "uploaded":
        return FileStatus.UPLOADED
    if status in {"processing", "in_progress"}:
        return FileStatus.PROCESSING
    if status == "failed":
        return FileStatus.FAILED
    if status == "deleted":
        return FileStatus.DELETED
    if status == "expired":
        return FileStatus.EXPIRED
    return FileStatus.UNKNOWN


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


def _deep_copy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _to_plain_data(item) for key, item in value.items()}


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
