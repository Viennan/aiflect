from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from whero.vatbrain import (
    ClientConfig,
    ImagePart,
    MessageItem,
    ProviderItemSnapshot,
    ReasoningConfig,
    RemoteContextHint,
    Role,
    SecretString,
    ToolCallConfig,
)
from whero.vatbrain.core.errors import ProviderRequestError, UnsupportedCapabilityError
from whero.vatbrain.core.generation import StreamEventType
from whero.vatbrain.providers.openai import OpenAIClient


class FakeResponses:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.result


class RaisingResponses:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def create(self, **kwargs: object) -> object:
        raise self.exc


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


class AsyncFallbackResponses:
    def __init__(self, *, first_exc: Exception, result: object) -> None:
        self.first_exc = first_exc
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            raise self.first_exc
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


class FakeImages:
    def __init__(self, *, generate_result: object, edit_result: object | None = None) -> None:
        self.generate_result = generate_result
        self.edit_result = edit_result if edit_result is not None else generate_result
        self.generate_calls: list[dict[str, object]] = []
        self.edit_calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> object:
        self.generate_calls.append(kwargs)
        return self.generate_result

    def edit(self, **kwargs: object) -> object:
        self.edit_calls.append(kwargs)
        return self.edit_result


class AsyncFakeImages:
    def __init__(self, *, generate_result: object, edit_result: object | None = None) -> None:
        self.generate_result = generate_result
        self.edit_result = edit_result if edit_result is not None else generate_result
        self.generate_calls: list[dict[str, object]] = []
        self.edit_calls: list[dict[str, object]] = []

    async def generate(self, **kwargs: object) -> object:
        self.generate_calls.append(kwargs)
        if kwargs.get("stream") is True and isinstance(self.generate_result, (list, tuple)):
            return AsyncFakeStream(self.generate_result)
        return self.generate_result

    async def edit(self, **kwargs: object) -> object:
        self.edit_calls.append(kwargs)
        if kwargs.get("stream") is True and isinstance(self.edit_result, (list, tuple)):
            return AsyncFakeStream(self.edit_result)
        return self.edit_result


class FakeEmbeddings:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.result


class FakeOpenAI:
    def __init__(
        self,
        *,
        response: object,
        embedding: object | None = None,
        image_generate: object | None = None,
        image_edit: object | None = None,
    ) -> None:
        self.responses = FakeResponses(response)
        self.embeddings = FakeEmbeddings(embedding or SimpleNamespace(data=[], usage=None))
        self.images = FakeImages(
            generate_result=image_generate or SimpleNamespace(data=[], usage=None),
            edit_result=image_edit,
        )


class FakeOpenAIRaising:
    def __init__(self, exc: Exception) -> None:
        self.responses = RaisingResponses(exc)
        self.embeddings = FakeEmbeddings(SimpleNamespace(data=[], usage=None))


class FakeOpenAIFallback:
    def __init__(self, *, first_exc: Exception, response: object) -> None:
        self.responses = FallbackResponses(first_exc=first_exc, result=response)
        self.embeddings = FakeEmbeddings(SimpleNamespace(data=[], usage=None))


class FakeAsyncOpenAIFallback:
    def __init__(self, *, first_exc: Exception, response: object) -> None:
        self.responses = AsyncFallbackResponses(first_exc=first_exc, result=response)


class FakeAsyncOpenAI:
    def __init__(
        self,
        *,
        response: object,
        image_generate: object | None = None,
        image_edit: object | None = None,
    ) -> None:
        self.responses = AsyncFakeResponses(response)
        self.images = AsyncFakeImages(
            generate_result=image_generate or SimpleNamespace(data=[], usage=None),
            edit_result=image_edit,
        )


class FakeOpenAIError(Exception):
    status_code = 400
    request_id = "req_1"
    body = {
        "error": {
            "type": "invalid_request_error",
            "code": "bad_param",
            "param": "stream_options",
        }
    }


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


class Contact(BaseModel):
    name: str
    email: str


def _openai_anchor(response_id: str = "resp_old") -> MessageItem:
    return MessageItem(
        Role.ASSISTANT,
        "covered",
        provider_snapshots=[
            ProviderItemSnapshot(
                provider="openai",
                api_family="responses",
                item_type="message",
                payload={
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "covered"}],
                },
                metadata={"response_id": response_id},
            )
        ],
    )


