"""Top-level API router assembly."""

from __future__ import annotations

from fastapi import APIRouter

from domain_intel.api.v1.routes import router as v1_router
from domain_intel.core.settings import get_settings


def build_api_router(api_v1_prefix: str) -> APIRouter:
    """Build the top-level API router with a configurable v1 prefix."""

    router = APIRouter()
    router.include_router(v1_router, prefix=api_v1_prefix)
    return router


api_router = build_api_router(get_settings().api_v1_prefix)
