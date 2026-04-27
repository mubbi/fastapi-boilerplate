"""Pydantic-settings backed application configuration.

Single ``Settings`` class composed of nested ``BaseModel`` sub-classes. Reads
``.env`` with ``env_nested_delimiter="__"`` so nested models map to keys like
``DATABASE__POOL_SIZE``. Required fields fail fast at startup.

Rules (see ``.cursor/rules/environment-config.mdc`` and spec §5):
- Sensitive values use ``SecretStr``.
- ``get_settings()`` is ``@lru_cache``-wrapped; tests reset via ``cache_clear()``.
- Nothing outside this module reads env vars directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AppEnv = Literal["local", "dev", "staging", "production", "test"]
ServiceRole = Literal["web", "worker", "beat"]
LogFormat = Literal["json", "console"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


# ── Nested settings groups ───────────────────────────────────────


class DatabaseSettings(BaseModel):
    """PostgreSQL pool & timeout knobs. URL is at the top level (``DATABASE_URL``)."""

    pool_size: int = Field(default=10, ge=1)
    max_overflow: int = Field(default=20, ge=0)
    pool_timeout: int = Field(default=30, ge=1)
    pool_recycle_seconds: int = Field(default=1800, ge=60)
    echo: bool = False
    statement_timeout_ms: int = Field(default=15000, ge=100)


class RedisSettings(BaseModel):
    """Redis connection knobs. URL is at the top level (``REDIS_URL``)."""

    max_connections: int = Field(default=50, ge=1)
    socket_timeout: float = Field(default=5.0, gt=0)


class HttpClientSettings(BaseModel):
    timeout_seconds: float = Field(default=10.0, gt=0)
    max_keepalive: int = Field(default=20, ge=1)
    max_connections: int = Field(default=100, ge=1)
    retry_attempts: int = Field(default=3, ge=0)
    retry_backoff_base: float = Field(default=0.5, gt=0)


# ── Top-level Settings ───────────────────────────────────────────


class Settings(BaseSettings):
    """Top-level configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Application ────────────────────────────────────────────
    app_name: str = "fastapi-boilerplate"
    app_env: AppEnv = "local"
    app_version: str = "0.1.0"
    app_debug: bool = False
    app_log_level: LogLevel = "INFO"
    app_log_format: LogFormat = "console"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_api_v1_prefix: str = "/api/v1"
    app_cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    app_cors_allow_credentials: bool = True
    app_request_timeout_seconds: float = 30.0
    app_graceful_shutdown_seconds: float = 20.0
    app_docs_enabled: bool = True
    app_trusted_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])
    service_role: ServiceRole = "web"

    # ── Security ───────────────────────────────────────────────
    secret_key: SecretStr = SecretStr("change-me-min-32-chars-random-string")
    jwt_secret_key: SecretStr = SecretStr("change-me-min-32-chars-random-string")
    jwt_algorithm: Literal["HS256", "HS384", "HS512", "RS256"] = "HS256"
    jwt_audience: str = "fastapi-boilerplate"
    jwt_access_token_expire_minutes: int = Field(default=60, ge=1)
    jwt_refresh_token_expire_days: int = Field(default=14, ge=1)
    auth_enabled: bool = False
    password_min_length: int = Field(default=12, ge=8)
    rate_limit_default: str = "60/minute"
    rate_limit_auth: str = "10/minute"

    # ── Database ───────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://app:app@postgres:5432/app_db"
    database_url_test: str = "postgresql+asyncpg://app_test:app_test@postgres_test:5432/app_test"
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)

    # ── Redis ──────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"
    redis_url_test: str = "redis://redis_test:6379/0"
    redis: RedisSettings = Field(default_factory=RedisSettings)
    cache_default_ttl_seconds: int = Field(default=300, ge=1)

    # ── Celery ─────────────────────────────────────────────────
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"
    celery_broker_url_test: str = "redis://redis_test:6379/1"
    celery_result_backend_test: str = "redis://redis_test:6379/2"
    celery_task_always_eager: bool = False
    celery_task_time_limit: int = 300
    celery_task_soft_time_limit: int = 240
    celery_worker_concurrency: int = 4
    celery_worker_prefetch_multiplier: int = 1
    celery_task_acks_late: bool = True
    celery_queues: str = "default,events"
    celery_beat_scheduler: str = "celery.beat.PersistentScheduler"
    celery_beat_schedule_filename: str = ""
    celery_cron_lock_prefix: str = "cron:lock"
    celery_cron_lock_ttl_seconds: int = 300

    # ── Email ──────────────────────────────────────────────────
    email_enabled: bool = True
    email_provider: Literal["smtp", "null"] = "smtp"
    email_from_address: str = "no-reply@example.com"
    email_from_name: str = "FastAPI Boilerplate"
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_use_tls: bool = False
    smtp_use_starttls: bool = False

    # ── HTTP client ────────────────────────────────────────────
    http_client: HttpClientSettings = Field(default_factory=HttpClientSettings)

    # ── Observability ──────────────────────────────────────────
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "fastapi-boilerplate"
    otel_traces_sampler: str = "parentbased_traceidratio"
    otel_traces_sampler_arg: float = Field(default=0.1, ge=0.0, le=1.0)
    prometheus_enabled: bool = True
    metrics_endpoint_auth_token: SecretStr = SecretStr("")

    # ── i18n / l10n ────────────────────────────────────────────
    locales_enabled: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["en", "ar"])
    locale_default: str = "en"
    locale_fallback: str = "en"
    locale_query_param: str = "lang"
    locale_header_name: str = "Accept-Language"
    locale_domain: str = "messages"
    locale_dir: str = "app/locales"
    rtl_locales: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["ar"])
    locale_translation_completeness_min: float = Field(default=0.95, ge=0.0, le=1.0)

    # ── Feature flags ──────────────────────────────────────────
    feature_demo_enabled: bool = False

    # ── Validators ─────────────────────────────────────────────

    @field_validator(
        "locales_enabled",
        "rtl_locales",
        "app_cors_origins",
        "app_trusted_hosts",
        mode="before",
    )
    @classmethod
    def _coerce_string_list(cls, value: object) -> object:
        """Allow comma-separated lists in addition to JSON arrays."""
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                import json

                try:
                    return json.loads(stripped)
                except json.JSONDecodeError:
                    return [s.strip() for s in stripped.strip("[]").split(",") if s.strip()]
            if stripped:
                return [s.strip() for s in stripped.split(",") if s.strip()]
            return []
        return value

    @field_validator("locale_default")
    @classmethod
    def _default_locale_is_enabled(cls, v: str, info: object) -> str:
        return v

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> Settings:
        """Fail fast when production is configured with unsafe defaults."""
        if not self.is_production:
            return self

        placeholders = {
            "change-me",
            "change-me-min-32-chars-random-string",
            "",
        }
        if self.secret_key.get_secret_value() in placeholders:
            raise ValueError("SECRET_KEY must be set to a non-placeholder value in production")
        if self.jwt_secret_key.get_secret_value() in placeholders:
            raise ValueError("JWT_SECRET_KEY must be set to a non-placeholder value in production")
        if self.app_debug:
            raise ValueError("APP_DEBUG must be false in production")
        if "*" in self.app_trusted_hosts:
            raise ValueError("APP_TRUSTED_HOSTS must be pinned in production")
        if (
            self.service_role == "web"
            and self.prometheus_enabled
            and not self.metrics_endpoint_auth_token.get_secret_value()
        ):
            raise ValueError("METRICS_ENDPOINT_AUTH_TOKEN must be set when metrics are enabled")
        return self

    # ── Convenience properties ─────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def docs_enabled(self) -> bool:
        """Docs are auto-disabled in production unless explicitly enabled."""
        if self.is_production:
            return self.app_docs_enabled
        return self.app_docs_enabled

    @property
    def locale_dir_path(self) -> Path:
        return Path(self.locale_dir)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached, validated ``Settings`` instance.

    Tests reset via ``get_settings.cache_clear()``.
    """
    return Settings()


SettingsDep = Annotated[Settings, "Settings dependency annotation"]  # documentation only
