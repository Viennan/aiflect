"""OpenAI provider client."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from dataclasses import dataclass, replace
from typing import Any

from whero.aiflect.core.capabilities import AdapterCapability, ModelCapability
from whero.aiflect.core.client import (
    ClientConfig,
    SecretString,
    reveal_secret_values,
    secretize_client_options,
    to_secret_string,
)
from whero.aiflect.core.embeddings import EmbeddingInput, EmbeddingRequest, EmbeddingResponse
from whero.aiflect.core.errors import ProviderRequestError
from whero.aiflect.core.generation import (
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
from whero.aiflect.core.items import Item
from whero.aiflect.core.media import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageGenerationStreamEvent,
)
from whero.aiflect.core.tools import ToolSpec
from whero.aiflect.structured import ParsedGenerationResponse, pydantic_output
from whero.aiflect.providers.openai.capabilities import (
    get_adapter_capability,
    get_model_capability,
)
from whero.aiflect.providers.openai.media import (
    from_openai_image_response,
    from_openai_image_stream_event,
    to_openai_image_params,
)
from whero.aiflect.providers.openai.mapper import (
    PROVIDER,
    from_openai_embedding_response,
    from_openai_generation_response,
    to_openai_embedding_params,
    to_openai_generation_params,
)
from whero.aiflect.providers.openai.stream import from_openai_stream_event

_DISABLED_RESPONSE_DELTA_VALUES = frozenset({"0", "disabled", "false", "full_context", "no", "off"})


@dataclass(frozen=True, slots=True)
class _GenerationCreateResult:
    response: Any
    metadata: dict[str, Any]


class OpenAIClient:
    """Provider-level OpenAI adapter client."""

    provider = "openai"

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
        **openai_client_options: Any,
    ) -> None:
        self._client = client
        self._async_client = async_client
        self._client_options = _merge_client_options(
            config=config,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            provider_options=openai_client_options,
        )
        self._adapter_options = _adapter_options(config)
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
        result = self._create_generation_response(request, message="OpenAI generation request failed.")
        return _with_generation_metadata(
            from_openai_generation_response(result.response),
            result.metadata,
        )

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
        result = await self._acreate_generation_response(
            request,
            message="OpenAI async generation request failed.",
        )
        return _with_generation_metadata(
            from_openai_generation_response(result.response),
            result.metadata,
        )

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
        stream = self._create_generation_stream(request, message="OpenAI stream generation request failed.")
        for sequence, event in enumerate(stream):
            yield from_openai_stream_event(event, sequence=sequence)

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
            message="OpenAI async stream generation request failed.",
        )
        sequence = 0
        async for event in stream:
            yield from_openai_stream_event(event, sequence=sequence)
            sequence += 1

    def generate_image(
        self,
        *,
        model: str,
        prompt: str,
        input_items: list[Item] | tuple[Item, ...] = (),
        quality: str | None = None,
        background: str | None = None,
        output_format: str | None = None,
        response_format: str | None = None,
        count: int | None = None,
        watermark: bool = True,
        stream_options: StreamOptions | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> ImageGenerationResponse:
        request = ImageGenerationRequest(
            model=model,
            prompt=prompt,
            input_items=input_items,
            quality=quality,
            background=background,
            output_format=output_format,
            response_format=response_format,
            count=count,
            watermark=watermark,
            stream_options=stream_options,
            provider_options=provider_options,
        )
        response = self._create_image_response(
            request,
            message="OpenAI image generation request failed.",
        )
        return from_openai_image_response(response)

    async def agenerate_image(
        self,
        *,
        model: str,
        prompt: str,
        input_items: list[Item] | tuple[Item, ...] = (),
        quality: str | None = None,
        background: str | None = None,
        output_format: str | None = None,
        response_format: str | None = None,
        count: int | None = None,
        watermark: bool = True,
        stream_options: StreamOptions | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> ImageGenerationResponse:
        request = ImageGenerationRequest(
            model=model,
            prompt=prompt,
            input_items=input_items,
            quality=quality,
            background=background,
            output_format=output_format,
            response_format=response_format,
            count=count,
            watermark=watermark,
            stream_options=stream_options,
            provider_options=provider_options,
        )
        response = await self._acreate_image_response(
            request,
            message="OpenAI async image generation request failed.",
        )
        return from_openai_image_response(response)

    def stream_generate_image(
        self,
        *,
        model: str,
        prompt: str,
        input_items: list[Item] | tuple[Item, ...] = (),
        quality: str | None = None,
        background: str | None = None,
        output_format: str | None = None,
        response_format: str | None = None,
        count: int | None = None,
        watermark: bool = True,
        stream_options: StreamOptions | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> Iterator[ImageGenerationStreamEvent]:
        request = ImageGenerationRequest(
            model=model,
            prompt=prompt,
            input_items=input_items,
            quality=quality,
            background=background,
            output_format=output_format,
            response_format=response_format,
            count=count,
            watermark=watermark,
            stream_options=stream_options,
            provider_options=provider_options,
        )
        stream = self._create_image_stream(
            request,
            message="OpenAI stream image generation request failed.",
        )
        for sequence, event in enumerate(stream):
            yield from_openai_image_stream_event(event, sequence=sequence)

    async def astream_generate_image(
        self,
        *,
        model: str,
        prompt: str,
        input_items: list[Item] | tuple[Item, ...] = (),
        quality: str | None = None,
        background: str | None = None,
        output_format: str | None = None,
        response_format: str | None = None,
        count: int | None = None,
        watermark: bool = True,
        stream_options: StreamOptions | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> AsyncIterator[ImageGenerationStreamEvent]:
        request = ImageGenerationRequest(
            model=model,
            prompt=prompt,
            input_items=input_items,
            quality=quality,
            background=background,
            output_format=output_format,
            response_format=response_format,
            count=count,
            watermark=watermark,
            stream_options=stream_options,
            provider_options=provider_options,
        )
        stream = await self._acreate_image_stream(
            request,
            message="OpenAI async stream image generation request failed.",
        )
        sequence = 0
        async for event in stream:
            yield from_openai_image_stream_event(event, sequence=sequence)
            sequence += 1

    def embed(
        self,
        *,
        model: str,
        inputs: list[EmbeddingInput | str] | tuple[EmbeddingInput | str, ...],
        dimensions: int | None = None,
        encoding_format: str | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> EmbeddingResponse:
        request = EmbeddingRequest(
            model=model,
            inputs=inputs,
            dimensions=dimensions,
            encoding_format=encoding_format,
            provider_options=provider_options,
        )
        params = to_openai_embedding_params(request)
        try:
            response = self._sync_client.embeddings.create(**params)
        except Exception as exc:
            raise _provider_request_error("OpenAI embedding request failed.", "embeddings.create", exc) from exc
        return from_openai_embedding_response(response)

    async def aembed(
        self,
        *,
        model: str,
        inputs: list[EmbeddingInput | str] | tuple[EmbeddingInput | str, ...],
        dimensions: int | None = None,
        encoding_format: str | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> EmbeddingResponse:
        request = EmbeddingRequest(
            model=model,
            inputs=inputs,
            dimensions=dimensions,
            encoding_format=encoding_format,
            provider_options=provider_options,
        )
        params = to_openai_embedding_params(request)
        try:
            response = await self._async_openai_client.embeddings.create(**params)
        except Exception as exc:
            raise _provider_request_error("OpenAI async embedding request failed.", "embeddings.create", exc) from exc
        return from_openai_embedding_response(response)

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

    def _create_generation_response(self, request: GenerationRequest, *, message: str) -> _GenerationCreateResult:
        use_response_delta = _response_delta_enabled(self._adapter_options)
        params = to_openai_generation_params(request, use_remote_context=use_response_delta)
        try:
            response = self._sync_client.responses.create(**params)
            return _generation_create_result(
                response,
                request=request,
                initial_params=params,
                final_params=params,
                refreshed_after_invalid_context=False,
                response_delta_enabled=use_response_delta,
            )
        except Exception as exc:
            if not _should_refresh_remote_context(params, exc):
                raise _provider_request_error(message, "responses.create", exc) from exc
            retry_params = to_openai_generation_params(request, use_remote_context=False)
            try:
                response = self._sync_client.responses.create(**retry_params)
                return _generation_create_result(
                    response,
                    request=request,
                    initial_params=params,
                    final_params=retry_params,
                    refreshed_after_invalid_context=True,
                    response_delta_enabled=use_response_delta,
                )
            except Exception as retry_exc:
                raise _provider_request_error(message, "responses.create", retry_exc) from retry_exc

    async def _acreate_generation_response(
        self,
        request: GenerationRequest,
        *,
        message: str,
    ) -> _GenerationCreateResult:
        use_response_delta = _response_delta_enabled(self._adapter_options)
        params = to_openai_generation_params(request, use_remote_context=use_response_delta)
        try:
            response = await self._async_openai_client.responses.create(**params)
            return _generation_create_result(
                response,
                request=request,
                initial_params=params,
                final_params=params,
                refreshed_after_invalid_context=False,
                response_delta_enabled=use_response_delta,
            )
        except Exception as exc:
            if not _should_refresh_remote_context(params, exc):
                raise _provider_request_error(message, "responses.create", exc) from exc
            retry_params = to_openai_generation_params(request, use_remote_context=False)
            try:
                response = await self._async_openai_client.responses.create(**retry_params)
                return _generation_create_result(
                    response,
                    request=request,
                    initial_params=params,
                    final_params=retry_params,
                    refreshed_after_invalid_context=True,
                    response_delta_enabled=use_response_delta,
                )
            except Exception as retry_exc:
                raise _provider_request_error(message, "responses.create", retry_exc) from retry_exc

    def _create_generation_stream(self, request: GenerationRequest, *, message: str) -> Any:
        use_response_delta = _response_delta_enabled(self._adapter_options)
        params = to_openai_generation_params(request, stream=True, use_remote_context=use_response_delta)
        try:
            return self._sync_client.responses.create(**params)
        except Exception as exc:
            if not _should_refresh_remote_context(params, exc):
                raise _provider_request_error(message, "responses.create", exc) from exc
            retry_params = to_openai_generation_params(request, stream=True, use_remote_context=False)
            try:
                return self._sync_client.responses.create(**retry_params)
            except Exception as retry_exc:
                raise _provider_request_error(message, "responses.create", retry_exc) from retry_exc

    async def _acreate_generation_stream(self, request: GenerationRequest, *, message: str) -> Any:
        use_response_delta = _response_delta_enabled(self._adapter_options)
        params = to_openai_generation_params(request, stream=True, use_remote_context=use_response_delta)
        try:
            return await self._async_openai_client.responses.create(**params)
        except Exception as exc:
            if not _should_refresh_remote_context(params, exc):
                raise _provider_request_error(message, "responses.create", exc) from exc
            retry_params = to_openai_generation_params(request, stream=True, use_remote_context=False)
            try:
                return await self._async_openai_client.responses.create(**retry_params)
            except Exception as retry_exc:
                raise _provider_request_error(message, "responses.create", retry_exc) from retry_exc

    def _create_image_response(self, request: ImageGenerationRequest, *, message: str) -> Any:
        operation, params = to_openai_image_params(request)
        try:
            return _call_openai_image_operation(self._sync_client, operation, params)
        except Exception as exc:
            raise _provider_request_error(message, operation, exc) from exc

    async def _acreate_image_response(self, request: ImageGenerationRequest, *, message: str) -> Any:
        operation, params = to_openai_image_params(request)
        try:
            return await _acall_openai_image_operation(self._async_openai_client, operation, params)
        except Exception as exc:
            raise _provider_request_error(message, operation, exc) from exc

    def _create_image_stream(self, request: ImageGenerationRequest, *, message: str) -> Any:
        operation, params = to_openai_image_params(request, stream=True)
        try:
            return _call_openai_image_operation(self._sync_client, operation, params)
        except Exception as exc:
            raise _provider_request_error(message, operation, exc) from exc

    async def _acreate_image_stream(self, request: ImageGenerationRequest, *, message: str) -> Any:
        operation, params = to_openai_image_params(request, stream=True)
        try:
            return await _acall_openai_image_operation(self._async_openai_client, operation, params)
        except Exception as exc:
            raise _provider_request_error(message, operation, exc) from exc

    @property
    def _sync_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(**reveal_secret_values(self._client_options))
        return self._client

    @property
    def _async_openai_client(self) -> Any:
        if self._async_client is None:
            from openai import AsyncOpenAI

            self._async_client = AsyncOpenAI(**reveal_secret_values(self._client_options))
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


def _adapter_options(config: ClientConfig | None) -> dict[str, Any]:
    return dict(config.adapter_options or {}) if config else {}


def _response_delta_enabled(adapter_options: Mapping[str, Any]) -> bool:
    remote_context_options = adapter_options.get("remote_context", {})
    if not isinstance(remote_context_options, Mapping):
        return True
    mode = remote_context_options.get("response_delta", "auto")
    if mode is None:
        return True
    if isinstance(mode, str):
        return mode.strip().lower() not in _DISABLED_RESPONSE_DELTA_VALUES
    return bool(mode)


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
        "OpenAIClient requires api_key or ClientConfig.api_key at initialization "
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


def _call_openai_image_operation(client: Any, operation: str, params: Mapping[str, Any]) -> Any:
    if operation == "images.generate":
        return client.images.generate(**params)
    if operation == "images.edit":
        return client.images.edit(**params)
    raise ValueError(f"Unsupported OpenAI image operation: {operation}")


async def _acall_openai_image_operation(client: Any, operation: str, params: Mapping[str, Any]) -> Any:
    if operation == "images.generate":
        return await client.images.generate(**params)
    if operation == "images.edit":
        return await client.images.edit(**params)
    raise ValueError(f"Unsupported OpenAI image operation: {operation}")


def _generation_create_result(
    response: Any,
    *,
    request: GenerationRequest,
    initial_params: Mapping[str, Any],
    final_params: Mapping[str, Any],
    refreshed_after_invalid_context: bool,
    response_delta_enabled: bool,
) -> _GenerationCreateResult:
    return _GenerationCreateResult(
        response=response,
        metadata=_response_style_remote_context_metadata(
            request=request,
            initial_params=initial_params,
            final_params=final_params,
            refreshed_after_invalid_context=refreshed_after_invalid_context,
            response_delta_enabled=response_delta_enabled,
        ),
    )


def _response_style_remote_context_metadata(
    *,
    request: GenerationRequest,
    initial_params: Mapping[str, Any],
    final_params: Mapping[str, Any],
    refreshed_after_invalid_context: bool,
    response_delta_enabled: bool,
) -> dict[str, Any]:
    if request.remote_context is None:
        return {}
    metadata: dict[str, Any] = {
        "api_family": "responses",
        "cache_enabled": request.remote_context.enable_cache,
        "session_cache_enabled": bool(request.remote_context.enable_cache and request.remote_context.session_key),
        "session_key_present": request.remote_context.session_key is not None,
        "response_delta_mode": "auto" if response_delta_enabled else "disabled",
        "response_delta_disabled_by_adapter_options": not response_delta_enabled,
        "attempted_previous_response_id": bool(initial_params.get("previous_response_id")),
        "final_request_used_previous_response_id": bool(final_params.get("previous_response_id")),
        "refreshed_after_invalid_context": refreshed_after_invalid_context,
    }
    if request.remote_context.new_items_start_index is not None:
        metadata["new_items_start_index"] = request.remote_context.new_items_start_index
    return {"remote_context": metadata}


def _with_generation_metadata(
    response: GenerationResponse,
    metadata: Mapping[str, Any],
) -> GenerationResponse:
    if not metadata:
        return response
    merged = dict(response.metadata)
    merged.update(dict(metadata))
    return replace(response, metadata=merged)


def _should_refresh_remote_context(params: Mapping[str, Any], exc: BaseException) -> bool:
    if not params.get("previous_response_id"):
        return False
    return _is_remote_context_invalid_error(exc)


def _is_remote_context_invalid_error(exc: BaseException) -> bool:
    body = _get_error_body(exc)
    error_payload = _get_error_payload(body)
    error_param = str(_get_attr(error_payload, "param", "") or "").lower()
    if error_param in {"previous_response_id", "previous_response"}:
        return True
    haystack = " ".join(
        str(value or "").lower()
        for value in (
            _get_attr(error_payload, "code", None),
            _get_attr(error_payload, "type", None),
            _get_attr(error_payload, "message", None),
            _get_attr(exc, "message", None),
            str(exc),
        )
    )
    return (
        "previous_response_id" in haystack
        or "previous response" in haystack
        or ("response" in haystack and "expired" in haystack)
        or ("context" in haystack and "expired" in haystack)
        or ("context" in haystack and "invalid" in haystack)
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
