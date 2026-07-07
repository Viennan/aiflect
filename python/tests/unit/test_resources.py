from __future__ import annotations

import pytest

from whero.aiflect import (
    FilePreprocessConfig,
    FileResource,
    FileStatus,
    FileUploadRequest,
)


def test_file_upload_request_accepts_preprocess_config() -> None:
    request = FileUploadRequest(
        file=b"hello",
        filename="hello.txt",
        preprocess=FilePreprocessConfig(
            video_fps=1.0,
            provider_options={"video": {"mode": "sample"}},
        ),
    )

    assert request.preprocess is not None
    assert request.preprocess.video_fps == 1.0
    assert request.preprocess.provider_options == {"video": {"mode": "sample"}}


def test_file_upload_request_does_not_accept_purpose() -> None:
    with pytest.raises(TypeError, match="purpose"):
        FileUploadRequest(file=b"hello", purpose="retrieval")  # type: ignore[call-arg]


def test_file_preprocess_config_does_not_accept_other_options() -> None:
    with pytest.raises(TypeError, match="extract_text"):
        FilePreprocessConfig(extract_text=True)  # type: ignore[call-arg]

    with pytest.raises(TypeError, match="image_detail"):
        FilePreprocessConfig(image_detail="high")  # type: ignore[call-arg]


def test_file_upload_request_requires_file_reference() -> None:
    with pytest.raises(ValueError, match="file is required"):
        FileUploadRequest(file=None)


def test_file_resource_normalizes_status_and_requires_identity() -> None:
    resource = FileResource(
        id="file_1",
        provider="volcengine",
        status="ready",
    )

    assert resource.id == "file_1"
    assert resource.provider == "volcengine"
    assert resource.status == FileStatus.READY

    with pytest.raises(ValueError, match="id is required"):
        FileResource(id="", provider="volcengine")

    with pytest.raises(TypeError, match="purpose"):
        FileResource(id="file_1", provider="volcengine", purpose="media")  # type: ignore[call-arg]
