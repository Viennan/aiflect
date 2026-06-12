"""Volcengine Ark provider client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator, Mapping
from dataclasses import dataclass, replace
import time
from typing import Any

from whero.vatbrain.core.capabilities import AdapterCapability, ModelCapability
from whero.vatbrain.core.client import (
    ClientConfig,
    SecretString,
    reveal_secret_values,
    secretize_client_options,
    to_secret_string,
)
from whero.vatbrain.core.embeddings import EmbeddingInput, EmbeddingRequest, EmbeddingResponse
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
from whero.vatbrain.core.media import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageGenerationStreamEvent,
    MediaGenerationTask,
    TaskStatus,
    VideoGenerationRequest,
)
from whero.vatbrain.core.resources import (
    FilePreprocessConfig,
    FileResource,
    FileUploadRequest,
)
from whero.vatbrain.core.tools import ToolSpec
from whero.vatbrain.providers.volcengine.capabilities import (
    get_adapter_capability,
    get_model_capability,
)
from whero.vatbrain.providers.volcengine.embeddings import (
    from_volcengine_embedding_response,
    to_volcengine_embedding_params,
)
from whero.vatbrain.providers.volcengine.files import (
    from_volcengine_file_delete_response,
    from_volcengine_file_resource,
    to_volcengine_file_create_params,
    to_volcengine_file_list_params,
)
from whero.vatbrain.providers.volcengine.media import (
    from_volcengine_image_response,
    from_volcengine_image_stream_event,
    from_volcengine_video_task,
    from_volcengine_video_task_create_response,
    to_volcengine_image_params,
    to_volcengine_video_task_create_params,
)
from whero.vatbrain.providers.volcengine.mapper import (
    PROVIDER,
    from_volcengine_generation_response,
    to_volcengine_generation_params,
    volcengine_previous_response_is_expiring,
    volcengine_response_expire_at_for,
)
from whero.vatbrain.providers.volcengine.stream import from_volcengine_stream_event
from whero.vatbrain.structured import ParsedGenerationResponse, pydantic_output


@dataclass(frozen=True, slots=True)
class _GenerationCreateResult:
    response: Any
    metadata: dict[str, Any]


class VolcengineClient:
    """Provider-level Volcengine Ark adapter client."""

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
        **ark_client_options: Any,
    ) -> None:
        self._client = client
        self._async_client = async_client
        self._client_options = _merge_client_options(
            config=config,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            provider_options=ark_client_options,
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
        result = self._create_generation_response(
            request,
            message="Volcengine generation request failed.",
        )
        return _with_generation_metadata(
            from_volcengine_generation_response(result.response),
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
            message="Volcengine async generation request failed.",
        )
        return _with_generation_metadata(
            from_volcengine_generation_response(result.response),
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
        stream = self._create_generation_stream(
            request,
            message="Volcengine stream generation request failed.",
        )
        for sequence, event in enumerate(stream):
            yield from_volcengine_stream_event(event, sequence=sequence)

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
            message="Volcengine async stream generation request failed.",
        )
        sequence = 0
        async for event in stream:
            yield from_volcengine_stream_event(event, sequence=sequence)
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
            message="Volcengine image generation request failed.",
        )
        return from_volcengine_image_response(response)

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
            message="Volcengine async image generation request failed.",
        )
        return from_volcengine_image_response(response)

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
            message="Volcengine stream image generation request failed.",
        )
        for sequence, event in enumerate(stream):
            yield from_volcengine_image_stream_event(event, sequence=sequence)

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
            message="Volcengine async stream image generation request failed.",
        )
        sequence = 0
        async for event in stream:
            yield from_volcengine_image_stream_event(event, sequence=sequence)
            sequence += 1

    def create_video_generation_task(
        self,
        *,
        model: str,
        prompt: str,
        input_items: list[Item] | tuple[Item, ...] = (),
        duration_seconds: float | None = None,
        ratio: str | None = None,
        resolution: str | None = None,
        generate_audio: bool | None = None,
        watermark: bool = True,
        stream_options: StreamOptions | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> MediaGenerationTask:
        request = VideoGenerationRequest(
            model=model,
            prompt=prompt,
            input_items=input_items,
            duration_seconds=duration_seconds,
            ratio=ratio,
            resolution=resolution,
            generate_audio=generate_audio,
            watermark=watermark,
            stream_options=stream_options,
            provider_options=provider_options,
        )
        response = self._create_video_task(
            request,
            message="Volcengine video generation task create request failed.",
        )
        return from_volcengine_video_task_create_response(response, model=request.model)

    async def acreate_video_generation_task(
        self,
        *,
        model: str,
        prompt: str,
        input_items: list[Item] | tuple[Item, ...] = (),
        duration_seconds: float | None = None,
        ratio: str | None = None,
        resolution: str | None = None,
        generate_audio: bool | None = None,
        watermark: bool = True,
        stream_options: StreamOptions | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> MediaGenerationTask:
        request = VideoGenerationRequest(
            model=model,
            prompt=prompt,
            input_items=input_items,
            duration_seconds=duration_seconds,
            ratio=ratio,
            resolution=resolution,
            generate_audio=generate_audio,
            watermark=watermark,
            stream_options=stream_options,
            provider_options=provider_options,
        )
        response = await self._acreate_video_task(
            request,
            message="Volcengine async video generation task create request failed.",
        )
        return from_volcengine_video_task_create_response(response, model=request.model)

    def get_video_generation_task(
        self,
        task_id: str,
        *,
        provider_options: dict[str, Any] | None = None,
    ) -> MediaGenerationTask:
        try:
            response = self._sync_client.content_generation.tasks.get(
                task_id=task_id,
                **dict(provider_options or {}),
            )
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine video generation task get request failed.",
                "content_generation.tasks.get",
                exc,
            ) from exc
        return from_volcengine_video_task(response)

    async def aget_video_generation_task(
        self,
        task_id: str,
        *,
        provider_options: dict[str, Any] | None = None,
    ) -> MediaGenerationTask:
        try:
            response = await self._async_ark_client.content_generation.tasks.get(
                task_id=task_id,
                **dict(provider_options or {}),
            )
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine async video generation task get request failed.",
                "content_generation.tasks.get",
                exc,
            ) from exc
        return from_volcengine_video_task(response)

    def wait_for_video_generation_task(
        self,
        task_id: str,
        *,
        poll_interval: float = 10.0,
        max_wait_seconds: float = 600.0,
        provider_options: dict[str, Any] | None = None,
    ) -> MediaGenerationTask:
        deadline = time.monotonic() + max_wait_seconds
        terminal = {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELED,
            TaskStatus.EXPIRED,
        }
        while True:
            task = self.get_video_generation_task(task_id, provider_options=provider_options)
            if task.status in terminal:
                return task
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Volcengine video generation task {task_id!r} did not finish "
                    f"within {max_wait_seconds} seconds."
                )
            time.sleep(poll_interval)

    async def await_video_generation_task(
        self,
        task_id: str,
        *,
        poll_interval: float = 10.0,
        max_wait_seconds: float = 600.0,
        provider_options: dict[str, Any] | None = None,
    ) -> MediaGenerationTask:
        deadline = time.monotonic() + max_wait_seconds
        terminal = {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELED,
            TaskStatus.EXPIRED,
        }
        while True:
            task = await self.aget_video_generation_task(task_id, provider_options=provider_options)
            if task.status in terminal:
                return task
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Volcengine video generation task {task_id!r} did not finish "
                    f"within {max_wait_seconds} seconds."
                )
            await asyncio.sleep(poll_interval)

    def embed(
        self,
        *,
        model: str,
        inputs: list[EmbeddingInput | str] | tuple[EmbeddingInput | str, ...],
        instructions: str | None = None,
        dimensions: int | None = None,
        encoding_format: str | None = None,
        sparse_embedding: bool | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> EmbeddingResponse:
        request = EmbeddingRequest(
            model=model,
            inputs=inputs,
            instructions=instructions,
            dimensions=dimensions,
            encoding_format=encoding_format,
            sparse_embedding=sparse_embedding,
            provider_options=provider_options,
        )
        params = to_volcengine_embedding_params(request)
        try:
            response = self._sync_client.multimodal_embeddings.create(**params)
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine embedding request failed.",
                "multimodal_embeddings.create",
                exc,
            ) from exc
        return from_volcengine_embedding_response(response)

    async def aembed(
        self,
        *,
        model: str,
        inputs: list[EmbeddingInput | str] | tuple[EmbeddingInput | str, ...],
        instructions: str | None = None,
        dimensions: int | None = None,
        encoding_format: str | None = None,
        sparse_embedding: bool | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> EmbeddingResponse:
        request = EmbeddingRequest(
            model=model,
            inputs=inputs,
            instructions=instructions,
            dimensions=dimensions,
            encoding_format=encoding_format,
            sparse_embedding=sparse_embedding,
            provider_options=provider_options,
        )
        params = to_volcengine_embedding_params(request)
        try:
            response = await self._async_ark_client.multimodal_embeddings.create(**params)
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine async embedding request failed.",
                "multimodal_embeddings.create",
                exc,
            ) from exc
        return from_volcengine_embedding_response(response)

    def upload_file(
        self,
        *,
        file: Any,
        filename: str | None = None,
        purpose: str | None = None,
        mime_type: str | None = None,
        preprocess: FilePreprocessConfig | None = None,
        expire_at: int | None = None,
        provider_options: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FileResource:
        request = FileUploadRequest(
            file=file,
            filename=filename,
            mime_type=mime_type,
            preprocess=preprocess,
            provider_options=_file_provider_options(purpose, expire_at, provider_options),
            metadata=metadata or {},
        )
        params = to_volcengine_file_create_params(request)
        try:
            response = self._sync_client.files.create(**params)
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine file upload request failed.",
                "files.create",
                exc,
            ) from exc
        return from_volcengine_file_resource(response)

    async def aupload_file(
        self,
        *,
        file: Any,
        filename: str | None = None,
        purpose: str | None = None,
        mime_type: str | None = None,
        preprocess: FilePreprocessConfig | None = None,
        expire_at: int | None = None,
        provider_options: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FileResource:
        request = FileUploadRequest(
            file=file,
            filename=filename,
            mime_type=mime_type,
            preprocess=preprocess,
            provider_options=_file_provider_options(purpose, expire_at, provider_options),
            metadata=metadata or {},
        )
        params = to_volcengine_file_create_params(request)
        try:
            response = await self._async_ark_client.files.create(**params)
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine async file upload request failed.",
                "files.create",
                exc,
            ) from exc
        return from_volcengine_file_resource(response)

    def retrieve_file(
        self,
        file_id: str,
        *,
        provider_options: dict[str, Any] | None = None,
    ) -> FileResource:
        try:
            response = self._sync_client.files.retrieve(file_id, **dict(provider_options or {}))
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine file retrieve request failed.",
                "files.retrieve",
                exc,
            ) from exc
        return from_volcengine_file_resource(response)

    async def aretrieve_file(
        self,
        file_id: str,
        *,
        provider_options: dict[str, Any] | None = None,
    ) -> FileResource:
        try:
            response = await self._async_ark_client.files.retrieve(file_id, **dict(provider_options or {}))
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine async file retrieve request failed.",
                "files.retrieve",
                exc,
            ) from exc
        return from_volcengine_file_resource(response)

    def list_files(
        self,
        *,
        purpose: str | None = None,
        limit: int | None = None,
        after: str | None = None,
        order: str | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> tuple[FileResource, ...]:
        params = to_volcengine_file_list_params(
            purpose=purpose,
            limit=limit,
            after=after,
            order=order,
            provider_options=provider_options,
        )
        try:
            page = self._sync_client.files.list(**params)
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine file list request failed.",
                "files.list",
                exc,
            ) from exc
        return tuple(from_volcengine_file_resource(item) for item in _iter_page_items(page))

    async def alist_files(
        self,
        *,
        purpose: str | None = None,
        limit: int | None = None,
        after: str | None = None,
        order: str | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> tuple[FileResource, ...]:
        params = to_volcengine_file_list_params(
            purpose=purpose,
            limit=limit,
            after=after,
            order=order,
            provider_options=provider_options,
        )
        try:
            page = self._async_ark_client.files.list(**params)
            resources = []
            async for item in page:
                resources.append(from_volcengine_file_resource(item))
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine async file list request failed.",
                "files.list",
                exc,
            ) from exc
        return tuple(resources)

    def delete_file(
        self,
        file_id: str,
        *,
        provider_options: dict[str, Any] | None = None,
    ) -> FileResource:
        try:
            response = self._sync_client.files.delete(file_id, **dict(provider_options or {}))
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine file delete request failed.",
                "files.delete",
                exc,
            ) from exc
        return from_volcengine_file_delete_response(response, file_id=file_id)

    async def adelete_file(
        self,
        file_id: str,
        *,
        provider_options: dict[str, Any] | None = None,
    ) -> FileResource:
        try:
            response = await self._async_ark_client.files.delete(file_id, **dict(provider_options or {}))
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine async file delete request failed.",
                "files.delete",
                exc,
            ) from exc
        return from_volcengine_file_delete_response(response, file_id=file_id)

    def wait_for_file_processing(
        self,
        file_id: str,
        *,
        poll_interval: float = 3.0,
        max_wait_seconds: float = 600.0,
    ) -> FileResource:
        try:
            response = self._sync_client.files.wait_for_processing(
                file_id,
                poll_interval=poll_interval,
                max_wait_seconds=max_wait_seconds,
            )
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine wait-for-file-processing request failed.",
                "files.wait_for_processing",
                exc,
            ) from exc
        return from_volcengine_file_resource(response)

    async def await_file_processing(
        self,
        file_id: str,
        *,
        poll_interval: float = 3.0,
        max_wait_seconds: float = 600.0,
    ) -> FileResource:
        try:
            response = await self._async_ark_client.files.wait_for_processing(
                file_id,
                poll_interval=poll_interval,
                max_wait_seconds=max_wait_seconds,
            )
        except Exception as exc:
            raise _provider_request_error(
                "Volcengine async wait-for-file-processing request failed.",
                "files.wait_for_processing",
                exc,
            ) from exc
        return from_volcengine_file_resource(response)

    async def await_for_file_processing(
        self,
        file_id: str,
        *,
        poll_interval: float = 3.0,
        max_wait_seconds: float = 600.0,
    ) -> FileResource:
        return await self.await_file_processing(
            file_id,
            poll_interval=poll_interval,
            max_wait_seconds=max_wait_seconds,
        )

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
        request_time = int(time.time())
        params = to_volcengine_generation_params(request, now=request_time)
        try:
            response = self._sync_client.responses.create(**params)
            return _generation_create_result(
                response,
                request=request,
                initial_params=params,
                final_params=params,
                refreshed_after_invalid_context=False,
                request_time=request_time,
            )
        except Exception as exc:
            if not _should_refresh_remote_context(params, exc):
                raise _provider_request_error(message, "responses.create", exc) from exc
            retry_params = to_volcengine_generation_params(
                request,
                use_remote_context=False,
                now=int(time.time()),
            )
            try:
                response = self._sync_client.responses.create(**retry_params)
                return _generation_create_result(
                    response,
                    request=request,
                    initial_params=params,
                    final_params=retry_params,
                    refreshed_after_invalid_context=True,
                    request_time=request_time,
                )
            except Exception as retry_exc:
                raise _provider_request_error(message, "responses.create", retry_exc) from retry_exc

    async def _acreate_generation_response(
        self,
        request: GenerationRequest,
        *,
        message: str,
    ) -> _GenerationCreateResult:
        request_time = int(time.time())
        params = to_volcengine_generation_params(request, now=request_time)
        try:
            response = await self._async_ark_client.responses.create(**params)
            return _generation_create_result(
                response,
                request=request,
                initial_params=params,
                final_params=params,
                refreshed_after_invalid_context=False,
                request_time=request_time,
            )
        except Exception as exc:
            if not _should_refresh_remote_context(params, exc):
                raise _provider_request_error(message, "responses.create", exc) from exc
            retry_params = to_volcengine_generation_params(
                request,
                use_remote_context=False,
                now=int(time.time()),
            )
            try:
                response = await self._async_ark_client.responses.create(**retry_params)
                return _generation_create_result(
                    response,
                    request=request,
                    initial_params=params,
                    final_params=retry_params,
                    refreshed_after_invalid_context=True,
                    request_time=request_time,
                )
            except Exception as retry_exc:
                raise _provider_request_error(message, "responses.create", retry_exc) from retry_exc

    def _create_generation_stream(self, request: GenerationRequest, *, message: str) -> Any:
        params = to_volcengine_generation_params(request, stream=True, now=int(time.time()))
        try:
            return self._sync_client.responses.create(**params)
        except Exception as exc:
            if not _should_refresh_remote_context(params, exc):
                raise _provider_request_error(message, "responses.create", exc) from exc
            retry_params = to_volcengine_generation_params(
                request,
                stream=True,
                use_remote_context=False,
                now=int(time.time()),
            )
            try:
                return self._sync_client.responses.create(**retry_params)
            except Exception as retry_exc:
                raise _provider_request_error(message, "responses.create", retry_exc) from retry_exc

    async def _acreate_generation_stream(self, request: GenerationRequest, *, message: str) -> Any:
        params = to_volcengine_generation_params(request, stream=True, now=int(time.time()))
        try:
            return await self._async_ark_client.responses.create(**params)
        except Exception as exc:
            if not _should_refresh_remote_context(params, exc):
                raise _provider_request_error(message, "responses.create", exc) from exc
            retry_params = to_volcengine_generation_params(
                request,
                stream=True,
                use_remote_context=False,
                now=int(time.time()),
            )
            try:
                return await self._async_ark_client.responses.create(**retry_params)
            except Exception as retry_exc:
                raise _provider_request_error(message, "responses.create", retry_exc) from retry_exc

    def _create_image_response(self, request: ImageGenerationRequest, *, message: str) -> Any:
        params = to_volcengine_image_params(request)
        try:
            return self._sync_client.images.generate(**params)
        except Exception as exc:
            raise _provider_request_error(message, "images.generate", exc) from exc

    async def _acreate_image_response(self, request: ImageGenerationRequest, *, message: str) -> Any:
        params = to_volcengine_image_params(request)
        try:
            return await self._async_ark_client.images.generate(**params)
        except Exception as exc:
            raise _provider_request_error(message, "images.generate", exc) from exc

    def _create_image_stream(self, request: ImageGenerationRequest, *, message: str) -> Any:
        params = to_volcengine_image_params(request, stream=True)
        try:
            return self._sync_client.images.generate(**params)
        except Exception as exc:
            raise _provider_request_error(message, "images.generate", exc) from exc

    async def _acreate_image_stream(self, request: ImageGenerationRequest, *, message: str) -> Any:
        params = to_volcengine_image_params(request, stream=True)
        try:
            return await self._async_ark_client.images.generate(**params)
        except Exception as exc:
            raise _provider_request_error(message, "images.generate", exc) from exc

    def _create_video_task(self, request: VideoGenerationRequest, *, message: str) -> Any:
        params = to_volcengine_video_task_create_params(request)
        try:
            return self._sync_client.content_generation.tasks.create(**params)
        except Exception as exc:
            raise _provider_request_error(message, "content_generation.tasks.create", exc) from exc

    async def _acreate_video_task(self, request: VideoGenerationRequest, *, message: str) -> Any:
        params = to_volcengine_video_task_create_params(request)
        try:
            return await self._async_ark_client.content_generation.tasks.create(**params)
        except Exception as exc:
            raise _provider_request_error(message, "content_generation.tasks.create", exc) from exc

    @property
    def _sync_client(self) -> Any:
        if self._client is None:
            from volcenginesdkarkruntime import Ark

            self._client = Ark(**reveal_secret_values(self._client_options))
        return self._client

    @property
    def _async_ark_client(self) -> Any:
        if self._async_client is None:
            from volcenginesdkarkruntime import AsyncArk

            self._async_client = AsyncArk(**reveal_secret_values(self._client_options))
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
        "VolcengineClient requires api_key or ClientConfig.api_key at initialization "
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


def _generation_create_result(
    response: Any,
    *,
    request: GenerationRequest,
    initial_params: Mapping[str, Any],
    final_params: Mapping[str, Any],
    refreshed_after_invalid_context: bool,
    request_time: int,
) -> _GenerationCreateResult:
    return _GenerationCreateResult(
        response=response,
        metadata=_response_style_remote_context_metadata(
            request=request,
            initial_params=initial_params,
            final_params=final_params,
            refreshed_after_invalid_context=refreshed_after_invalid_context,
            request_time=request_time,
        ),
    )


def _response_style_remote_context_metadata(
    *,
    request: GenerationRequest,
    initial_params: Mapping[str, Any],
    final_params: Mapping[str, Any],
    refreshed_after_invalid_context: bool,
    request_time: int,
) -> dict[str, Any]:
    if request.remote_context is None:
        return {}
    previous_response_expire_at = _previous_response_expire_at(request)
    metadata: dict[str, Any] = {
        "api_family": "responses",
        "cache_enabled": request.remote_context.enable_cache,
        "session_cache_enabled": bool(request.remote_context.enable_cache and request.remote_context.session_key),
        "session_key_present": request.remote_context.session_key is not None,
        "attempted_previous_response_id": bool(initial_params.get("previous_response_id")),
        "final_request_used_previous_response_id": bool(final_params.get("previous_response_id")),
        "refreshed_after_invalid_context": refreshed_after_invalid_context,
        "refreshed_before_expiry": _refreshed_before_expiry(
            request,
            initial_params=initial_params,
            request_time=request_time,
        ),
    }
    if previous_response_expire_at is not None:
        metadata["previous_response_expire_at"] = previous_response_expire_at
    if request.remote_context.new_items_start_index is not None:
        metadata["new_items_start_index"] = request.remote_context.new_items_start_index
    return {"remote_context": metadata}


def _previous_response_expire_at(request: GenerationRequest) -> int | None:
    anchor_item = _remote_context_anchor_item(request)
    if anchor_item is None:
        return None
    return volcengine_response_expire_at_for(anchor_item)


def _refreshed_before_expiry(
    request: GenerationRequest,
    *,
    initial_params: Mapping[str, Any],
    request_time: int,
) -> bool:
    remote_context = request.remote_context
    if (
        remote_context is None
        or not remote_context.enable_cache
        or remote_context.session_key is None
        or initial_params.get("previous_response_id")
    ):
        return False
    anchor_item = _remote_context_anchor_item(request)
    if anchor_item is None:
        return False
    return volcengine_previous_response_is_expiring(anchor_item, now=request_time)


def _remote_context_anchor_item(request: GenerationRequest) -> Item | None:
    remote_context = request.remote_context
    if remote_context is None or remote_context.new_items_start_index is None:
        return None
    if remote_context.new_items_start_index <= 0:
        return None
    if remote_context.new_items_start_index > len(request.items):
        return None
    return request.items[remote_context.new_items_start_index - 1]


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


def _file_provider_options(
    purpose: str | None,
    expire_at: int | None,
    provider_options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    options = dict(provider_options or {})
    if purpose is not None:
        options.setdefault("purpose", purpose)
    if expire_at is not None:
        options.setdefault("expire_at", expire_at)
    return options


def _iter_page_items(page: Any) -> Iterator[Any]:
    if isinstance(page, (list, tuple)):
        yield from page
        return
    data = _get_attr(page, "data", None)
    if isinstance(data, (list, tuple)):
        yield from data
        return
    yield from page


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
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)
