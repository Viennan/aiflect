"""aiflect error hierarchy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class AiflectError(Exception):
    """Base class for aiflect errors."""


class InvalidItemError(AiflectError):
    """Raised when an item cannot be used in the requested API family."""


class UnsupportedCapabilityError(AiflectError):
    """Raised when a request requires a known unsupported capability."""


@dataclass(frozen=True, slots=True)
class ProviderErrorDetails:
    """Diagnostic details extracted from a provider SDK/API error."""

    provider: str | None = None
    operation: str | None = None
    status_code: int | None = None
    request_id: str | None = None
    error_type: str | None = None
    error_code: str | None = None
    error_param: str | None = None
    raw: Any | None = None


class ProviderRequestError(AiflectError):
    """Raised when a provider SDK call fails."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        operation: str | None = None,
        status_code: int | None = None,
        request_id: str | None = None,
        error_type: str | None = None,
        error_code: str | None = None,
        error_param: str | None = None,
        raw: Any | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.cause = cause
        self.details = ProviderErrorDetails(
            provider=provider,
            operation=operation,
            status_code=status_code,
            request_id=request_id,
            error_type=error_type,
            error_code=error_code,
            error_param=error_param,
            raw=raw,
        )


class ProviderResponseMappingError(AiflectError):
    """Raised when a provider response cannot be mapped into aiflect models."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        operation: str | None = None,
        raw: Any | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.cause = cause
        self.details = ProviderErrorDetails(provider=provider, operation=operation, raw=raw)
