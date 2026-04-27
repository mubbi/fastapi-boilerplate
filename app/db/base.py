"""SQLAlchemy declarative base + project-wide ``MetaData`` naming convention.

Spec §6; rules in ``.cursor/rules/sqlalchemy-async.mdc`` and
``.cursor/rules/alembic-migrations.mdc``.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Project-wide declarative base.

    Every ORM model in ``app/models/*`` MUST inherit from this class so that the
    naming convention applies uniformly across migrations.
    """

    metadata = metadata
