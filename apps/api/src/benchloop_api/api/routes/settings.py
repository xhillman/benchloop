from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from benchloop_api.api.contracts import (
    ApiRequestModel,
    ApiResponseModel,
    documented_error_statuses,
)
from benchloop_api.auth.dependencies import CurrentUser
from benchloop_api.db.session import get_db_session
from benchloop_api.settings.service import UserSettingsService

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    responses=documented_error_statuses(include_auth=True),
)


def get_user_settings_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> UserSettingsService:
    return UserSettingsService(session)


class UserSettingsResponse(ApiResponseModel):
    default_provider: str | None = None
    default_model: str | None = None
    timezone: str | None = None


class UpdateUserSettingsRequest(ApiRequestModel):
    default_provider: str | None = Field(default=None, max_length=100)
    default_model: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, max_length=100)

    @field_validator("default_provider", "default_model", "timezone", mode="before")
    @classmethod
    def normalize_blank_strings(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@router.get("", response_model=UserSettingsResponse)
async def read_user_settings(
    current_user: CurrentUser,
    settings_service: Annotated[UserSettingsService, Depends(get_user_settings_service)],
) -> UserSettingsResponse:
    settings = settings_service.read(user_id=current_user.id)
    if settings is None:
        return UserSettingsResponse()

    return UserSettingsResponse.model_validate(settings)


@router.put("", response_model=UserSettingsResponse)
async def update_user_settings(
    payload: UpdateUserSettingsRequest,
    current_user: CurrentUser,
    settings_service: Annotated[UserSettingsService, Depends(get_user_settings_service)],
) -> UserSettingsResponse:
    settings = settings_service.update(
        user_id=current_user.id,
        default_provider=payload.default_provider,
        default_model=payload.default_model,
        timezone=payload.timezone,
    )
    return UserSettingsResponse.model_validate(settings)
