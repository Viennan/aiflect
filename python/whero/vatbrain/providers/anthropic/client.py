"""Anthropic provider client."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from typing import Any

from whero.vatbrain.core.capabilities import AdapterCapability, ModelCapability
from whero.vatbrain.core.client import (
    ClientConfig,
    SecretString,
    reveal_secret_values,
    secretize_client_options,
    to_secret_string,
)
from whero.vatbrain.core.errors import ProviderRequestError
from whero.vatbrain.core.generation import (
    GenerationConfig,
    GenerationRequest,
    GenerationResponse,
    GenerationStreamEvent,
    ReasoningConfig,
    RemoteContextHint,
    ReplayPolicy,
    ResponseFormat,
    StreamOptions,
    ToolCallConfig,
)
from whero.vatbrain.core.items import Item
from whero.vatbrain.core.tools import ToolSpec
from whero.vatbrain.structured import ParsedGenerationResponse, pydantic_output
from whero.vatbrain.providers.anthropic.capabilities import (
    get_adapter_capability,
    get_model_capability,
)
from whero.vatbrain.providers.anthropic.mapper import (
    PROVIDER,
    from_anthropic_generation_response,
    to_anthropic_generation_params,
)
from whero.vatbrain.providers.anthropic.stream import from_anthropic_stream_event


class AnthropicClient:
    """Provider-level Anthropic adapter client."""

    provider = PROVIDER

    def __init__(
        self,
        *,
        config: ClientConfig | None = None,
        api_key: str | SecretString | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        client: Any | None = None,
        async_client: Any | None = None,
        model_capability_overrides: Mapping[str, Mapping[str, Any]] | None = None,
        **anthropic_client_options: Any,
    ) -> None:
        self._client = client
        self._async_client = async_client
        self._client_options = _merge_client_options(
            config=config,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            provider_options=anthropic_client_options,
        )
        _validate_client_credentials(
            client=client,
            async_client=async_client,
            options=self._client_options,
        )
        self._model_capability_overrides = {
            model: dict(values)
            for model, values in (model_capability_overrides or {}).items()
        }

    def generate(
        self,
        *,
        model: str,
        items: list[Item] | tuple[Item, ...],
        tools: list[ToolSpec] | tuple[ToolSpec, ...] = (),
        generation_config: GenerationConfig | None = None,
        response_format: ResponseFormat | None = None,
        reasoning: ReasoningConfig | None = None,
        tool_call_config: ToolCallConfig | None = None,
        remote_context: RemoteContextHint | None = None,
        replay_policy: ReplayPolicy | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> GenerationResponse:
        request = GenerationRequest(
            model=model,
            items=items,
            tools=tools,
            generation_config=generation_config,
            response_format=response_format,
            reasoning=reasoning,
            tool_call_config=tool_call_config,
            remote_context=remote_context,
            replay_policy=replay_policy,
            provider_options=provider_options,
        )
        response = self._create_generation_response(
            request,
            message="Anthropic generation request failed.",
        )
        return from_anthropic_generation_response(response)

    def generate_parsed(
        self,
        *,
        model: str,
        items: list[Item] | tuple[Item, ...],
        output_type: Any,
        tools: list[ToolSpec] | tuple[ToolSpec, ...] = (),
        generation_config: GenerationConfig | None = None,
        reasoning: ReasoningConfig | None = None,
        tool_call_config: ToolCallConfig | None = None,
        remote_context: RemoteContextHint | None = None,
        replay_policy: ReplayPolicy | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> ParsedGenerationResponse[Any]:
        output_spec = pydantic_output(output_type)
        response = self.generate(
            model=model,
            items=items,
            tools=tools,
            generation_config=generation_config,
            response_format=output_spec.response_format,
            reasoning=reasoning,
            tool_call_config=tool_call_config,
            remote_context=remote_context,
            replay_policy=replay_policy,
            provider_options=provider_options,
        )
        return output_spec.parse_response(response)

    async def agenerate(
        self,
        *,
        model: str,
        items: list[Item] | tuple[Item, ...],
        tools: list[ToolSpec] | tuple[ToolSpec, ...] = (),
        generation_config: GenerationConfig | None = None,
        response_format: ResponseFormat | None = None,
        reasoning: ReasoningConfig | None = None,
        tool_call_config: ToolCallConfig | None = None,
        remote_context: RemoteContextHint | None = None,
        replay_policy: ReplayPolicy | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> GenerationResponse:
        request = GenerationRequest(
            model=model,
            items=items,
            tools=tools,
            generation_config=generation_config,
            response_format=response_format,
            reasoning=reasoning,
            tool_call_config=tool_call_config,
            remote_context=remote_context,
            replay_policy=replay_policy,
            provider_options=provider_options,
        )
        response = await self._acreate_generation_response(
            request,
            message="Anthropic async generation request failed.",
        )
        return from_anthropic_generation_response(response)

    async def agenerate_parsed(
        self,
        *,
        model: str,
        items: list[Item] | tuple[Item, ...],
        output_type: Any,
        tools: list[ToolSpec] | tuple[ToolSpec, ...] = (),
        generation_config: GenerationConfig | None = None,
        reasoning: ReasoningConfig | None = None,
        tool_call_config: ToolCallConfig | None = None,
        remote_context: RemoteContextHint | None = None,
        replay_policy: ReplayPolicy | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> ParsedGenerationResponse[Any]:
        output_spec = pydantic_output(output_type)
        response = await self.agenerate(
            model=model,
            items=items,
            tools=tools,
            generation_config=generation_config,
            response_format=output_spec.response_format,
            reasoning=reasoning,
            tool_call_config=tool_call_config,
            remote_context=remote_context,
            replay_policy=replay_policy,
            provider_options=provider_options,
        )
        return output_spec.parse_response(response)

    def stream_generate(
        self,
        *,
        model: str,
        items: list[Item] | tuple[Item, ...],
        tools: list[ToolSpec] | tuple[ToolSpec, ...] = (),
        generation_config: GenerationConfig | None = None,
        response_format: ResponseFormat | None = None,
        reasoning: ReasoningConfig | None = None,
        tool_call_config: ToolCallConfig | None = None,
        stream_options: StreamOptions | None = None,
        remote_context: RemoteContextHint | None = None,
        replay_policy: ReplayPolicy | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> Iterator[GenerationStreamEvent]:
        request = GenerationRequest(
            model=model,
            items=items,
            tools=tools,
            generation_config=generation_config,
            response_format=response_format,
            reasoning=reasoning,
            tool_call_config=tool_call_config,
            stream_options=stream_options,
            remote_context=remote_context,
            replay_policy=replay_policy,
            provider_options=provider_options,
        )
        stream = self._create_generation_stream(
            request,
            message="Anthropic stream generation request failed.",
        )
        for sequence, event in enumerate(stream):
            yield from_anthropic_stream_event(event, sequence=sequence)

    async def astream_generate(
        self,
        *,
        model: str,
        items: list[Item] | tuple[Item, ...],
        tools: list[ToolSpec] | tuple[ToolSpec, ...] = (),
        generation_config: GenerationConfig | None = None,
        response_format: ResponseFormat | None = None,
        reasoning: ReasoningConfig | None = None,
        tool_call_config: ToolCallConfig | None = None,
        stream_options: StreamOptions | None = None,
        remote_context: RemoteContextHint | None = None,
        replay_policy: ReplayPolicy | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> AsyncIterator[GenerationStreamEvent]:
        request = GenerationRequest(
            model=model,
            items=items,
            tools=tools,
            generation_config=generation_config,
            response_format=response_format,
            reasoning=reasoning,
            tool_call_config=tool_call_config,
            stream_options=stream_options,
            remote_context=remote_context,
            replay_policy=replay_policy,
            provider_options=provider_options,
        )
        stream = await self._acreate_generation_stream(
            request,
            message="Anthropic async stream generation request failed.",
        )
        sequence = 0
        async for event in stream:
            yield from_anthropic_stream_event(event, sequence=sequence)
            sequence += 1

    def get_adapter_capability(self) -> AdapterCapability:
        return get_adapter_capability()

    def get_model_capability(
        self,
        model: str,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> ModelCapability:
        merged_overrides = dict(self._model_capability_overrides.get(model, {}))
        if overrides:
            merged_overrides.update(dict(overrides))
        return get_model_capability(model, overrides=merged_overrides or None)

    def _create_generation_response(self, request: GenerationRequest, *, message: str) -> Any:
        params = to_anthropic_generation_params(request)
        try:
            return self._sync_client.messages.create(**params)
        except Exception as exc:
            raise _provider_request_error(message, "messages.create", exc) from exc

    async def _acreate_generation_response(self, request: GenerationRequest, *, message: str) -> Any:
        params = to_anthropic_generation_params(request)
        try:
            return await self._async_anthropic_client.messages.create(**params)
        except Exception as exc:
            raise _provider_request_error(message, "messages.create", exc) from exc

    def _create_generation_stream(self, request: GenerationRequest, *, message: str) -> Any:
        params = to_anthropic_generation_params(request, stream=True)
        try:
            return self._sync_client.messages.create(**params)
        except Exception as exc:
            raise _provider_request_error(message, "messages.create", exc) from exc

    async def _acreate_generation_stream(self, request: GenerationRequest, *, message: str) -> Any:
        params = to_anthropic_generation_params(request, stream=True)
        try:
            return await self._async_anthropic_client.messages.create(**params)
        except Exception as exc:
            raise _provider_request_error(message, "messages.create", exc) from exc

    @property
    def _sync_client(self) -> Any:
        if self._client is None:
            from anthropic import Anthropic

            self._client = Anthropic(**reveal_secret_values(self._client_options))
        return self._client

    @property
    def _async_anthropic_client(self) -> Any:
        if self._async_client is None:
            from anthropic import AsyncAnthropic

            self._async_client = AsyncAnthropic(**reveal_secret_values(self._client_options))
        return self._async_client


def _merge_client_options(
    *,
    config: ClientConfig | None,
    api_key: str | SecretString | None,
    base_url: str | None,
    timeout: float | None,
    max_retries: int | None,
    provider_options: Mapping[str, Any],
) -> dict[str, Any]:
    options: dict[str, Any] = secretize_client_options(config.provider_options or {}) if config else {}
    options.update(secretize_client_options(provider_options))
    resolved_api_key = api_key if api_key is not None else (config.api_key if config else None)
    resolved_base_url = base_url if base_url is not None else (config.base_url if config else None)
    resolved_timeout = timeout if timeout is not None else (config.timeout if config else None)
    resolved_max_retries = max_retries if max_retries is not None else (config.max_retries if config else None)
    if resolved_api_key is not None:
        options["api_key"] = to_secret_string(resolved_api_key)
    if resolved_base_url is not None:
        options["base_url"] = resolved_base_url
    if resolved_timeout is not None:
        options["timeout"] = resolved_timeout
    if resolved_max_retries is not None:
        options["max_retries"] = resolved_max_retries
    return options


def _validate_client_credentials(
    *,
    client: Any | None,
    async_client: Any | None,
    options: Mapping[str, Any],
) -> None:
    if client is not None and async_client is not None:
        return
    if options.get("api_key") is not None:
        return
    raise ValueError(
        "AnthropicClient requires api_key or ClientConfig.api_key at initialization "
        "when provider SDK clients are not injected."
    )


def _provider_request_error(message: str, operation: str, exc: BaseException) -> ProviderRequestError:
    body = _get_error_body(exc)
    error_payload = _get_error_payload(body)
    return ProviderRequestError(
        message,
        provider=PROVIDER,
        operation=operation,
        status_code=_get_attr(exc, "status_code", None),
        request_id=_get_attr(exc, "request_id", _get_attr(exc, "x_request_id", None)),
        error_type=_get_attr(error_payload, "type", None),
        error_code=_get_attr(error_payload, "code", None),
        error_param=_get_attr(error_payload, "param", None),
        raw=body,
        cause=exc,
    )


def _get_error_body(exc: BaseException) -> Any:
    body = _get_attr(exc, "body", None)
    if body is not None:
        return body
    response = _get_attr(exc, "response", None)
    if response is not None:
        try:
            return response.json()
        except Exception:
            return response
    return None


def _get_error_payload(body: Any) -> Any:
    if isinstance(body, Mapping):
        return body.get("error", body)
    return body


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)
