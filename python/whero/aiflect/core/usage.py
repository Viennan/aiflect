"""Usage accounting models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Usage:
    """Normalized token/resource usage with raw provider data retained."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None
    raw: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
