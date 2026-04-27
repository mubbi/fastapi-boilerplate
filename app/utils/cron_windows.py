"""Helpers for aligning distributed locks with Celery Beat cron windows."""

from __future__ import annotations

from datetime import datetime


def utc_cron_window_key(now: datetime, *, step_minutes: int) -> str:
    """Return an ISO-8601 key for the start of the current cron window in ``now``'s timezone.

    For a schedule of every ``step_minutes`` (e.g. 5 for ``crontab(minute="*/5")``), all
    invocations in the same wall-clock window share one key, so a Redis ``SET NX`` lock
    deduplicates work across Beat replicas for that tick.

    Args:
        now: Timezone-aware ``datetime`` (use UTC in workers).
        step_minutes: Cron step in minutes; must be in ``[1, 60]`` and divide 60 for
            typical ``*/N`` crontab alignment.

    Returns:
        ISO-8601 timestamp string for the window start (e.g. ``2026-04-28T12:10:00+00:00``).
    """
    if now.tzinfo is None:
        msg = "now must be timezone-aware"
        raise ValueError(msg)
    if not 1 <= step_minutes <= 60:
        msg = "step_minutes must be between 1 and 60"
        raise ValueError(msg)
    minute_floor = (now.minute // step_minutes) * step_minutes
    window_start = now.replace(minute=minute_floor, second=0, microsecond=0)
    return window_start.isoformat()
