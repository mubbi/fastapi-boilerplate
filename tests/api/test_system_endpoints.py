"""Smoke tests for the platform endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import AsyncClient


@pytest.mark.api
async def test_health_returns_200(client: AsyncClient) -> None:
    """``/health`` is liveness only; no DB / Redis touched."""
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["env"] == "test"
    assert body["version"]


@pytest.mark.api
async def test_versioned_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.api
async def test_health_response_contains_request_id(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers.get("X-Request-ID")
    assert response.headers.get("X-API-Version")


@pytest.mark.api
async def test_metrics_endpoint_returns_text(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")


@pytest.mark.api
async def test_metrics_returns_404_when_disabled(
    app: FastAPI, client: AsyncClient, settings
) -> None:
    """A disabled metrics collector must not expose an unauthenticated endpoint."""
    from app.core.container import settings_dependency

    app.dependency_overrides[settings_dependency] = lambda: settings.model_copy(
        update={"prometheus_enabled": False}
    )
    response = await client.get("/metrics")
    assert response.status_code == 404


@pytest.mark.api
async def test_metrics_requires_bearer_token_when_configured(
    app: FastAPI, client: AsyncClient, settings
) -> None:
    """When a token is set, the endpoint rejects missing/incorrect bearers."""
    from pydantic import SecretStr

    from app.core.container import settings_dependency

    tweaked = settings.model_copy(
        update={"metrics_endpoint_auth_token": SecretStr("s3cret-metrics-token")}
    )
    app.dependency_overrides[settings_dependency] = lambda: tweaked

    missing = await client.get("/metrics")
    assert missing.status_code == 403

    wrong = await client.get("/metrics", headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 403

    ok = await client.get("/metrics", headers={"Authorization": "Bearer s3cret-metrics-token"})
    assert ok.status_code == 200


@pytest.mark.api
async def test_locale_via_query_overrides_header(client: AsyncClient) -> None:
    response = await client.get("/health?lang=ar", headers={"Accept-Language": "en"})
    assert response.headers.get("Content-Language") == "ar"


@pytest.mark.api
async def test_locale_falls_back_to_default(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"Accept-Language": "fr"})
    assert response.headers.get("Content-Language") == "en"


@pytest.mark.api
async def test_404_returns_envelope(client: AsyncClient) -> None:
    response = await client.get("/nope")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "HTTP_404"


@pytest.mark.api
async def test_security_headers(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "no-referrer"


@pytest.mark.api
async def test_request_id_is_propagated(client: AsyncClient) -> None:
    custom = "test-corr-id-123"
    response = await client.get("/health", headers={"X-Request-ID": custom})
    assert response.headers.get("X-Request-ID") == custom
