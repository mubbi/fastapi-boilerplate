"""Project-wide constants. Magic numbers/strings in code = review-reject."""

from typing import Final

# ── HTTP correlation headers ────────────────────────────────────
HEADER_REQUEST_ID: Final[str] = "X-Request-ID"
HEADER_API_VERSION: Final[str] = "X-API-Version"
HEADER_CONTENT_LANGUAGE: Final[str] = "Content-Language"
HEADER_IDEMPOTENCY_KEY: Final[str] = "Idempotency-Key"
HEADER_RETRY_AFTER: Final[str] = "Retry-After"

# ── Pagination caps ─────────────────────────────────────────────
PAGINATION_DEFAULT_PAGE: Final[int] = 1
PAGINATION_DEFAULT_SIZE: Final[int] = 20
PAGINATION_MAX_SIZE: Final[int] = 100

# ── Cache key prefix (versioned, see cache-redis.mdc) ───────────
CACHE_KEY_PREFIX: Final[str] = "boilerplate"
CACHE_KEY_VERSION: Final[str] = "v1"

# ── Idempotency ─────────────────────────────────────────────────
IDEMPOTENCY_TTL_SECONDS: Final[int] = 60 * 60 * 24

# ── /ready cache ────────────────────────────────────────────────
READY_CHECK_CACHE_TTL_SECONDS: Final[float] = 5.0
READY_CHECK_TIMEOUT_SECONDS: Final[float] = 1.0

# ── Celery Beat: system.heartbeat (``crontab(minute="*/5")``) ────
CELERY_HEARTBEAT_CRON_MINUTES: Final[int] = 5
# Drop scheduled messages not claimed before the next tick (``celery-beat.mdc``).
CELERY_HEARTBEAT_BEAT_EXPIRES_SECONDS: Final[int] = 270

# ── Audit logger name (separate sink, never sampled) ────────────
AUDIT_LOGGER_NAME: Final[str] = "audit"
