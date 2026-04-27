"""Unit tests for cron window keys (Celery Beat lock alignment)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.utils.cron_windows import utc_cron_window_key


@pytest.mark.unit
def test_utc_cron_window_key_floors_to_step_minutes() -> None:
    now = datetime(2026, 4, 28, 12, 7, 30, tzinfo=UTC)
    assert utc_cron_window_key(now, step_minutes=5) == "2026-04-28T12:05:00+00:00"


@pytest.mark.unit
def test_utc_cron_window_key_aligns_hour_boundary() -> None:
    now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC)
    assert utc_cron_window_key(now, step_minutes=5) == "2026-04-28T12:00:00+00:00"


@pytest.mark.unit
def test_utc_cron_window_key_rejects_naive_datetime() -> None:
    naive = datetime(2026, 4, 28, 12, 0, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        utc_cron_window_key(naive, step_minutes=5)


@pytest.mark.unit
def test_utc_cron_window_key_rejects_invalid_step() -> None:
    now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="step_minutes"):
        utc_cron_window_key(now, step_minutes=0)
