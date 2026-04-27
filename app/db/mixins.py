"""Reusable ORM mixins: UUIDv7 primary key, timestamps, soft delete.

UUIDv7 sorts naturally by creation time which is friendly for B-tree indexes
and for time-range queries — preferred over UUIDv4.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, declarative_mixin, mapped_column

from app.utils.ids import new_uuid7


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


@declarative_mixin
class IdMixin:
    """UUIDv7 primary key, generated client-side on insert."""

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid7,
    )


@declarative_mixin
class TimestampMixin:
    """``created_at`` / ``updated_at`` timestamps in UTC."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )


@declarative_mixin
class SoftDeleteMixin:
    """``deleted_at`` column for soft-deletable aggregates.

    Repositories filter on ``deleted_at IS NULL`` by default; use ``include_deleted=True``
    to bypass when explicitly required.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
