"""HTTP integration: Protocol + ``httpx.AsyncClient`` adapter."""

from __future__ import annotations

from app.core.config import Settings
from app.integrations.http.base import HttpClient
from app.integrations.http.httpx_client import HttpxClient


async def build_http_client(settings: Settings) -> HttpClient:
    """Construct the shared ``httpx.AsyncClient`` once per process."""
    return await HttpxClient.connect(settings=settings)


__all__ = ["HttpClient", "HttpxClient", "build_http_client"]
