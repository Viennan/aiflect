from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from whero.aiflect import (
    ClientConfig,
    FilePreprocessConfig,
    FileStatus,
    ImagePart,
    MediaKind,
    MessageItem,
    ProviderItemSnapshot,
    RemoteContextHint,
    Role,
    SecretString,
    TaskStatus,
    VideoPart,
)
from whero.aiflect.core.errors import ProviderRequestError
from whero.aiflect.core.generation import StreamEventType
from whero.aiflect.providers.volcengine import VolcengineClient


class FakeResponses:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.result


class AsyncFakeResponses:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.result


class AsyncFakeStream:
    def __init__(self, items: list[object] | tuple[object, ...]) -> None:
        self._items = iter(items)

    def __aiter__(self) -> AsyncFakeStream:
        return self

    async def __anext__(self) -> object:
        try:
            return next(self._items)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FallbackResponses:
    def __init__(self, *, first_exc: Exception, result: object) -> None:
        self.first_exc = first_exc
        self.result = result
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            raise self.first_exc
        return self.result


class RaisingResponses:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def create(self, **kwargs: object) -> object:
        raise self.exc


class FakeEmbeddings:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.result


class FakeImages:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.result


class AsyncFakeImages:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if kwargs.get("stream") is True and isinstance(self.result, (list, tuple)):
            return AsyncFakeStream(self.result)
        return self.result


class FakeFiles:
    def __init__(self, file_obj: object) -> None:
        self.file_obj = file_obj
        self.create_calls: list[dict[str, object]] = []
        self.retrieve_calls: list[tuple[str, dict[str, object]]] = []
        self.list_calls: list[dict[str, object]] = []
        self.delete_calls: list[tuple[str, dict[str, object]]] = []
        self.wait_calls: list[tuple[str, dict[str, object]]] = []

    def create(self, **kwargs: object) -> object:
        self.create_calls.append(kwargs)
        return self.file_obj

    def retrieve(self, file_id: str, **kwargs: object) -> object:
        self.retrieve_calls.append((file_id, kwargs))
        return self.file_obj

    def list(self, **kwargs: object) -> list[object]:
        self.list_calls.append(kwargs)
        return [self.file_obj]

    def delete(self, file_id: str, **kwargs: object) -> object:
        self.delete_calls.append((file_id, kwargs))
        return SimpleNamespace(id=file_id, deleted=True)

    def wait_for_processing(self, id: str, **kwargs: object) -> object:
        self.wait_calls.append((id, kwargs))
        return self.file_obj


class FakeTasks:
    def __init__(self, *, create_result: object, get_results: list[object] | tuple[object, ...]) -> None:
        self.create_result = create_result
        self.get_results = list(get_results)
        self.create_calls: list[dict[str, object]] = []
        self.get_calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.create_calls.append(kwargs)
        return self.create_result

    def get(self, **kwargs: object) -> object:
        self.get_calls.append(kwargs)
        if len(self.get_results) > 1:
            return self.get_results.pop(0)
        return self.get_results[0]


class AsyncFakeTasks:
    def __init__(self, *, create_result: object, get_results: list[object] | tuple[object, ...]) -> None:
        self.create_result = create_result
        self.get_results = list(get_results)
        self.create_calls: list[dict[str, object]] = []
        self.get_calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.create_calls.append(kwargs)
        return self.create_result

    async def get(self, **kwargs: object) -> object:
        self.get_calls.append(kwargs)
        if len(self.get_results) > 1:
            return self.get_results.pop(0)
        return self.get_results[0]


class FakeArk:
    def __init__(
        self,
        *,
        response: object,
        embedding: object,
        file_obj: object,
        image: object | None = None,
        task_create: object | None = None,
        task_get: object | list[object] | tuple[object, ...] | None = None,
    ) -> None:
        self.responses = FakeResponses(response)
        self.multimodal_embeddings = FakeEmbeddings(embedding)
        self.files = FakeFiles(file_obj)
        self.images = FakeImages(image or SimpleNamespace(model="image-test", data=[], usage=None))
        task_get_results: list[object] | tuple[object, ...]
        if task_get is None:
            task_get_results = [_raw_video_task()]
        elif isinstance(task_get, (list, tuple)):
            task_get_results = task_get
        else:
            task_get_results = [task_get]
        self.content_generation = SimpleNamespace(
            tasks=FakeTasks(
                create_result=task_create or SimpleNamespace(id="task_1"),
                get_results=task_get_results,
            )
        )


