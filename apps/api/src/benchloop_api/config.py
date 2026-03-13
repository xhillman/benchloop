from collections.abc import Mapping
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[2]
ENV_FILE_PATH = API_DIR / ".env"


class AppSettings(BaseSettings):
    environment: Literal["local", "development", "test", "production"] = Field(
        default="local",
        validation_alias=AliasChoices("BENCHLOOP_ENV", "environment"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("BENCHLOOP_LOG_LEVEL", "log_level"),
    )
    host: str = Field(
        default="0.0.0.0",
        validation_alias=AliasChoices("BENCHLOOP_HOST", "host"),
    )
    port: int = Field(
        default=8000,
        validation_alias=AliasChoices("BENCHLOOP_PORT", "port"),
    )
    database_url: str = Field(
        default="postgresql+psycopg://benchloop:benchloop@localhost:5432/benchloop",
        validation_alias=AliasChoices("BENCHLOOP_DATABASE_URL", "database_url"),
    )
    db_echo: bool = Field(
        default=False,
        validation_alias=AliasChoices("BENCHLOOP_DB_ECHO", "db_echo"),
    )
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias=AliasChoices(
            "BENCHLOOP_CORS_ALLOWED_ORIGINS",
            "cors_allowed_origins",
        ),
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        enable_decoding=False,
        extra="ignore",
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.startswith("["):
                parsed = json.loads(normalized)
                if isinstance(parsed, list):
                    return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in normalized.split(",") if origin.strip()]
        if isinstance(value, list):
            return value
        return ["http://localhost:3000"]


@lru_cache(maxsize=1)
def _get_base_settings() -> AppSettings:
    return AppSettings()


def get_settings(overrides: Mapping[str, Any] | None = None) -> AppSettings:
    if not overrides:
        return _get_base_settings()

    settings_data = _get_base_settings().model_dump()
    settings_data.update(overrides)
    return AppSettings.model_validate(settings_data)


def get_app_settings(app: FastAPI) -> AppSettings:
    return app.state.settings
