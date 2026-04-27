"""OpenTelemetry tracing setup — vendor-agnostic via OTLP/HTTP.

Disabled when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is empty so local dev stays quiet.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

_initialized = False


def configure_tracing(settings: Settings) -> None:
    """Set up OTel tracer provider, OTLP exporter, and auto-instrumentation.

    Idempotent — repeated calls within the same process are no-ops after the first.
    """
    global _initialized
    if _initialized:
        return

    if not settings.otel_exporter_otlp_endpoint:
        log.info("tracing.disabled", reason="OTEL_EXPORTER_OTLP_ENDPOINT not set")
        _initialized = True
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import (
            ParentBased,
            TraceIdRatioBased,
        )
    except ImportError:
        log.warning("tracing.import_failed")
        _initialized = True
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.app_env,
        }
    )
    sampler = ParentBased(TraceIdRatioBased(settings.otel_traces_sampler_arg))
    provider = TracerProvider(resource=resource, sampler=sampler)

    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    log.info("tracing.configured", endpoint=settings.otel_exporter_otlp_endpoint)
    _initialized = True


def instrument_app(app: object) -> None:
    """Attach FastAPI / SQLAlchemy / Redis / httpx auto-instrumentation."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,  # type: ignore[arg-type]
            excluded_urls="/health,/ready,/metrics",
        )
    except Exception:
        log.debug("tracing.fastapi_instrument_failed")
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception:
        log.debug("tracing.httpx_instrument_failed")
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
    except Exception:
        log.debug("tracing.redis_instrument_failed")
