"""Generic repository base + Unit-of-Work helper.

Spec §3.1, §3.2; rules in ``.cursor/rules/repositories-layer.mdc``.

Hard rules enforced here:
- Repositories never call ``commit`` / ``rollback``. Services own the UoW.
- ``BaseRepository`` provides the typed plumbing for one aggregate root.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import inspect as orm_inspect
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.db.mixins import IdMixin

log = get_logger(__name__)

T = TypeVar("T", bound=IdMixin)


# ── Base repository ──────────────────────────────────────────────


class BaseRepository(Generic[T]):
    """Typed CRUD plumbing. Subclasses add aggregate-specific queries."""

    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def get_by_id(self, id_: UUID, *, include_deleted: bool = False) -> T | None:
        try:
            stmt = select(self.model).where(self.model.id == id_)
            if not include_deleted:
                mapper = orm_inspect(self.model)
                if mapper is not None and mapper.has_property("deleted_at"):
                    stmt = stmt.where(mapper.column_attrs["deleted_at"].is_(None))
            result = await self._session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            log.error("repo.get_by_id_failed", model=self.model.__name__, error=str(exc))
            raise ExternalServiceError(message="errors.db.unavailable") from exc

    async def add(self, entity: T) -> T:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def add_all(self, entities: Sequence[T]) -> Sequence[T]:
        self._session.add_all(list(entities))
        await self._session.flush()
        return entities

    async def delete(self, entity: T) -> None:
        await self._session.delete(entity)
        await self._session.flush()

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return await self._session.execute(*args, **kwargs)