def test_client_generate_uses_explicit_model_and_common_options() -> None:
    raw_response = SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status="completed",
        output=[],
        usage=None,
    )
    fake = FakeOpenAI(response=raw_response)
    client = OpenAIClient(client=fake, async_client=object())

    response = client.generate(
        model="gpt-test",
        items=[_openai_anchor(), MessageItem.user("hello")],
        reasoning=ReasoningConfig(effort="low"),
        tool_call_config=ToolCallConfig(parallel_tool_calls=True),
        remote_context=RemoteContextHint(enable_cache=True, new_items_start_index=1),
    )

    assert response.id == "resp_1"
    assert fake.responses.calls[0]["model"] == "gpt-test"
    assert fake.responses.calls[0]["reasoning"] == {"effort": "low"}
    assert fake.responses.calls[0]["parallel_tool_calls"] is True
    assert fake.responses.calls[0]["previous_response_id"] == "resp_old"
    assert len(fake.responses.calls[0]["input"]) == 1
    assert fake.responses.calls[0]["input"][0]["role"] == "user"
    assert response.metadata["remote_context"] == {
        "api_family": "responses",
        "cache_enabled": True,
        "attempted_previous_response_id": True,
        "final_request_used_previous_response_id": True,
        "refreshed_after_invalid_context": False,
        "new_items_start_index": 1,
    }


def test_client_generate_refreshes_invalid_remote_context() -> None:
    raw_response = SimpleNamespace(
        id="resp_2",
        model="gpt-test",
        status="completed",
        output=[],
        usage=None,
    )
    fake = FakeOpenAIFallback(first_exc=FakePreviousResponseExpiredError("expired"), response=raw_response)
    client = OpenAIClient(client=fake, async_client=object())

    response = client.generate(
        model="gpt-test",
        items=[_openai_anchor(), MessageItem.user("hello")],
        remote_context=RemoteContextHint(
            enable_cache=True,
            new_items_start_index=1,
        ),
    )

    assert response.id == "resp_2"
    assert len(fake.responses.calls) == 2
    assert fake.responses.calls[0]["previous_response_id"] == "resp_old"
    assert len(fake.responses.calls[0]["input"]) == 1
    assert fake.responses.calls[0]["input"][0]["role"] == "user"
    assert "previous_response_id" not in fake.responses.calls[1]
    assert fake.responses.calls[1]["store"] is True
    assert len(fake.responses.calls[1]["input"]) == 2
    assert fake.responses.calls[1]["input"][0]["role"] == "assistant"
    assert fake.responses.calls[1]["input"][1]["role"] == "user"
    assert response.metadata["remote_context"] == {
        "api_family": "responses",
        "cache_enabled": True,
        "attempted_previous_response_id": True,
        "final_request_used_previous_response_id": False,
        "refreshed_after_invalid_context": True,
        "new_items_start_index": 1,
    }


def test_client_generate_does_not_refresh_when_previous_response_id_was_not_sent() -> None:
    exc = FakePreviousResponseExpiredError("expired")
    client = OpenAIClient(client=FakeOpenAIRaising(exc), async_client=object())

    try:
        client.generate(
            model="gpt-test",
            items=[MessageItem.assistant("covered"), MessageItem.user("hello")],
            remote_context=RemoteContextHint(enable_cache=True, new_items_start_index=1),
        )
    except ProviderRequestError as wrapped:
        assert wrapped.cause is exc
        assert wrapped.details.error_param == "previous_response_id"
    else:
        raise AssertionError("Expected ProviderRequestError")


def test_client_generate_parsed_builds_response_format_and_parses_output() -> None:
    raw_response = SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                id="msg_1",
                role="assistant",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text='{"name":"Ada","email":"ada@example.test"}',
                    )
                ],
            )
        ],
        usage=None,
    )
    fake = FakeOpenAI(response=raw_response)
    client = OpenAIClient(client=fake, async_client=object())

    parsed = client.generate_parsed(
        model="gpt-test",
        items=[MessageItem.user("extract")],
        output_type=Contact,
    )

    assert fake.responses.calls[0]["text"]["format"]["type"] == "json_schema"
    assert fake.responses.calls[0]["text"]["format"]["strict"] is True
    assert fake.responses.calls[0]["text"]["format"]["name"] == "Contact"
    assert parsed.response.id == "resp_1"
    assert parsed.output_parsed == Contact(name="Ada", email="ada@example.test")


