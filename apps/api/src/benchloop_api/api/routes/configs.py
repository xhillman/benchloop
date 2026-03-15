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
from benchloop_api.configs.service import ConfigService, normalize_workflow_mode
from benchloop_api.db.session import get_db_session
from benchloop_api.ownership.service import UserOwnedResourceNotFoundError
from benchloop_api.experiments.service import normalize_tags

router = APIRouter(
    prefix="/experiments/{experiment_id}/configs",
    tags=["configs"],
    responses=documented_error_statuses(include_auth=True, extra_statuses=(404,)),
)


def get_config_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ConfigService:
    return ConfigService(session)


class ConfigResponse(ApiResponseModel):
    id: UUID
    experiment_id: UUID
    name: str
    version_label: str
    description: str | None = None
    provider: str
    model: str
    workflow_mode: str
    system_prompt: str | None = None
    user_prompt_template: str
    temperature: float
    max_output_tokens: int
    top_p: float | None = None
    context_bundle_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)
    is_baseline: bool
    created_at: datetime
    updated_at: datetime


class ConfigWriteRequest(ApiRequestModel):
    name: str = Field(min_length=1, max_length=255)
    version_label: str = Field(min_length=1, max_length=100)
    description: str | None = None
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=255)
    workflow_mode: str = Field(min_length=1, max_length=50)
    system_prompt: str | None = None
    user_prompt_template: str = Field(min_length=1)
    temperature: float = Field(ge=0, le=2)
    max_output_tokens: int = Field(ge=1, le=32768)
    top_p: float | None = Field(default=None, ge=0, le=1)
    context_bundle_id: UUID | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    is_baseline: bool = False

    @field_validator("description", "system_prompt", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("workflow_mode", mode="before")
    @classmethod
    def validate_workflow_mode(cls, value: Any) -> Any:
        if isinstance(value, str):
            return normalize_workflow_mode(value)
        return value

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_payload_tags(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        return normalize_tags([str(tag) for tag in value])


def _to_response(config) -> ConfigResponse:
    return ConfigResponse.model_validate(config)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    )


@router.get("", response_model=list[ConfigResponse])
async def list_configs(
    experiment_id: UUID,
    current_user: CurrentUser,
    config_service: Annotated[ConfigService, Depends(get_config_service)],
) -> list[ConfigResponse]:
    try:
        configs = config_service.list(
            user_id=current_user.id,
            experiment_id=experiment_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return [_to_response(config) for config in configs]


@router.post(
    "",
    response_model=ConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_config(
    experiment_id: UUID,
    payload: ConfigWriteRequest,
    current_user: CurrentUser,
    config_service: Annotated[ConfigService, Depends(get_config_service)],
) -> ConfigResponse:
    try:
        config = config_service.create(
            user_id=current_user.id,
            experiment_id=experiment_id,
            name=payload.name,
            version_label=payload.version_label,
            description=payload.description,
            provider=payload.provider,
            model=payload.model,
            workflow_mode=payload.workflow_mode,
            system_prompt=payload.system_prompt,
            user_prompt_template=payload.user_prompt_template,
            temperature=payload.temperature,
            max_output_tokens=payload.max_output_tokens,
            top_p=payload.top_p,
            context_bundle_id=payload.context_bundle_id,
            tags=payload.tags,
            is_baseline=payload.is_baseline,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return _to_response(config)


@router.put("/{config_id}", response_model=ConfigResponse)
async def update_config(
    experiment_id: UUID,
    config_id: UUID,
    payload: ConfigWriteRequest,
    current_user: CurrentUser,
    config_service: Annotated[ConfigService, Depends(get_config_service)],
) -> ConfigResponse:
    try:
        config = config_service.update(
            user_id=current_user.id,
            experiment_id=experiment_id,
            config_id=config_id,
            name=payload.name,
            version_label=payload.version_label,
            description=payload.description,
            provider=payload.provider,
            model=payload.model,
            workflow_mode=payload.workflow_mode,
            system_prompt=payload.system_prompt,
            user_prompt_template=payload.user_prompt_template,
            temperature=payload.temperature,
            max_output_tokens=payload.max_output_tokens,
            top_p=payload.top_p,
            context_bundle_id=payload.context_bundle_id,
            tags=payload.tags,
            is_baseline=payload.is_baseline,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return _to_response(config)


@router.post(
    "/{config_id}/clone",
    response_model=ConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clone_config(
    experiment_id: UUID,
    config_id: UUID,
    current_user: CurrentUser,
    config_service: Annotated[ConfigService, Depends(get_config_service)],
) -> ConfigResponse:
    try:
        config = config_service.clone(
            user_id=current_user.id,
            experiment_id=experiment_id,
            config_id=config_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return _to_response(config)


@router.post("/{config_id}/baseline", response_model=ConfigResponse)
async def mark_config_baseline(
    experiment_id: UUID,
    config_id: UUID,
    current_user: CurrentUser,
    config_service: Annotated[ConfigService, Depends(get_config_service)],
) -> ConfigResponse:
    try:
        config = config_service.mark_baseline(
            user_id=current_user.id,
            experiment_id=experiment_id,
            config_id=config_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return _to_response(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    experiment_id: UUID,
    config_id: UUID,
    current_user: CurrentUser,
    config_service: Annotated[ConfigService, Depends(get_config_service)],
) -> Response:
    try:
        config_service.delete(
            user_id=current_user.id,
            experiment_id=experiment_id,
            config_id=config_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
