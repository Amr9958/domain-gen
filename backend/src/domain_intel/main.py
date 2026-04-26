"""FastAPI application entrypoint."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from domain_intel.api.router import build_api_router
from domain_intel.api.v1.routes import health as health_handler
from domain_intel.core.settings import BackendSettings, get_settings


def create_app(settings: Optional[BackendSettings] = None) -> FastAPI:
    """Create a configured FastAPI application."""

    app_settings = settings or get_settings()
    app = FastAPI(
        title=app_settings.app_name,
        debug=app_settings.debug,
        version="0.1.0",
    )

    if app_settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(build_api_router(app_settings.api_v1_prefix))
    app.add_api_route("/health", health_handler, methods=["GET"], tags=["health"])
    return app


app = create_app()
