from __future__ import annotations

import pytest

from whero.aiflect import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    MediaArtifact,
    MediaGenerationTask,
    MediaKind,
    TaskStatus,
    VideoGenerationRequest,
)
from whero.aiflect.core.tools import ToolSpec


def test_media_artifact_requires_a_reference() -> None:
    artifact = MediaArtifact(kind="image", url="https://example.test/a.png", width=512, height=512)

    assert artifact.kind == MediaKind.IMAGE
    assert artifact.url == "https://example.test/a.png"
    assert artifact.width == 512
    assert artifact.height == 512

    with pytest.raises(ValueError, match="requires url, data, file_id, or raw"):
        MediaArtifact(kind="image")


def test_image_generation_request_and_response_construct() -> None:
    request = ImageGenerationRequest(
        model="image-test",
        prompt="a small robot",
        count=2,
        quality="high",
        background="transparent",
        output_format="png",
    )
    artifact = MediaArtifact(kind=MediaKind.IMAGE, data="abc")
    response = ImageGenerationResponse(provider="test", model="image-test", artifacts=(artifact,))

    assert request.prompt == "a small robot"
    assert request.count == 2
    assert request.quality == "high"
    assert request.background == "transparent"
    assert request.watermark is True
    assert response.artifacts == (artifact,)


def test_image_generation_request_accepts_watermark_control() -> None:
    request = ImageGenerationRequest(
        model="image-test",
        prompt="a small robot",
        count=1,
        output_format="png",
        watermark=False,
        provider_options={"seed": 42},
    )

    assert request.model == "image-test"
    assert request.prompt == "a small robot"
    assert request.count == 1
    assert request.output_format == "png"
    assert request.watermark is False
    assert request.provider_options == {"seed": 42}


def test_image_generation_request_does_not_accept_tools() -> None:
    with pytest.raises(TypeError, match="tools"):
        ImageGenerationRequest(  # type: ignore[call-arg]
            model="image-test",
            prompt="a small robot",
            tools=[ToolSpec(name="lookup")],
        )


def test_image_generation_request_does_not_accept_size() -> None:
    with pytest.raises(TypeError, match="size"):
        ImageGenerationRequest(  # type: ignore[call-arg]
            model="image-test",
            prompt="a small robot",
            size="1024x1024",
        )


def test_video_generation_request_constructs_without_tools() -> None:
    request = VideoGenerationRequest(
        model="video-test",
        prompt="a small robot walks",
        duration_seconds=8,
        ratio="16:9",
        resolution="1080p",
        generate_audio=True,
        watermark=False,
    )

    assert request.model == "video-test"
    assert request.prompt == "a small robot walks"
    assert request.duration_seconds == 8
    assert request.ratio == "16:9"
    assert request.resolution == "1080p"
    assert request.generate_audio is True
    assert request.watermark is False

    with pytest.raises(TypeError, match="tools"):
        VideoGenerationRequest(  # type: ignore[call-arg]
            model="video-test",
            prompt="hello",
            tools=[ToolSpec(name="lookup")],
        )


def test_media_generation_task_normalizes_status() -> None:
    task = MediaGenerationTask(
        id="task_1",
        provider="volcengine",
        model="video-test",
        status="running",
    )

    assert task.id == "task_1"
    assert task.provider == "volcengine"
    assert task.model == "video-test"
    assert task.status == TaskStatus.RUNNING

    with pytest.raises(ValueError, match="id is required"):
        MediaGenerationTask(id="", provider="volcengine", model="video-test")