def _volcengine_anchor(
    response_id: str = "resp_old",
    *,
    response_expire_at: int | None = None,
) -> MessageItem:
    metadata = {"response_id": response_id}
    if response_expire_at is not None:
        metadata["response_expire_at"] = response_expire_at
    return MessageItem(
        Role.ASSISTANT,
        "covered",
        provider_snapshots=[
            ProviderItemSnapshot(
                provider="volcengine",
                api_family="responses",
                item_type="message",
                payload={
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "covered"}],
                },
                metadata=metadata,
            )
        ],
    )


class FakeArkFallback:
    def __init__(self, *, first_exc: Exception, response: object) -> None:
        self.responses = FallbackResponses(first_exc=first_exc, result=response)


class FakeArkRaising:
    def __init__(self, exc: Exception) -> None:
        self.responses = RaisingResponses(exc)


class FakePreviousResponseExpiredError(Exception):
    status_code = 400
    request_id = "req_expired"
    body = {
        "error": {
            "type": "invalid_request_error",
            "code": "previous_response_expired",
            "param": "previous_response_id",
            "message": "The previous response has expired.",
        }
    }


class FakeArkError(Exception):
    status_code = 400
    request_id = "req_1"
    body = {
        "error": {
            "type": "invalid_request_error",
            "code": "bad_param",
            "param": "input",
        }
    }


def _raw_response(
    response_id: str = "resp_1",
    *,
    created_at: int | None = None,
    expire_at: int | None = None,
    caching: object | None = None,
    store: bool | None = None,
    output: list[object] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=response_id,
        model="doubao-test",
        status="completed",
        output=[] if output is None else output,
        usage=None,
        created_at=created_at,
        expire_at=expire_at,
        caching=caching,
        store=store,
    )


def _raw_embedding() -> SimpleNamespace:
    return SimpleNamespace(
        id="emb_1",
        model="doubao-embedding-test",
        data=SimpleNamespace(embedding=[1.0, 2.0]),
        usage=None,
    )


def _raw_file() -> SimpleNamespace:
    return SimpleNamespace(
        id="file_1",
        filename="a.txt",
        purpose="user_data",
        mime_type="text/plain",
        bytes=3,
        status="active",
        created_at=1_700_000_000,
        expire_at=1_700_086_400,
        preprocess_configs=None,
    )


def _raw_image_response() -> SimpleNamespace:
    return SimpleNamespace(
        model="doubao-image-test",
        data=[SimpleNamespace(url="https://example.test/image.png", size="1024x1024")],
        usage=SimpleNamespace(generated_images=1, output_tokens=2, total_tokens=3),
        created_at=1_700_000_000,
    )


def _raw_video_task(status: str = "succeeded") -> SimpleNamespace:
    return SimpleNamespace(
        id="task_1",
        model="doubao-video-test",
        status=status,
        error=None,
        content=SimpleNamespace(
            video_url="https://example.test/video.mp4",
            file_url=None,
            last_frame_url="https://example.test/last.png",
        ),
        usage=SimpleNamespace(completion_tokens=7, total_tokens=8),
        created_at=1_700_000_000,
        updated_at=1_700_000_010,
        duration=5,
        ratio="16:9",
        resolution="1920x1080",
        fileformat="mp4",
        generate_audio=True,
    )


