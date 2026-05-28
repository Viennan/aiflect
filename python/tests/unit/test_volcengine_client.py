from __future__ import annotations

from types import SimpleNamespace

import pytest

from whero.vatbrain import (
    ClientConfig,
    FilePreprocessConfig,
    FileStatus,
    MessageItem,
    RemoteContextHint,
    RemoteContextInvalidBehavior,
    ReplayPolicy,
)
from whero.vatbrain.core.errors import ProviderRequestError
from whero.vatbrain.core.generation import StreamEventType
from whero.vatbrain.providers.volcengine import VolcengineClient


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


class FakeArk:
    def __init__(self, *, response: object, embedding: object, file_obj: object) -> None:
        self.responses = FakeResponses(response)
        self.multimodal_embeddings = FakeEmbeddings(embedding)
        self.files = FakeFiles(file_obj)


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


def _raw_response(response_id: str = "resp_1") -> SimpleNamespace:
    return SimpleNamespace(
        id=response_id,
        model="doubao-test",
        status="completed",
        output=[],
        usage=None,
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


def test_client_generate_uses_ark_responses_endpoint() -> None:
    fake = FakeArk(response=_raw_response(), embedding=_raw_embedding(), file_obj=_raw_file())
    client = VolcengineClient(client=fake, async_client=object())

    response = client.generate(
        model="doubao-test",
        items=[MessageItem.system("covered"), MessageItem.user("hello")],
        remote_context=RemoteContextHint(previous_response_id="resp_old", covered_item_count=1),
    )

    assert response.id == "resp_1"
    assert fake.responses.calls[0]["model"] == "doubao-test"
    assert fake.responses.calls[0]["previous_response_id"] == "resp_old"
    assert len(fake.responses.calls[0]["input"]) == 1
    assert fake.responses.calls[0]["input"][0]["role"] == "user"


def test_client_generate_replays_without_remote_context_when_enabled() -> None:
    fake = FakeArkFallback(
        first_exc=FakePreviousResponseExpiredError("expired"),
        response=_raw_response("resp_2"),
    )
    client = VolcengineClient(client=fake, async_client=object())

    response = client.generate(
        model="doubao-test",
        items=[MessageItem.system("covered"), MessageItem.user("hello")],
        remote_context=RemoteContextHint(previous_response_id="resp_old", covered_item_count=1),
        replay_policy=ReplayPolicy(
            on_remote_context_invalid=RemoteContextInvalidBehavior.REPLAY_WITHOUT_REMOTE_CONTEXT,
        ),
    )

    assert response.id == "resp_2"
    assert len(fake.responses.calls) == 2
    assert fake.responses.calls[0]["previous_response_id"] == "resp_old"
    assert "previous_response_id" not in fake.responses.calls[1]
    assert len(fake.responses.calls[1]["input"]) == 2


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


def test_client_embed_uses_multimodal_embeddings_endpoint() -> None:
    fake = FakeArk(response=_raw_response(), embedding=_raw_embedding(), file_obj=_raw_file())
    client = VolcengineClient(client=fake, async_client=object())

    response = client.embed(
        model="doubao-embedding-test",
        inputs=["hello"],
        instructions="query",
        sparse_embedding=False,
    )

    assert fake.multimodal_embeddings.calls[0]["model"] == "doubao-embedding-test"
    assert fake.multimodal_embeddings.calls[0]["input"] == [{"type": "text", "text": "hello"}]
    assert fake.multimodal_embeddings.calls[0]["extra_body"] == {"instructions": "query"}
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


def test_client_common_init_options_are_collected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV_VATBRAIN_VOLCENGINE_API_KEY", "env-key")

    client = VolcengineClient(
        config=ClientConfig(
            api_key="from-config",
            base_url="https://example.test/api/v3",
            timeout=30.0,
            max_retries=1,
            provider_options={"region": "cn-beijing"},
        ),
        timeout=10.0,
        ak="ak",
    )

    assert client._client_options == {
        "api_key": "from-config",
        "base_url": "https://example.test/api/v3",
        "timeout": 10.0,
        "max_retries": 1,
        "region": "cn-beijing",
        "ak": "ak",
    }


def test_client_reads_provider_scoped_vatbrain_env_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV_VATBRAIN_VOLCENGINE_API_KEY", "env-key")

    client = VolcengineClient()

    assert client._client_options["api_key"] == "env-key"


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
