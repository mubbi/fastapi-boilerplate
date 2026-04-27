"""Versioned mirrors of platform health/readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import SystemServiceDep
from app.schemas.system import HealthResponse, ReadyCheck, ReadyResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Versioned liveness probe")
async def health(svc: SystemServiceDep) -> HealthResponse:
    return HealthResponse(**svc.health())


@router.get("/ready", response_model=ReadyResponse, summary="Versioned readiness probe")
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
