"""DTOs for ``/health`` and ``/ready``."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str
    version: str
    env: str

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class ReadyCheck(BaseModel):
    """Per-dependency readiness check."""

    name: str
    healthy: bool
    duration_ms: float
    error: str | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class ReadyResponse(BaseModel):
    """Aggregate readiness response."""

    ready: bool
    checks: tuple[ReadyCheck, ...]

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
