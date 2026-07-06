from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from whero.aiflect import FilePreprocessConfig, FileStatus, FileUploadRequest
from whero.aiflect.core.errors import UnsupportedCapabilityError
from whero.aiflect.providers.volcengine.files import (
    from_volcengine_file_delete_response,
    from_volcengine_file_resource,
    to_volcengine_file_create_params,
    to_volcengine_file_list_params,
)


def test_file_upload_request_maps_user_data_and_preprocess_configs() -> None:
    request = FileUploadRequest(
        file="video.mp4",
        filename="video.mp4",
        mime_type="video/mp4",
        preprocess=FilePreprocessConfig(
            video_fps=0.3,
            provider_options={"video": {"mode": "sample"}},
        ),
        provider_options={"expire_at": 1_800_000_000},
    )

    params = to_volcengine_file_create_params(request)

    assert params["purpose"] == "user_data"
    assert params["file"] == ("video.mp4", Path("video.mp4"), "video/mp4")
    assert params["preprocess_configs"] == {"video": {"mode": "sample", "fps": 0.3}}
    assert params["expire_at"] == 1_800_000_000


def test_file_upload_request_maps_provider_purpose_option() -> None:
    request = FileUploadRequest(
        file=b"data",
        provider_options={"purpose": "user_data", "expire_at": 1_800_000_000},
    )

    params = to_volcengine_file_create_params(request)

    assert params["purpose"] == "user_data"
    assert params["expire_at"] == 1_800_000_000


def test_file_upload_request_rejects_unknown_provider_purpose() -> None:
    request = FileUploadRequest(file=b"data", provider_options={"purpose": "retrieval"})

    with pytest.raises(UnsupportedCapabilityError, match="user_data"):
        to_volcengine_file_create_params(request)


def test_file_list_params_map_purpose_and_provider_options() -> None:
    params = to_volcengine_file_list_params(
        purpose="user_data",
        limit=10,
        after="file_prev",
        order="desc",
        provider_options={"extra_query": {"trace": "1"}},
    )

    assert params == {
        "purpose": "user_data",
        "limit": 10,
        "after": "file_prev",
        "order": "desc",
        "extra_query": {"trace": "1"},
    }


def test_file_resource_maps_status_purpose_timestamps_and_preprocess() -> None:
    raw = SimpleNamespace(
        id="file_1",
        filename="video.mp4",
        purpose="user_data",
        mime_type="video/mp4",
        bytes=123,
        status="active",
        created_at=1_700_000_000,
        expire_at=1_700_086_400,
        preprocess_configs={"video": {"fps": 0.3}},
    )

    mapped = from_volcengine_file_resource(raw)

    assert mapped.id == "file_1"
    assert mapped.provider == "volcengine"
    assert mapped.metadata["raw_purpose"] == "user_data"
    assert mapped.status == FileStatus.READY
    assert mapped.created_at is not None
    assert mapped.expires_at is not None
    assert mapped.preprocess is not None
    assert mapped.preprocess.video_fps == 0.3


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        ("uploaded", FileStatus.UPLOADED),
        ("processing", FileStatus.PROCESSING),
        ("in_progress", FileStatus.PROCESSING),
        ("active", FileStatus.READY),
        ("processed", FileStatus.READY),
        ("ready", FileStatus.READY),
        ("success", FileStatus.READY),
        ("failed", FileStatus.FAILED),
        ("expired", FileStatus.EXPIRED),
        ("deleted", FileStatus.DELETED),
    ],
)
def test_file_resource_maps_documented_and_sdk_statuses(
    raw_status: str,
    expected: FileStatus,
) -> None:
    mapped = from_volcengine_file_resource(SimpleNamespace(id="file_1", status=raw_status))

    assert mapped.status == expected


def test_file_delete_response_maps_tombstone_resource() -> None:
    mapped = from_volcengine_file_delete_response(
        SimpleNamespace(id="file_1", deleted=True),
        file_id="file_1",
    )

    assert mapped.id == "file_1"
    assert mapped.status == FileStatus.DELETED
    assert mapped.metadata["deleted"] is True
