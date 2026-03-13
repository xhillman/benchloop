from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from benchloop_api.api.router import api_router
from benchloop_api.config import get_settings
from benchloop_api.errors import register_exception_handlers


def create_app(settings_overrides: Mapping[str, Any] | None = None) -> FastAPI:
    settings = get_settings(settings_overrides)
    docs_enabled = settings.environment != "production"

    app = FastAPI(
        title="Benchloop API",
        version="0.1.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