def test_client_generate_uses_ark_responses_endpoint() -> None:
    fake = FakeArk(response=_raw_response(), embedding=_raw_embedding(), file_obj=_raw_file())
    client = VolcengineClient(client=fake, async_client=object())

    response = client.generate(
        model="doubao-test",
        items=[_volcengine_anchor(), MessageItem.user("hello")],
        remote_context=RemoteContextHint(enable_cache=True, new_items_start_index=1),
    )

    assert response.id == "resp_1"
    assert fake.responses.calls[0]["model"] == "doubao-test"
    assert fake.responses.calls[0]["previous_response_id"] == "resp_old"
    assert len(fake.responses.calls[0]["input"]) == 1
    assert fake.responses.calls[0]["input"][0]["role"] == "user"
    assert response.metadata["remote_context"] == {
        "api_family": "responses",
        "cache_enabled": True,
        "session_cache_enabled": False,
        "session_key_present": False,
        "attempted_previous_response_id": True,
        "final_request_used_previous_response_id": True,
        "refreshed_after_invalid_context": False,
        "refreshed_before_expiry": False,
        "new_items_start_index": 1,
    }


def test_client_generate_refreshes_invalid_remote_context() -> None:
    fake = FakeArkFallback(
        first_exc=FakePreviousResponseExpiredError("expired"),
        response=_raw_response("resp_2"),
    )
    client = VolcengineClient(client=fake, async_client=object())

    response = client.generate(
        model="doubao-test",
        items=[_volcengine_anchor(), MessageItem.user("hello")],
        remote_context=RemoteContextHint(enable_cache=True, new_items_start_index=1),
    )

    assert response.id == "resp_2"
    assert len(fake.responses.calls) == 2
    assert fake.responses.calls[0]["previous_response_id"] == "resp_old"
    assert "previous_response_id" not in fake.responses.calls[1]
    assert len(fake.responses.calls[1]["input"]) == 2
    assert response.metadata["remote_context"] == {
        "api_family": "responses",
        "cache_enabled": True,
        "session_cache_enabled": False,
        "session_key_present": False,
        "attempted_previous_response_id": True,
        "final_request_used_previous_response_id": False,
        "refreshed_after_invalid_context": True,
        "refreshed_before_expiry": False,
        "new_items_start_index": 1,
    }