@pytest.mark.anyio
async def test_async_client_generate_replays_without_remote_context_when_enabled() -> None:
    raw_response = SimpleNamespace(
        id="resp_async",
        model="gpt-test",
        status="completed",
        output=[],
        usage=None,
    )
    fake_async = FakeAsyncOpenAIFallback(
        first_exc=FakePreviousResponseExpiredError("expired"),
        response=raw_response,
    )
    client = OpenAIClient(client=object(), async_client=fake_async)

    response = await client.agenerate(
        model="gpt-test",
        items=[_openai_anchor(), MessageItem.user("hello")],
        remote_context=RemoteContextHint(enable_cache=True, new_items_start_index=1),
    )

    assert response.id == "resp_async"
    assert len(fake_async.responses.calls) == 2
    assert fake_async.responses.calls[0]["previous_response_id"] == "resp_old"
    assert len(fake_async.responses.calls[0]["input"]) == 1
    assert "previous_response_id" not in fake_async.responses.calls[1]
    assert len(fake_async.responses.calls[1]["input"]) == 2
    assert response.metadata["remote_context"] == {
        "api_family": "responses",
        "cache_enabled": True,
        "attempted_previous_response_id": True,
        "final_request_used_previous_response_id": False,
        "refreshed_after_invalid_context": True,
        "new_items_start_index": 1,
    }


@pytest.mark.anyio
async def test_async_client_generate_parsed_builds_response_format_and_parses_output() -> None:
    raw_response = SimpleNamespace(
        id="resp_async_parsed",
        model="gpt-test",
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                id="msg_1",
                role="assistant",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text='{"name":"Ada","email":"ada@example.test"}',
                    )
                ],
            )
        ],
        usage=None,
    )
    fake_async = FakeAsyncOpenAI(response=raw_response)
    client = OpenAIClient(client=object(), async_client=fake_async)

    parsed = await client.agenerate_parsed(
        model="gpt-test",
        items=[MessageItem.user("extract")],
        output_type=Contact,
    )

    assert fake_async.responses.calls[0]["text"]["format"]["name"] == "Contact"
    assert parsed.response.id == "resp_async_parsed"
    assert parsed.output_parsed.email == "ada@example.test"


def test_client_stream_generate_maps_events() -> None:
    stream = [
        SimpleNamespace(
            type="response.output_text.delta",
            response_id="resp_1",
            item_id="msg_1",
            delta="hi",
        )
    ]
    fake = FakeOpenAI(response=stream)
    client = OpenAIClient(client=fake, async_client=object())

    events = list(client.stream_generate(model="gpt-test", items=[MessageItem.user("hello")]))

    assert fake.responses.calls[0]["stream"] is True
    assert events[0].delta == "hi"
    assert events[0].type == StreamEventType.TEXT_DELTA.value


def test_client_stream_generate_refreshes_invalid_remote_context() -> None:
    stream = [
        SimpleNamespace(
            type="response.output_text.delta",
            response_id="resp_2",
            item_id="msg_1",
            delta="hi",
        )
    ]
    fake = FakeOpenAIFallback(first_exc=FakePreviousResponseExpiredError("expired"), response=stream)
    client = OpenAIClient(client=fake, async_client=object())

    events = list(
        client.stream_generate(
            model="gpt-test",
            items=[_openai_anchor(), MessageItem.user("hello")],
            remote_context=RemoteContextHint(enable_cache=True, new_items_start_index=1),
        )
    )

    assert len(fake.responses.calls) == 2
    assert fake.responses.calls[0]["previous_response_id"] == "resp_old"
    assert len(fake.responses.calls[0]["input"]) == 1
    assert "previous_response_id" not in fake.responses.calls[1]
    assert len(fake.responses.calls[1]["input"]) == 2
    assert events[0].delta == "hi"


