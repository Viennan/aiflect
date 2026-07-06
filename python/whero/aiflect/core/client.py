"""Common provider client configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

DEFAULT_SECRET_OPTION_NAMES = frozenset(
    {
        "api_key",
    }
)


@dataclass(frozen=True, slots=True)
class SecretString:
    """A string wrapper that redacts secret values in repr output."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("SecretString.value must not be empty.")

    def reveal(self) -> str:
        """Return the raw secret value for provider SDK initialization."""

        return self.value

    def __repr__(self) -> str:
        return "SecretString('********')"

    def __str__(self) -> str:
        return "********"


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """Common provider client initialization options."""

    api_key: str | SecretString | None = None
    base_url: str | None = None
    timeout: float | None = None
    max_retries: int | None = None
    provider_options: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.api_key is not None:
            object.__setattr__(self, "api_key", to_secret_string(self.api_key))
        if self.provider_options is not None:
            object.__setattr__(
                self,
                "provider_options",
                secretize_client_options(self.provider_options),
            )


def to_secret_string(value: str | SecretString) -> SecretString:
    """Return a SecretString, preserving existing wrappers."""

    if isinstance(value, SecretString):
        return value
    return SecretString(value)


def secretize_client_options(
    options: Mapping[str, Any],
    *,
    secret_option_names: frozenset[str] = DEFAULT_SECRET_OPTION_NAMES,
) -> dict[str, Any]:
    """Copy client options while wrapping known top-level secret fields."""

    secret_names = {name.lower() for name in secret_option_names}
    copied = dict(options)
    for key, value in tuple(copied.items()):
        if value is not None and str(key).lower() in secret_names:
            copied[key] = to_secret_string(value)
    return copied


def reveal_secret_values(value: Any) -> Any:
    """Recursively reveal SecretString values for provider SDK calls."""

    if isinstance(value, SecretString):
        return value.reveal()
    if isinstance(value, Mapping):
        return {key: reveal_secret_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [reveal_secret_values(item) for item in value]
    if isinstance(value, tuple):
        return tuple(reveal_secret_values(item) for item in value)
    return value