def test_client_generate_uses_session_cache_params(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("whero.aiflect.providers.volcengine.client.time.time", lambda: 1_800_000_000)
    fake = FakeArk(response=_raw_response(), embedding=_raw_embedding(), file_obj=_raw_file())
    client = VolcengineClient(client=fake, async_client=object())

    response = client.generate(
        model="doubao-test",
        items=[
            _volcengine_anchor(response_expire_at=1_800_003_700),
            MessageItem.user("hello"),
        ],
        remote_context=RemoteContextHint(
            enable_cache=True,
            session_key="session-1",
            new_items_start_index=1,
        ),
    )

    assert fake.responses.calls[0]["previous_response_id"] == "resp_old"
    assert fake.responses.calls[0]["caching"] == {"type": "enabled"}
    assert fake.responses.calls[0]["expire_at"] == 1_800_003_600
    assert response.metadata["remote_context"] == {
        "api_family": "responses",
        "cache_enabled": True,
        "session_cache_enabled": True,
        "session_key_present": True,
        "attempted_previous_response_id": True,
        "final_request_used_previous_response_id": True,
        "refreshed_after_invalid_context": False,
        "refreshed_before_expiry": False,
        "previous_response_expire_at": 1_800_003_700,
        "new_items_start_index": 1,
    }


def test_client_generate_refreshes_session_cache_before_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("whero.aiflect.providers.volcengine.client.time.time", lambda: 1_800_000_000)
    fake = FakeArk(response=_raw_response(), embedding=_raw_embedding(), file_obj=_raw_file())
    client = VolcengineClient(client=fake, async_client=object())

    response = client.generate(
        model="doubao-test",
        items=[
            _volcengine_anchor(response_expire_at=1_800_000_299),
            MessageItem.user("hello"),
        ],
        remote_context=RemoteContextHint(
            enable_cache=True,
            session_key="session-1",
            new_items_start_index=1,
        ),
    )

    assert "previous_response_id" not in fake.responses.calls[0]
    assert len(fake.responses.calls[0]["input"]) == 2
    assert fake.responses.calls[0]["caching"] == {"type": "enabled"}
    assert fake.responses.calls[0]["expire_at"] == 1_800_003_600
    assert response.metadata["remote_context"] == {
        "api_family": "responses",
        "cache_enabled": True,
        "session_cache_enabled": True,
        "session_key_present": True,
        "attempted_previous_response_id": False,
        "final_request_used_previous_response_id": False,
        "refreshed_after_invalid_context": False,
        "refreshed_before_expiry": True,
        "previous_response_expire_at": 1_800_000_299,
        "new_items_start_index": 1,
    }


def test_client_stream_generate_maps_events() -> None:
    stream = [
        SimpleNamespace(
            type="response.output_text.delta",
            response_id="resp_1",
            item_id="msg_1",
            delta="hi",
        )
    ]
    fake = FakeArk(response=stream, embedding=_raw_embedding(), file_obj=_raw_file())
    client = VolcengineClient(client=fake, async_client=object())

    events = list(client.stream_generate(model="doubao-test", items=[MessageItem.user("hello")]))

    assert fake.responses.calls[0]["stream"] is True
    assert events[0].type == StreamEventType.TEXT_DELTA.value
    assert events[0].provider == "volcengine"
    assert events[0].delta == "hi"


def test_client_generate_image_uses_ark_images_endpoint() -> None:
    fake = FakeArk(
        response=_raw_response(),
        embedding=_raw_embedding(),
        file_obj=_raw_file(),
        image=_raw_image_response(),
    )
    client = VolcengineClient(client=fake, async_client=object())

    response = client.generate_image(
        model="doubao-image-test",
        prompt="a small robot",
        input_items=[
            MessageItem.user(
                [
                    ImagePart(url="https://example.test/ref1.png"),
                    ImagePart(data="aGVsbG8=", mime_type="image/png"),
                ]
            )
        ],
        output_format="png",
        response_format="url",
        count=2,
        quality="high",
        background="transparent",
        watermark=False,
    )

    call = fake.images.calls[0]
    assert call["model"] == "doubao-image-test"
    assert call["prompt"] == "a small robot"
    assert call["image"] == [
        "https://example.test/ref1.png",
        "data:image/png;base64,aGVsbG8=",
    ]
    assert "size" not in call
    assert call["output_format"] == "png"
    assert call["response_format"] == "url"
    assert call["watermark"] is False
    assert call["sequential_image_generation_options"] == {"max_images": 2}
    assert "quality" not in call
    assert "background" not in call
    assert "extra_body" not in call
    assert response.artifacts[0].kind == MediaKind.IMAGE
    assert response.artifacts[0].url == "https://example.test/image.png"
    assert response.artifacts[0].width == 1024
    assert response.usage is not None
    assert response.usage.metadata["generated_images"] == 1


def test_client_stream_generate_image_maps_ark_events() -> None:
    stream = [
        SimpleNamespace(
            type="image_generation.partial_succeeded",
            model="doubao-image-test",
            url="https://example.test/partial.png",
            size="512x512",
            image_index=0,
        ),
        SimpleNamespace(
            type="image_generation.partial_failed",
            model="doubao-image-test",
            image_index=1,
            error=SimpleNamespace(code="OutputImageSensitiveContentDetected", message="blocked"),
        ),
        SimpleNamespace(
            type="image_generation.completed",
            model="doubao-image-test",
            usage=SimpleNamespace(generated_images=1, output_tokens=2, total_tokens=3),
        ),
    ]
    fake = FakeArk(
        response=_raw_response(),
        embedding=_raw_embedding(),
        file_obj=_raw_file(),
        image=stream,
    )
    client = VolcengineClient(client=fake, async_client=object())

    events = list(client.stream_generate_image(model="doubao-image-test", prompt="a small robot"))

    assert fake.images.calls[0]["stream"] is True
    assert events[0].type == "image.partial"
    assert events[0].artifact is not None
    assert events[0].artifact.url == "https://example.test/partial.png"
    assert events[1].type == "image.failed"
    assert events[1].error == "OutputImageSensitiveContentDetected: blocked"
    assert events[2].type == "image.completed"
    assert events[2].usage is not None
    assert events[2].usage.total_tokens == 3


def test_client_generate_image_defaults_to_watermark() -> None:
    fake = FakeArk(
        response=_raw_response(),
        embedding=_raw_embedding(),
        file_obj=_raw_file(),
        image=_raw_image_response(),
    )
    client = VolcengineClient(client=fake, async_client=object())

    client.generate_image(model="doubao-image-test", prompt="a small robot")

    assert fake.images.calls[0]["watermark"] is True


def test_client_video_generation_task_methods_use_ark_content_generation() -> None:
    task_get = _raw_video_task(status="succeeded")
    fake = FakeArk(
        response=_raw_response(),
        embedding=_raw_embedding(),
        file_obj=_raw_file(),
        task_create=SimpleNamespace(id="task_1", safety_identifier="safe_1"),
        task_get=task_get,
    )
    client = VolcengineClient(client=fake, async_client=object())

    created = client.create_video_generation_task(
        model="doubao-video-test",
        prompt="a robot walks",
        input_items=[
            MessageItem.user(
                [
                    ImagePart(url="https://example.test/ref.png"),
                    ImagePart(
                        url="https://example.test/first.png",
                        metadata={"role": "first_frame"},
                    ),
                    VideoPart(url="https://example.test/ref.mp4", fps=2.0),
                ]
            )
        ],
        duration_seconds=5,
        ratio="16:9",
        resolution="1080p",
        generate_audio=True,
        watermark=False,
    )
    retrieved = client.get_video_generation_task("task_1")

    create_call = fake.content_generation.tasks.create_calls[0]
    assert created.id == "task_1"
    assert created.status == TaskStatus.QUEUED
    assert created.metadata["safety_identifier"] == "safe_1"
    assert create_call["model"] == "doubao-video-test"
    assert create_call["duration"] == 5
    assert create_call["ratio"] == "16:9"
    assert create_call["resolution"] == "1080p"
    assert create_call["generate_audio"] is True
    assert create_call["watermark"] is False
    assert create_call["content"] == [
        {"type": "text", "text": "a robot walks"},
        {
            "type": "image_url",
            "image_url": {"url": "https://example.test/ref.png"},
            "role": "reference_image",
        },
        {
            "type": "image_url",
            "image_url": {"url": "https://example.test/first.png"},
            "role": "first_frame",
        },
        {
            "type": "video_url",
            "video_url": {"url": "https://example.test/ref.mp4", "fps": 2.0},
            "role": "reference_video",
        },
    ]
    assert fake.content_generation.tasks.get_calls[0] == {"task_id": "task_1"}
    assert retrieved.status == TaskStatus.COMPLETED
    assert retrieved.artifacts[0].kind == MediaKind.VIDEO
    assert retrieved.artifacts[0].url == "https://example.test/video.mp4"
    assert retrieved.artifacts[1].kind == MediaKind.IMAGE
    assert retrieved.artifacts[1].url == "https://example.test/last.png"
    assert retrieved.metadata["usage"].total_tokens == 8


def test_client_wait_for_video_generation_task_polls_until_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeArk(
        response=_raw_response(),
        embedding=_raw_embedding(),
        file_obj=_raw_file(),
        task_get=[
            _raw_video_task(status="queued"),
            _raw_video_task(status="running"),
            _raw_video_task(status="succeeded"),
        ],
    )
    client = VolcengineClient(client=fake, async_client=object())
    monkeypatch.setattr("whero.aiflect.providers.volcengine.client.time.sleep", lambda _: None)

    task = client.wait_for_video_generation_task("task_1", poll_interval=0.1, max_wait_seconds=5)

    assert task.status == TaskStatus.COMPLETED
    assert len(fake.content_generation.tasks.get_calls) == 3


def test_client_create_video_generation_task_defaults_to_watermark() -> None:
    fake = FakeArk(
        response=_raw_response(),
        embedding=_raw_embedding(),
        file_obj=_raw_file(),
        task_create=SimpleNamespace(id="task_1"),
    )
    client = VolcengineClient(client=fake, async_client=object())

    client.create_video_generation_task(
        model="doubao-video-test",
        prompt="a robot walks",
    )

    assert fake.content_generation.tasks.create_calls[0]["watermark"] is True


@pytest.mark.anyio
async def test_async_client_generate_image_uses_ark_images_endpoint() -> None:
    fake_async = SimpleNamespace(
        images=AsyncFakeImages(_raw_image_response()),
    )
    client = VolcengineClient(client=object(), async_client=fake_async)

    response = await client.agenerate_image(
        model="doubao-image-test",
        prompt="a small robot",
        response_format="url",
    )

    assert fake_async.images.calls[0]["model"] == "doubao-image-test"
    assert fake_async.images.calls[0]["response_format"] == "url"
    assert fake_async.images.calls[0]["watermark"] is True
    assert response.artifacts[0].url == "https://example.test/image.png"


@pytest.mark.anyio
async def test_async_client_stream_generate_image_maps_ark_events() -> None:
    stream = [
        SimpleNamespace(type="image_generation.generating", b64_json="abc", image_index=0),
        SimpleNamespace(type="image_generation.completed"),
    ]
    fake_async = SimpleNamespace(images=AsyncFakeImages(stream))
    client = VolcengineClient(client=object(), async_client=fake_async)

    events = [
        event
        async for event in client.astream_generate_image(
            model="doubao-image-test",
            prompt="a small robot",
        )
    ]

    assert fake_async.images.calls[0]["stream"] is True
    assert events[0].type == "image.partial"
    assert events[0].artifact is not None
    assert events[0].artifact.data == "abc"


@pytest.mark.anyio
async def test_async_client_video_generation_task_methods_use_ark_content_generation() -> None:
    fake_tasks = AsyncFakeTasks(
        create_result=SimpleNamespace(id="task_async"),
        get_results=[_raw_video_task(status="succeeded")],
    )
    fake_async = SimpleNamespace(content_generation=SimpleNamespace(tasks=fake_tasks))
    client = VolcengineClient(client=object(), async_client=fake_async)

    created = await client.acreate_video_generation_task(
        model="doubao-video-test",
        prompt="a robot walks",
        duration_seconds=5,
    )
    retrieved = await client.aget_video_generation_task("task_async")

    assert created.id == "task_async"
    assert fake_tasks.create_calls[0]["duration"] == 5
    assert fake_tasks.create_calls[0]["watermark"] is True
    assert fake_tasks.get_calls[0] == {"task_id": "task_async"}
    assert retrieved.status == TaskStatus.COMPLETED


def test_client_embed_uses_multimodal_embeddings_endpoint() -> None:
    fake = FakeArk(response=_raw_response(), embedding=_raw_embedding(), file_obj=_raw_file())
    client = VolcengineClient(client=fake, async_client=object())

    response = client.embed(
        model="doubao-embedding-test",
        inputs=["hello"],
        instructions="query",
        sparse_embedding=False,
        provider_options={"trace_id": "trace-1"},
    )

    assert fake.multimodal_embeddings.calls[0]["model"] == "doubao-embedding-test"
    assert fake.multimodal_embeddings.calls[0]["input"] == [{"type": "text", "text": "hello"}]
    assert fake.multimodal_embeddings.calls[0]["extra_body"] == {
        "instructions": "query",
        "trace_id": "trace-1",
    }
    assert fake.multimodal_embeddings.calls[0]["sparse_embedding"] == {"type": "disabled"}
    assert response.vectors[0].dense == [1.0, 2.0]


def test_client_file_methods_use_ark_files_endpoint() -> None:
    fake = FakeArk(response=_raw_response(), embedding=_raw_embedding(), file_obj=_raw_file())
    client = VolcengineClient(client=fake, async_client=object())

    uploaded = client.upload_file(
        file=b"abc",
        filename="a.txt",
        purpose="user_data",
        mime_type="text/plain",
        preprocess=FilePreprocessConfig(video_fps=0.2),
        expire_at=1_800_000_000,
    )
    listed = client.list_files(purpose="user_data", limit=1)
    deleted = client.delete_file("file_1")
    waited = client.wait_for_file_processing("file_1", poll_interval=0.1, max_wait_seconds=1)

    assert uploaded.id == "file_1"
    assert fake.files.create_calls[0]["purpose"] == "user_data"
    assert fake.files.create_calls[0]["file"] == ("a.txt", b"abc", "text/plain")
    assert fake.files.create_calls[0]["preprocess_configs"] == {"video": {"fps": 0.2}}
    assert fake.files.create_calls[0]["expire_at"] == 1_800_000_000
    assert fake.files.list_calls[0] == {"purpose": "user_data", "limit": 1}
    assert listed[0].status == FileStatus.READY
    assert deleted.status == FileStatus.DELETED
    assert waited.id == "file_1"
    assert fake.files.wait_calls[0][1] == {"poll_interval": 0.1, "max_wait_seconds": 1}


def test_client_common_init_options_are_collected() -> None:
    client = VolcengineClient(
        config=ClientConfig(
            api_key="from-config",
            base_url="https://example.test/api/v3",
            timeout=30.0,
            max_retries=1,
            provider_options={"region": "cn-beijing"},
        ),
        timeout=10.0,
        region="cn-shanghai",
    )

    assert client._client_options == {
        "api_key": SecretString("from-config"),
        "base_url": "https://example.test/api/v3",
        "timeout": 10.0,
        "max_retries": 1,
        "region": "cn-shanghai",
    }
    assert repr(client._client_options["api_key"]) == "SecretString('********')"


def test_client_does_not_read_provider_scoped_aiflect_env_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENV_AIFLECT_VOLCENGINE_API_KEY", "env-key")

    with pytest.raises(ValueError, match="requires api_key"):
        VolcengineClient()


def test_client_reveals_secret_string_only_when_creating_sdk_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ark_cls = Mock(return_value=object())
    async_ark_cls = Mock(return_value=object())
    monkeypatch.setitem(
        sys.modules,
        "volcenginesdkarkruntime",
        SimpleNamespace(Ark=ark_cls, AsyncArk=async_ark_cls),
    )
    client = VolcengineClient(
        api_key=SecretString("explicit"),
        region="cn-beijing",
    )

    assert client._client_options["api_key"] == SecretString("explicit")

    _ = client._sync_client
    _ = client._async_ark_client

    ark_cls.assert_called_once_with(api_key="explicit", region="cn-beijing")
    async_ark_cls.assert_called_once_with(api_key="explicit", region="cn-beijing")


def test_client_config_api_key_satisfies_explicit_credential_requirement() -> None:
    client = VolcengineClient(config=ClientConfig(api_key="from-config"))

    assert client._client_options["api_key"] == SecretString("from-config")


def test_client_request_error_is_wrapped_with_provider_details() -> None:
    exc = FakeArkError("bad request")
    client = VolcengineClient(client=FakeArkRaising(exc), async_client=object())

    with pytest.raises(ProviderRequestError) as exc_info:
        client.generate(model="doubao-test", items=[MessageItem.user("hello")])

    wrapped = exc_info.value
    assert wrapped.cause is exc
    assert wrapped.details.provider == "volcengine"
    assert wrapped.details.operation == "responses.create"
    assert wrapped.details.status_code == 400
    assert wrapped.details.request_id == "req_1"
    assert wrapped.details.error_type == "invalid_request_error"
    assert wrapped.details.error_code == "bad_param"
    assert wrapped.details.error_param == "input"


@pytest.mark.anyio
async def test_async_client_generate_uses_async_ark_responses_endpoint() -> None:
    fake_async = SimpleNamespace(responses=AsyncFakeResponses(_raw_response("resp_async")))
    client = VolcengineClient(client=object(), async_client=fake_async)

    response = await client.agenerate(
        model="doubao-test",
        items=[MessageItem.user("hello")],
    )

    assert response.id == "resp_async"
    assert fake_async.responses.calls[0]["model"] == "doubao-test"
