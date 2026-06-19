"""Platform endpoints — ``/health``, ``/ready``, ``/metrics``.

Mounted on the bare app (no version prefix) so external probes don't need to
chase API versions.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Request, Response, status

from app.api.deps import SettingsDep, SystemServiceDep
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.metrics import render_metrics
from app.schemas.system import HealthResponse, ReadyCheck, ReadyResponse

router = APIRouter(tags=["system"], include_in_schema=True)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns 200 if the process is up. Does NOT touch dependencies.",
)
async def health(svc: SystemServiceDep) -> HealthResponse:
    body = svc.health()
    return HealthResponse(**body)


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
    description="Aggregates DB + cache health. Returns 503 when not ready.",
    responses={503: {"description": "One or more dependencies are unhealthy"}},
)
async def ready(svc: SystemServiceDep, response: Response) -> ReadyResponse:
    report = await svc.readiness()
    payload = ReadyResponse(
        ready=report.ready,
        checks=tuple(
            ReadyCheck(
                name=check.name,
                healthy=check.healthy,
                duration_ms=check.duration_ms,
                error=check.error,
            )
            for check in report.checks
        ),
    )
    if not report.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Plain-text Prometheus exposition.",
    include_in_schema=False,
)
async def metrics(request: Request, settings: SettingsDep) -> Response:
    # When metrics collection is disabled the endpoint must not exist — returning
    # 404 avoids leaking process internals through an unauthenticated route.
    if not settings.prometheus_enabled:
        raise NotFoundError()
    expected = settings.metrics_endpoint_auth_token.get_secret_value()
    if expected:
        presented = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # Constant-time comparison to avoid a token-recovery timing oracle (CWE-208).
        if not hmac.compare_digest(presented, expected):
            raise ForbiddenError(message="errors.metrics.forbidden")
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)
