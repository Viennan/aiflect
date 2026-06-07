from __future__ import annotations

from types import SimpleNamespace

import pytest

from whero.vatbrain import (
    ClientConfig,
    GenerationConfig,
    MessageItem,
    RemoteContextHint,
    SecretString,
)
from whero.vatbrain.core.errors import ProviderRequestError
from whero.vatbrain.core.generation import StreamEventType
from whero.vatbrain.providers.deepseek import DeepSeekClient
from whero.vatbrain.providers.deepseek.client import DEFAULT_ANTHROPIC_BASE_URL


class FakeMessages:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.result


class RaisingMessages:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def create(self, **kwargs: object) -> object:
        raise self.exc


class AsyncFakeMessages:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if kwargs.get("stream") is True and isinstance(self.result, (list, tuple)):
            return AsyncFakeStream(self.result)
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


class FakeDeepSeek:
    def __init__(self, response: object) -> None:
        self.messages = FakeMessages(response)


class FakeDeepSeekRaising:
    def __init__(self, exc: Exception) -> None:
        self.messages = RaisingMessages(exc)


class FakeAsyncDeepSeek:
    def __init__(self, response: object) -> None:
        self.messages = AsyncFakeMessages(response)


class FakeDeepSeekError(Exception):
    status_code = 400
    request_id = "req_1"
    body = {
        "error": {
            "type": "invalid_request_error",
            "code": "bad_param",
            "param": "messages",
        }
    }


def _raw_response(response_id: str = "msg_1") -> SimpleNamespace:
    return SimpleNamespace(
        id=response_id,
        model="deepseek-chat",
        stop_reason="end_turn",
        content=[],
        usage=None,
    )


def test_deepseek_client_generate_uses_messages_create_and_ignores_cache_hint() -> None:
    fake = FakeDeepSeek(_raw_response())
    client = DeepSeekClient(client=fake, async_client=object())

    response = client.generate(
        model="deepseek-chat",
        items=[MessageItem.system("policy"), MessageItem.user("hello")],
        generation_config=GenerationConfig(max_output_tokens=64),
        remote_context=RemoteContextHint(
            enable_cache=True,
            new_items_start_index=1,
        ),
    )

    assert response.id == "msg_1"
    assert response.provider == "deepseek"
    assert client._client_options["base_url"] == DEFAULT_ANTHROPIC_BASE_URL
    assert fake.messages.calls[0]["model"] == "deepseek-chat"
    assert fake.messages.calls[0]["max_tokens"] == 64
    assert "cache_control" not in fake.messages.calls[0]
    assert "previous_response_id" not in fake.messages.calls[0]
    assert fake.messages.calls[0]["system"] == [{"type": "text", "text": "policy"}]
    assert fake.messages.calls[0]["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]}
    ]


def test_deepseek_client_base_url_precedence() -> None:
    defaulted = DeepSeekClient(api_key="secret", async_client=object())
    configured = DeepSeekClient(
        config=ClientConfig(api_key="secret", base_url="https://config.example.test"),
        async_client=object(),
    )
    explicit = DeepSeekClient(
        config=ClientConfig(api_key="secret", base_url="https://config.example.test"),
        base_url="https://explicit.example.test",
        async_client=object(),
    )

    assert defaulted._client_options["base_url"] == DEFAULT_ANTHROPIC_BASE_URL
    assert configured._client_options["base_url"] == "https://config.example.test"
    assert explicit._client_options["base_url"] == "https://explicit.example.test"


def test_deepseek_client_rejects_unimplemented_or_unknown_api_format() -> None:
    with pytest.raises(ValueError, match="openai_completion"):
        DeepSeekClient(
            client=object(),
            async_client=object(),
            api_format="openai_completion",
        )

    with pytest.raises(ValueError, match="Unsupported DeepSeek api_format"):
        DeepSeekClient(
            client=object(),
            async_client=object(),
            api_format="chat_completion",
        )


def test_deepseek_client_stream_generate_maps_events() -> None:
    stream = [
        SimpleNamespace(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="text_delta", text="hi"),
        )
    ]
    fake = FakeDeepSeek(stream)
    client = DeepSeekClient(client=fake, async_client=object())

    events = list(
        client.stream_generate(
            model="deepseek-chat",
            items=[MessageItem.user("hello")],
            generation_config=GenerationConfig(max_output_tokens=64),
        )
    )

    assert fake.messages.calls[0]["stream"] is True
    assert events[0].provider == "deepseek"
    assert events[0].type == StreamEventType.TEXT_DELTA.value
    assert events[0].delta == "hi"


@pytest.mark.anyio
async def test_deepseek_async_client_generate_and_stream() -> None:
    fake_async = FakeAsyncDeepSeek(_raw_response("msg_async"))
    client = DeepSeekClient(client=object(), async_client=fake_async)

    response = await client.agenerate(
        model="deepseek-chat",
        items=[MessageItem.user("hello")],
        generation_config=GenerationConfig(max_output_tokens=64),
    )

    assert response.id == "msg_async"
    assert response.provider == "deepseek"
    assert fake_async.messages.calls[0]["max_tokens"] == 64

    stream_client = DeepSeekClient(
        client=object(),
        async_client=FakeAsyncDeepSeek(
            [
                SimpleNamespace(
                    type="content_block_delta",
                    index=0,
                    delta=SimpleNamespace(type="text_delta", text="async"),
                )
            ]
        ),
    )
    events = [
        event
        async for event in stream_client.astream_generate(
            model="deepseek-chat",
            items=[MessageItem.user("hello")],
            generation_config=GenerationConfig(max_output_tokens=64),
        )
    ]

    assert events[0].provider == "deepseek"
    assert events[0].delta == "async"


def test_deepseek_client_wraps_provider_errors() -> None:
    exc = FakeDeepSeekError("bad")
    client = DeepSeekClient(client=FakeDeepSeekRaising(exc), async_client=object())

    with pytest.raises(ProviderRequestError) as raised:
        client.generate(
            model="deepseek-chat",
            items=[MessageItem.user("hello")],
            generation_config=GenerationConfig(max_output_tokens=64),
        )

    assert raised.value.cause is exc
    assert raised.value.details.provider == "deepseek"
    assert raised.value.details.operation == "messages.create"
    assert raised.value.details.request_id == "req_1"
    assert raised.value.details.error_type == "invalid_request_error"
    assert raised.value.details.error_code == "bad_param"
    assert raised.value.details.error_param == "messages"


def test_deepseek_client_requires_credentials_without_injected_clients() -> None:
    with pytest.raises(ValueError, match="DeepSeekClient requires api_key"):
        DeepSeekClient()

    client = DeepSeekClient(config=ClientConfig(api_key="secret"), async_client=object())

    assert client._client_options["api_key"] == SecretString("secret")
