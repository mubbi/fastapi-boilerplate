"""Prove async SQLAlchemy + Postgres on the test stack (migrations applied in CI)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.container import Container


@pytest.mark.integration
async def test_postgres_session_select_one(container: Container) -> None:
    """Baseline persistence path: engine, pool, and DB round-trip to ``postgres_test``."""
    async with container.db_session_factory() as session:
        one = (await session.execute(select(1))).scalar_one()
        assert one == 1
