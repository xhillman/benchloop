from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from benchloop_api.api.contracts import (
    ApiRequestModel,
    ApiResponseModel,
    documented_error_statuses,
)
from benchloop_api.auth.dependencies import CurrentUser
from benchloop_api.db.session import get_db_session
from benchloop_api.experiments.service import ExperimentService, normalize_tags
from benchloop_api.ownership.service import UserOwnedResourceNotFoundError

router = APIRouter(
    prefix="/experiments",
    tags=["experiments"],
    responses=documented_error_statuses(include_auth=True, extra_statuses=(404,)),
)


def get_experiment_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ExperimentService:
    return ExperimentService(session)


class ExperimentResponse(ApiResponseModel):
    id: UUID
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class CreateExperimentRequest(ApiRequestModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("description", mode="before")
    @classmethod
    def normalize_blank_description(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_payload_tags(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        return normalize_tags([str(tag) for tag in value])


class UpdateExperimentRequest(CreateExperimentRequest):
    is_archived: bool = False


def _to_response(experiment) -> ExperimentResponse:
    return ExperimentResponse.model_validate(experiment)


@router.get("", response_model=list[ExperimentResponse])
async def list_experiments(
    current_user: CurrentUser,
    experiments_service: Annotated[ExperimentService, Depends(get_experiment_service)],
    search: str | None = Query(default=None, max_length=255),
    tag: list[str] = Query(default_factory=list),
    include_archived: bool = False,
) -> list[ExperimentResponse]:
    experiments = experiments_service.list(
        user_id=current_user.id,
        search=search,
        tags=tag,
        include_archived=include_archived,
    )
    return [_to_response(experiment) for experiment in experiments]


@router.post(
    "",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_experiment(
    payload: CreateExperimentRequest,
    current_user: CurrentUser,
    experiments_service: Annotated[ExperimentService, Depends(get_experiment_service)],
) -> ExperimentResponse:
    experiment = experiments_service.create(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        tags=payload.tags,
    )
    return _to_response(experiment)


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def read_experiment(
    experiment_id: UUID,
    current_user: CurrentUser,
    experiments_service: Annotated[ExperimentService, Depends(get_experiment_service)],
) -> ExperimentResponse:
    try:
        experiment = experiments_service.read(
            user_id=current_user.id,
            experiment_id=experiment_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return _to_response(experiment)


@router.put("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: UUID,
    payload: UpdateExperimentRequest,
    current_user: CurrentUser,
    experiments_service: Annotated[ExperimentService, Depends(get_experiment_service)],
) -> ExperimentResponse:
    try:
        experiment = experiments_service.update(
            user_id=current_user.id,
            experiment_id=experiment_id,
            name=payload.name,
            description=payload.description,
            tags=payload.tags,
            is_archived=payload.is_archived,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return _to_response(experiment)


@router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experiment(
    experiment_id: UUID,
    current_user: CurrentUser,
    experiments_service: Annotated[ExperimentService, Depends(get_experiment_service)],
) -> Response:
    try:
        experiments_service.delete(
            user_id=current_user.id,
            experiment_id=experiment_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
