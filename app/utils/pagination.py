"""Cursor + offset pagination helpers.

Spec §9.5: GET-list endpoints expose ``page`` + ``size`` (default 20, max 100)
and may layer cursor pagination on top for hot timelines.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from app.core.constants import (
    PAGINATION_DEFAULT_PAGE,
    PAGINATION_DEFAULT_SIZE,
    PAGINATION_MAX_SIZE,
)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PaginationParams:
    """Validated pagination input."""

    page: int = PAGINATION_DEFAULT_PAGE
    size: int = PAGINATION_DEFAULT_SIZE

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.size <= PAGINATION_MAX_SIZE:
            raise ValueError(f"size must be in [1, {PAGINATION_MAX_SIZE}]")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    """Paginated response envelope (matches the public API contract)."""

    items: Sequence[T]
    page: int
    size: int
    total: int

    @property
    def total_pages(self) -> int:
        if self.size == 0:
            return 0
        return (self.total + self.size - 1) // self.size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1