def test_client_generate_image_uses_images_generate() -> None:
    raw_image = SimpleNamespace(
        model="gpt-image-test",
        data=[SimpleNamespace(url="https://example.test/image.png")],
        usage=SimpleNamespace(input_tokens=1, output_tokens=2, total_tokens=3),
    )
    fake = FakeOpenAI(response=SimpleNamespace(output=[]), image_generate=raw_image)
    client = OpenAIClient(client=fake, async_client=object())

    response = client.generate_image(
        model="gpt-image-test",
        prompt="a small robot",
        quality="high",
        output_format="png",
        response_format="url",
        count=2,
        watermark=False,
        provider_options={"user": "user_1", "watermark": False},
    )

    assert fake.images.generate_calls[0]["model"] == "gpt-image-test"
    assert fake.images.generate_calls[0]["prompt"] == "a small robot"
    assert "size" not in fake.images.generate_calls[0]
    assert "watermark" not in fake.images.generate_calls[0]
    assert fake.images.generate_calls[0]["quality"] == "high"
    assert fake.images.generate_calls[0]["n"] == 2
    assert fake.images.generate_calls[0]["user"] == "user_1"
    assert fake.images.edit_calls == []
    assert response.artifacts[0].url == "https://example.test/image.png"
    assert response.usage is not None
    assert response.usage.total_tokens == 3


def test_client_generate_image_with_reference_uses_images_edit() -> None:
    raw_image = SimpleNamespace(
        model="gpt-image-test",
        data=[SimpleNamespace(b64_json="abc")],
        usage=None,
    )
    fake = FakeOpenAI(response=SimpleNamespace(output=[]), image_edit=raw_image)
    client = OpenAIClient(client=fake, async_client=object())

    response = client.generate_image(
        model="gpt-image-test",
        prompt="turn this into a sketch",
        input_items=[MessageItem.user([ImagePart(data="aGVsbG8=", mime_type="image/png")])],
    )

    image_file = fake.images.edit_calls[0]["image"]
    assert fake.images.generate_calls == []
    assert image_file == ("image_0.png", b"hello", "image/png")
    assert fake.images.edit_calls[0]["prompt"] == "turn this into a sketch"
    assert response.artifacts[0].data == "abc"


def test_client_generate_image_rejects_openai_url_reference() -> None:
    client = OpenAIClient(client=FakeOpenAI(response=SimpleNamespace(output=[])), async_client=object())

    with pytest.raises(UnsupportedCapabilityError):
        client.generate_image(
            model="gpt-image-test",
            prompt="turn this into a sketch",
            input_items=[MessageItem.user([ImagePart(url="https://example.test/ref.png")])],
        )


def test_client_stream_generate_image_maps_events() -> None:
    stream = [
        SimpleNamespace(
            type="image_generation.partial_image",
            b64_json="abc",
            partial_image_index=0,
            size="1024x1024",
        ),
        SimpleNamespace(
            type="image_generation.completed",
            usage=SimpleNamespace(input_tokens=1, output_tokens=2, total_tokens=3),
        ),
    ]
    fake = FakeOpenAI(response=SimpleNamespace(output=[]), image_generate=stream)
    client = OpenAIClient(client=fake, async_client=object())

    events = list(client.stream_generate_image(model="gpt-image-test", prompt="a small robot"))

    assert fake.images.generate_calls[0]["stream"] is True
    assert "watermark" not in fake.images.generate_calls[0]
    assert events[0].type == "image.partial"
    assert events[0].artifact is not None
    assert events[0].artifact.data == "abc"
    assert events[1].type == "image.completed"
    assert events[1].usage is not None
    assert events[1].usage.total_tokens == 3


@pytest.mark.anyio
async def test_async_client_generate_image_uses_images_generate() -> None:
    raw_image = SimpleNamespace(
        model="gpt-image-test",
        data=[SimpleNamespace(url="https://example.test/async.png")],
        usage=None,
    )
    fake_async = FakeAsyncOpenAI(response=SimpleNamespace(output=[]), image_generate=raw_image)
    client = OpenAIClient(client=object(), async_client=fake_async)

    response = await client.agenerate_image(model="gpt-image-test", prompt="a small robot")

    assert fake_async.images.generate_calls[0]["model"] == "gpt-image-test"
    assert response.artifacts[0].url == "https://example.test/async.png"


