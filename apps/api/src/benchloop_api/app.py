from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from benchloop_api.api.contracts import API_V1_PREFIX, install_openapi_contract
from benchloop_api.api.router import api_router
from benchloop_api.auth.service import ClerkJwtVerifier
from benchloop_api.config import get_settings
from benchloop_api.db.session import create_database_engine, create_session_factory
from benchloop_api.errors import register_exception_handlers
from benchloop_api.execution.adapters import create_provider_adapter_registry
from benchloop_api.settings.encryption import create_encryption_service
from benchloop_api.settings.validation import create_provider_credential_validator


def create_app(settings_overrides: Mapping[str, Any] | None = None) -> FastAPI:
    settings = get_settings(settings_overrides)
    docs_enabled = settings.environment != "production"
    database_engine = create_database_engine(settings)
    session_factory = create_session_factory(database_engine)

    app = FastAPI(
        title="Benchloop API",
        version="0.1.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.state.settings = settings
    app.state.db_engine = database_engine
    app.state.session_factory = session_factory
    app.state.auth_verifier = ClerkJwtVerifier(settings)
    app.state.encryption_service = create_encryption_service(settings)
    app.state.provider_adapter_registry = create_provider_adapter_registry()
    app.state.provider_credential_validator = create_provider_credential_validator()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_openapi_contract(app)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=API_V1_PREFIX)
    app.add_event_handler("shutdown", database_engine.dispose)

    return app


app = create_app()
