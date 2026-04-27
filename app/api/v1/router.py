"""Aggregator for v1 routes.

Per-project domain routers register themselves here. The boilerplate ships an
empty router so ``/api/v1/`` is mounted but contains no endpoints by default.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import system

api_router = APIRouter()
api_router.include_router(system.router)


# Per-project routers should be included like:
#
#     from app.api.v1 import users
#     api_router.include_router(users.router)