@pytest.mark.anyio
async def test_async_client_stream_generate_image_maps_events() -> None:
    stream = [
        SimpleNamespace(type="image_generation.partial_image", b64_json="abc"),
        SimpleNamespace(type="image_generation.completed"),
    ]
    fake_async = FakeAsyncOpenAI(response=SimpleNamespace(output=[]), image_generate=stream)
    client = OpenAIClient(client=object(), async_client=fake_async)

    events = [
        event
        async for event in client.astream_generate_image(
            model="gpt-image-test",
            prompt="a small robot",
        )
    ]

    assert fake_async.images.generate_calls[0]["stream"] is True
    assert events[0].type == "image.partial"
    assert events[0].artifact is not None
    assert events[0].artifact.data == "abc"


def test_client_embed_uses_embedding_endpoint() -> None:
    raw_embedding = SimpleNamespace(
        model="text-embedding-test",
        data=[SimpleNamespace(index=0, embedding=[1.0, 2.0])],
        usage=None,
    )
    fake = FakeOpenAI(response=SimpleNamespace(output=[]), embedding=raw_embedding)
    client = OpenAIClient(client=fake, async_client=object())

    response = client.embed(model="text-embedding-test", inputs=["hello"])

    assert fake.embeddings.calls[0]["model"] == "text-embedding-test"
    assert fake.embeddings.calls[0]["input"] == ["hello"]
    assert response.vectors[0].embedding == [1.0, 2.0]


def test_client_common_init_options_are_collected() -> None:
    client = OpenAIClient(
        config=ClientConfig(
            api_key="from-config",
            base_url="https://example.test/v1",
            timeout=30.0,
            max_retries=1,
            provider_options={"default_headers": {"x-config": "yes"}},
        ),
        api_key="explicit",
        timeout=10.0,
        organization="org_1",
    )

    assert client._client_options == {
        "api_key": SecretString("explicit"),
        "base_url": "https://example.test/v1",
        "timeout": 10.0,
        "max_retries": 1,
        "default_headers": {"x-config": "yes"},
        "organization": "org_1",
    }
    assert repr(client._client_options["api_key"]) == "SecretString('********')"


def test_client_does_not_read_provider_scoped_vatbrain_env_api_key(monkeypatch) -> None:
    monkeypatch.setenv("ENV_VATBRAIN_OPENAI_API_KEY", "env-key")

    with pytest.raises(ValueError, match="requires api_key"):
        OpenAIClient()


def test_client_reveals_secret_string_only_when_creating_sdk_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openai_cls = Mock(return_value=object())
    async_openai_cls = Mock(return_value=object())
    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(OpenAI=openai_cls, AsyncOpenAI=async_openai_cls),
    )
    client = OpenAIClient(api_key=SecretString("explicit"), organization="org_1")

    assert client._client_options["api_key"] == SecretString("explicit")

    _ = client._sync_client
    _ = client._async_openai_client

    openai_cls.assert_called_once_with(api_key="explicit", organization="org_1")
    async_openai_cls.assert_called_once_with(api_key="explicit", organization="org_1")


def test_client_config_api_key_satisfies_explicit_credential_requirement() -> None:
    client = OpenAIClient(config=ClientConfig(api_key="from-config"))

    assert client._client_options["api_key"] == SecretString("from-config")


def test_client_request_error_is_wrapped_with_provider_details() -> None:
    exc = FakeOpenAIError("bad request")
    client = OpenAIClient(client=FakeOpenAIRaising(exc), async_client=object())

    try:
        client.generate(model="gpt-test", items=[MessageItem.user("hello")])
    except ProviderRequestError as wrapped:
        assert wrapped.cause is exc
        assert wrapped.details.provider == "openai"
        assert wrapped.details.operation == "responses.create"
        assert wrapped.details.status_code == 400
        assert wrapped.details.request_id == "req_1"
        assert wrapped.details.error_type == "invalid_request_error"
        assert wrapped.details.error_code == "bad_param"
        assert wrapped.details.error_param == "stream_options"
    else:
        raise AssertionError("Expected ProviderRequestError")
