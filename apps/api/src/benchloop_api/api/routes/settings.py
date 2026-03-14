from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from benchloop_api.api.contracts import (
    ApiRequestModel,
    ApiResponseModel,
    documented_error_statuses,
)
from benchloop_api.auth.dependencies import CurrentUser
from benchloop_api.db.session import get_db_session
from benchloop_api.ownership.service import UserOwnedResourceNotFoundError
from benchloop_api.settings.encryption import EncryptionService, get_encryption_service
from benchloop_api.settings.models import UserProviderCredential
from benchloop_api.settings.service import (
    ActiveCredentialAlreadyExistsError,
    UserProviderCredentialService,
    UserSettingsService,
    mask_api_key,
)
from benchloop_api.settings.validation import (
    ProviderCredentialValidationError,
    ProviderCredentialValidator,
    UnsupportedCredentialProviderError,
    get_provider_credential_validator,
)

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    responses=documented_error_statuses(
        include_auth=True,
        extra_statuses=(400, 404, 409, 502),
    ),
)


def get_user_settings_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> UserSettingsService:
    return UserSettingsService(session)


def get_user_provider_credential_service(
    session: Annotated[Session, Depends(get_db_session)],
    encryption_service: Annotated[EncryptionService, Depends(get_encryption_service)],
) -> UserProviderCredentialService:
    return UserProviderCredentialService(session, encryption_service)


class UserSettingsResponse(ApiResponseModel):
    default_provider: str | None = None
    default_model: str | None = None
    timezone: str | None = None


class UserProviderCredentialResponse(ApiResponseModel):
    id: UUID
    provider: str
    key_label: str | None = None
    masked_api_key: str
    validation_status: str
    last_validated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


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


class CreateUserProviderCredentialRequest(ApiRequestModel):
    provider: str = Field(min_length=1, max_length=100)
    api_key: str = Field(min_length=1)
    key_label: str | None = Field(default=None, max_length=255)

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("key_label", mode="before")
    @classmethod
    def normalize_blank_key_label(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class ReplaceUserProviderCredentialRequest(ApiRequestModel):
    api_key: str = Field(min_length=1)
    key_label: str | None = Field(default=None, max_length=255)

    @field_validator("key_label", mode="before")
    @classmethod
    def normalize_blank_key_label(cls, value: Any) -> Any:
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


def build_user_provider_credential_response(
    credential: UserProviderCredential,
    encryption_service: EncryptionService,
) -> UserProviderCredentialResponse:
    decrypted_api_key = encryption_service.decrypt(credential.encrypted_api_key)
    return UserProviderCredentialResponse(
        id=credential.id,
        provider=credential.provider,
        key_label=credential.key_label,
        masked_api_key=mask_api_key(decrypted_api_key),
        validation_status=credential.validation_status,
        last_validated_at=credential.last_validated_at,
        created_at=credential.created_at,
        updated_at=credential.updated_at,
    )


@router.get("/credentials", response_model=list[UserProviderCredentialResponse])
async def list_user_provider_credentials(
    current_user: CurrentUser,
    credentials_service: Annotated[
        UserProviderCredentialService,
        Depends(get_user_provider_credential_service),
    ],
    encryption_service: Annotated[EncryptionService, Depends(get_encryption_service)],
) -> list[UserProviderCredentialResponse]:
    credentials = credentials_service.list(user_id=current_user.id)
    return [
        build_user_provider_credential_response(credential, encryption_service)
        for credential in credentials
    ]


@router.post(
    "/credentials",
    response_model=UserProviderCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_provider_credential(
    payload: CreateUserProviderCredentialRequest,
    current_user: CurrentUser,
    credentials_service: Annotated[
        UserProviderCredentialService,
        Depends(get_user_provider_credential_service),
    ],
    encryption_service: Annotated[EncryptionService, Depends(get_encryption_service)],
) -> UserProviderCredentialResponse:
    try:
        credential = credentials_service.create(
            user_id=current_user.id,
            provider=payload.provider,
            api_key=payload.api_key,
            key_label=payload.key_label,
        )
    except ActiveCredentialAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return build_user_provider_credential_response(credential, encryption_service)


@router.put("/credentials/{credential_id}", response_model=UserProviderCredentialResponse)
async def replace_user_provider_credential(
    credential_id: UUID,
    payload: ReplaceUserProviderCredentialRequest,
    current_user: CurrentUser,
    credentials_service: Annotated[
        UserProviderCredentialService,
        Depends(get_user_provider_credential_service),
    ],
    encryption_service: Annotated[EncryptionService, Depends(get_encryption_service)],
) -> UserProviderCredentialResponse:
    try:
        credential = credentials_service.replace(
            user_id=current_user.id,
            credential_id=credential_id,
            api_key=payload.api_key,
            key_label=payload.key_label,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return build_user_provider_credential_response(credential, encryption_service)


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_provider_credential(
    credential_id: UUID,
    current_user: CurrentUser,
    credentials_service: Annotated[
        UserProviderCredentialService,
        Depends(get_user_provider_credential_service),
    ],
) -> Response:
    try:
        credentials_service.delete(
            user_id=current_user.id,
            credential_id=credential_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/credentials/{credential_id}/validate",
    response_model=UserProviderCredentialResponse,
)
async def validate_user_provider_credential(
    credential_id: UUID,
    current_user: CurrentUser,
    credentials_service: Annotated[
        UserProviderCredentialService,
        Depends(get_user_provider_credential_service),
    ],
    credential_validator: Annotated[
        ProviderCredentialValidator,
        Depends(get_provider_credential_validator),
    ],
    encryption_service: Annotated[EncryptionService, Depends(get_encryption_service)],
) -> UserProviderCredentialResponse:
    try:
        credential = await credentials_service.validate(
            user_id=current_user.id,
            credential_id=credential_id,
            validator=credential_validator,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except UnsupportedCredentialProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ProviderCredentialValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return build_user_provider_credential_response(credential, encryption_service)
