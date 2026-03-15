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
from benchloop_api.test_cases.service import TestCaseService

router = APIRouter(
    prefix="/experiments/{experiment_id}/test-cases",
    tags=["test-cases"],
    responses=documented_error_statuses(include_auth=True, extra_statuses=(404,)),
)


def get_test_case_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> TestCaseService:
    return TestCaseService(session)


class TestCaseResponse(ApiResponseModel):
    id: UUID
    experiment_id: UUID
    input_text: str
    expected_output_text: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TestCaseWriteRequest(ApiRequestModel):
    input_text: str = Field(min_length=1)
    expected_output_text: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("expected_output_text", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


def _to_response(test_case) -> TestCaseResponse:
    return TestCaseResponse.model_validate(test_case)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    )


@router.get("", response_model=list[TestCaseResponse])
async def list_test_cases(
    experiment_id: UUID,
    current_user: CurrentUser,
    test_case_service: Annotated[TestCaseService, Depends(get_test_case_service)],
) -> list[TestCaseResponse]:
    try:
        test_cases = test_case_service.list(
            user_id=current_user.id,
            experiment_id=experiment_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return [_to_response(test_case) for test_case in test_cases]


@router.post(
    "",
    response_model=TestCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_case(
    experiment_id: UUID,
    payload: TestCaseWriteRequest,
    current_user: CurrentUser,
    test_case_service: Annotated[TestCaseService, Depends(get_test_case_service)],
) -> TestCaseResponse:
    try:
        test_case = test_case_service.create(
            user_id=current_user.id,
            experiment_id=experiment_id,
            input_text=payload.input_text,
            expected_output_text=payload.expected_output_text,
            notes=payload.notes,
            tags=payload.tags,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return _to_response(test_case)


@router.put("/{test_case_id}", response_model=TestCaseResponse)
async def update_test_case(
    experiment_id: UUID,
    test_case_id: UUID,
    payload: TestCaseWriteRequest,
    current_user: CurrentUser,
    test_case_service: Annotated[TestCaseService, Depends(get_test_case_service)],
) -> TestCaseResponse:
    try:
        test_case = test_case_service.update(
            user_id=current_user.id,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
            input_text=payload.input_text,
            expected_output_text=payload.expected_output_text,
            notes=payload.notes,
            tags=payload.tags,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return _to_response(test_case)


@router.post(
    "/{test_case_id}/duplicate",
    response_model=TestCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_test_case(
    experiment_id: UUID,
    test_case_id: UUID,
    current_user: CurrentUser,
    test_case_service: Annotated[TestCaseService, Depends(get_test_case_service)],
) -> TestCaseResponse:
    try:
        test_case = test_case_service.duplicate(
            user_id=current_user.id,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return _to_response(test_case)


@router.delete("/{test_case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_case(
    experiment_id: UUID,
    test_case_id: UUID,
    current_user: CurrentUser,
    test_case_service: Annotated[TestCaseService, Depends(get_test_case_service)],
) -> Response:
    try:
        test_case_service.delete(
            user_id=current_user.id,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
