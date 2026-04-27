"""Prometheus metrics registry + custom metrics + scrape helpers.

Spec §13.2; rules in ``.cursor/rules/observability.mdc``.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)


def get_registry() -> CollectorRegistry:
    """Return the registry, multiprocess-aware when ``PROMETHEUS_MULTIPROC_DIR`` is set."""
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if multiproc_dir:
        registry = CollectorRegistry()
        _register_multiproc: Callable[[CollectorRegistry], object] = cast(
            "Callable[[CollectorRegistry], object]",
            multiprocess.MultiProcessCollector,
        )
        _register_multiproc(registry)
        return registry
    # Default registry already includes process + platform collectors when imported.
    from prometheus_client import REGISTRY

    return REGISTRY


def reset_multiproc_dir() -> None:
    """Clean ``PROMETHEUS_MULTIPROC_DIR`` at container start (multi-worker hygiene)."""
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not multiproc_dir:
        return
    path = Path(multiproc_dir)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def render_metrics() -> tuple[bytes, str]:
    """Return ``(body, content_type)`` for an HTTP response."""
    return generate_latest(get_registry()), CONTENT_TYPE_LATEST


# ── Custom metrics (exported, low-cardinality labels only) ──────


HTTP_REQUESTS_TOTAL: Counter = Counter(
    "http_requests_total",
    "Total HTTP requests handled, labelled by method, route, and status class.",
    labelnames=("method", "route", "status_class"),
)

HTTP_REQUEST_DURATION_SECONDS: Histogram = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds, labelled by method and route.",
    labelnames=("method", "route"),
)

HTTP_IN_FLIGHT: Gauge = Gauge(
    "http_in_flight",
    "Number of HTTP requests currently being handled.",
)

I18N_MISSING_KEYS_TOTAL: Counter = Counter(
    "i18n_missing_key_total",
    "Translation keys missing from the loaded catalog.",
    labelnames=("locale",),
)

EMAIL_LOCALE_FALLBACK_TOTAL: Counter = Counter(
    "email_locale_fallback_total",
    "Times an email template fell back to the default locale because the requested locale was missing.",
    labelnames=("template", "locale"),
)

CELERY_CRON_LOCK_SKIPPED_TOTAL: Counter = Counter(
    "celery_cron_lock_skipped_total",
    "Scheduled task ticks skipped because a peer holds the distributed lock.",
    labelnames=("task",),
)


__all__ = [
    "CELERY_CRON_LOCK_SKIPPED_TOTAL",
    "EMAIL_LOCALE_FALLBACK_TOTAL",
    "HTTP_IN_FLIGHT",
    "HTTP_REQUESTS_TOTAL",
    "HTTP_REQUEST_DURATION_SECONDS",
    "I18N_MISSING_KEYS_TOTAL",
    "get_registry",
    "render_metrics",
    "reset_multiproc_dir",
]


# Type-alias to keep mypy happy when these are passed around.
Metric = Any
