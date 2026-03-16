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
from benchloop_api.context_bundles.service import ContextBundleService
from benchloop_api.db.session import get_db_session
from benchloop_api.ownership.service import UserOwnedResourceNotFoundError

router = APIRouter(
    prefix="/experiments/{experiment_id}/context-bundles",
    tags=["context-bundles"],
    responses=documented_error_statuses(include_auth=True, extra_statuses=(404,)),
)


def get_context_bundle_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ContextBundleService:
    return ContextBundleService(session)


class ContextBundleResponse(ApiResponseModel):
    id: UUID
    experiment_id: UUID
    name: str
    content_text: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ContextBundleWriteRequest(ApiRequestModel):
    name: str = Field(min_length=1, max_length=255)
    content_text: str = Field(min_length=1)
    notes: str | None = None

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


def _to_response(context_bundle) -> ContextBundleResponse:
    return ContextBundleResponse.model_validate(context_bundle)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    )


@router.get("", response_model=list[ContextBundleResponse])
async def list_context_bundles(
    experiment_id: UUID,
    current_user: CurrentUser,
    context_bundle_service: Annotated[
        ContextBundleService,
        Depends(get_context_bundle_service),
    ],
) -> list[ContextBundleResponse]:
    try:
        context_bundles = context_bundle_service.list(
            user_id=current_user.id,
            experiment_id=experiment_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return [_to_response(context_bundle) for context_bundle in context_bundles]


@router.post(
    "",
    response_model=ContextBundleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_context_bundle(
    experiment_id: UUID,
    payload: ContextBundleWriteRequest,
    current_user: CurrentUser,
    context_bundle_service: Annotated[
        ContextBundleService,
        Depends(get_context_bundle_service),
    ],
) -> ContextBundleResponse:
    try:
        context_bundle = context_bundle_service.create(
            user_id=current_user.id,
            experiment_id=experiment_id,
            name=payload.name,
            content_text=payload.content_text,
            notes=payload.notes,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return _to_response(context_bundle)


@router.put("/{context_bundle_id}", response_model=ContextBundleResponse)
async def update_context_bundle(
    experiment_id: UUID,
    context_bundle_id: UUID,
    payload: ContextBundleWriteRequest,
    current_user: CurrentUser,
    context_bundle_service: Annotated[
        ContextBundleService,
        Depends(get_context_bundle_service),
    ],
) -> ContextBundleResponse:
    try:
        context_bundle = context_bundle_service.update(
            user_id=current_user.id,
            experiment_id=experiment_id,
            context_bundle_id=context_bundle_id,
            name=payload.name,
            content_text=payload.content_text,
            notes=payload.notes,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return _to_response(context_bundle)


@router.delete("/{context_bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_context_bundle(
    experiment_id: UUID,
    context_bundle_id: UUID,
    current_user: CurrentUser,
    context_bundle_service: Annotated[
        ContextBundleService,
        Depends(get_context_bundle_service),
    ],
) -> Response:
    try:
        context_bundle_service.delete(
            user_id=current_user.id,
            experiment_id=experiment_id,
            context_bundle_id=context_bundle_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
