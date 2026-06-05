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
from whero.vatbrain.providers.anthropic import AnthropicClient


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


class FakeAnthropic:
    def __init__(self, response: object) -> None:
        self.messages = FakeMessages(response)


class FakeAnthropicRaising:
    def __init__(self, exc: Exception) -> None:
        self.messages = RaisingMessages(exc)


class FakeAsyncAnthropic:
    def __init__(self, response: object) -> None:
        self.messages = AsyncFakeMessages(response)


class FakeAnthropicError(Exception):
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
        model="claude-test",
        stop_reason="end_turn",
        content=[],
        usage=None,
    )


def test_anthropic_client_generate_uses_messages_create_and_cache_hint() -> None:
    fake = FakeAnthropic(_raw_response())
    client = AnthropicClient(client=fake, async_client=object())

    response = client.generate(
        model="claude-test",
        items=[MessageItem.system("policy"), MessageItem.user("hello")],
        generation_config=GenerationConfig(max_output_tokens=64),
        remote_context=RemoteContextHint(
            previous_response_id="ignored",
            covered_item_count=1,
            store=True,
        ),
    )

    assert response.id == "msg_1"
    assert fake.messages.calls[0]["model"] == "claude-test"
    assert fake.messages.calls[0]["max_tokens"] == 64
    assert fake.messages.calls[0]["cache_control"] == {"type": "ephemeral"}
    assert "previous_response_id" not in fake.messages.calls[0]
    assert fake.messages.calls[0]["system"] == [{"type": "text", "text": "policy"}]
    assert fake.messages.calls[0]["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]}
    ]


def test_anthropic_client_stream_generate_maps_events() -> None:
    stream = [
        SimpleNamespace(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="text_delta", text="hi"),
        )
    ]
    fake = FakeAnthropic(stream)
    client = AnthropicClient(client=fake, async_client=object())

    events = list(
        client.stream_generate(
            model="claude-test",
            items=[MessageItem.user("hello")],
            generation_config=GenerationConfig(max_output_tokens=64),
        )
    )

    assert fake.messages.calls[0]["stream"] is True
    assert events[0].type == StreamEventType.TEXT_DELTA.value
    assert events[0].delta == "hi"


@pytest.mark.anyio
async def test_anthropic_async_client_generate_and_stream() -> None:
    fake_async = FakeAsyncAnthropic(_raw_response("msg_async"))
    client = AnthropicClient(client=object(), async_client=fake_async)

    response = await client.agenerate(
        model="claude-test",
        items=[MessageItem.user("hello")],
        generation_config=GenerationConfig(max_output_tokens=64),
    )

    assert response.id == "msg_async"
    assert fake_async.messages.calls[0]["max_tokens"] == 64

    stream_client = AnthropicClient(
        client=object(),
        async_client=FakeAsyncAnthropic(
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
            model="claude-test",
            items=[MessageItem.user("hello")],
            generation_config=GenerationConfig(max_output_tokens=64),
        )
    ]

    assert events[0].delta == "async"


def test_anthropic_client_wraps_provider_errors() -> None:
    exc = FakeAnthropicError("bad")
    client = AnthropicClient(client=FakeAnthropicRaising(exc), async_client=object())

    with pytest.raises(ProviderRequestError) as raised:
        client.generate(
            model="claude-test",
            items=[MessageItem.user("hello")],
            generation_config=GenerationConfig(max_output_tokens=64),
        )

    assert raised.value.cause is exc
    assert raised.value.details.provider == "anthropic"
    assert raised.value.details.operation == "messages.create"
    assert raised.value.details.request_id == "req_1"
    assert raised.value.details.error_type == "invalid_request_error"
    assert raised.value.details.error_code == "bad_param"
    assert raised.value.details.error_param == "messages"


def test_anthropic_client_requires_credentials_without_injected_clients() -> None:
    with pytest.raises(ValueError, match="AnthropicClient requires api_key"):
        AnthropicClient()

    client = AnthropicClient(config=ClientConfig(api_key="secret"), async_client=object())

    assert client._client_options["api_key"] == SecretString("secret")
