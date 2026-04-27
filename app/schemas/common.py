"""Common Pydantic schemas: error envelope, pagination metadata, generic page response.

Spec §9.1 / §9.5; rules in ``.cursor/rules/api-design.mdc`` and
``.cursor/rules/pydantic-v2.mdc``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ResponseModel(BaseModel):
    """Base for response DTOs. ``from_attributes=True`` so they read ORM rows directly."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
    )


class RequestModel(BaseModel):
    """Base for request DTOs. Strict: unknown keys rejected."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


# ── Error envelope ───────────────────────────────────────────────


class ErrorBody(BaseModel):
    """Inner ``error`` object — see spec §9.1."""

    code: str = Field(..., description="Stable, locale-independent SCREAMING_SNAKE_CASE code.")
    message: str = Field(..., description="Locale-translated, human-readable message.")
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str = ""
    timestamp: datetime | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class ErrorEnvelope(BaseModel):
    """Outer error envelope returned for all 4xx / 5xx responses."""

    error: ErrorBody

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


# ── Pagination ───────────────────────────────────────────────────


class PageMeta(BaseModel):
    """Pagination metadata."""

    page: int = Field(..., ge=1)
    size: int = Field(..., ge=1)
    total: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_prev: bool

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class PageResponse(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: Sequence[T]
    meta: PageMeta

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


# ── OK envelope (rare; mostly for action endpoints) ─────────────


class StatusResponse(BaseModel):
    """Tiny ``{"status": "ok"}`` response for action endpoints."""

    status: str = "ok"

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
