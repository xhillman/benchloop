from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from benchloop_api.api.contracts import (
    ApiRequestModel,
    ApiResponseModel,
    documented_error_statuses,
)
from benchloop_api.auth.dependencies import CurrentUser
from benchloop_api.db.session import get_db_session
from benchloop_api.execution.adapters import (
    ProviderAdapterRegistry,
    get_provider_adapter_registry,
)
from benchloop_api.execution.rendering import PromptRenderingError
from benchloop_api.execution.service import (
    RunLaunchService,
    SingleShotExecutionService,
    UnsupportedExecutionWorkflowError,
)
from benchloop_api.execution.snapshots import ConfigSnapshot, ContextSnapshot, InputSnapshot
from benchloop_api.ownership.service import UserOwnedResourceNotFoundError
from benchloop_api.settings.encryption import EncryptionService, get_encryption_service

router = APIRouter(
    prefix="/experiments/{experiment_id}/runs",
    tags=["runs"],
    responses=documented_error_statuses(include_auth=True, extra_statuses=(404, 409)),
)


def get_run_launch_service(
    session: Annotated[Session, Depends(get_db_session)],
    encryption_service: Annotated[EncryptionService, Depends(get_encryption_service)],
    provider_registry: Annotated[ProviderAdapterRegistry, Depends(get_provider_adapter_registry)],
) -> RunLaunchService:
    execution_service = SingleShotExecutionService(
        session=session,
        encryption_service=encryption_service,
        provider_registry=provider_registry,
    )
    return RunLaunchService(
        session=session,
        execution_service=execution_service,
    )


class RunResponse(ApiResponseModel):
    id: UUID
    experiment_id: UUID
    test_case_id: UUID
    config_id: UUID
    credential_id: UUID | None = None
    status: str
    provider: str
    model: str
    workflow_mode: str
    config_snapshot: ConfigSnapshot
    input_snapshot: InputSnapshot
    context_snapshot: ContextSnapshot | None = None
    output_text: str | None = None
    error_message: str | None = None
    usage_input_tokens: int | None = None
    usage_output_tokens: int | None = None
    usage_total_tokens: int | None = None
    latency_ms: int | None = None
    estimated_cost_usd: float | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class LaunchRunRequest(ApiRequestModel):
    test_case_id: UUID
    config_id: UUID


class LaunchBatchRunsRequest(ApiRequestModel):
    test_case_id: UUID
    config_ids: list[UUID] = Field(min_length=1)

    @field_validator("config_ids")
    @classmethod
    def ensure_unique_ids(cls, value: list[UUID]) -> list[UUID]:
        unique_ids = list(dict.fromkeys(value))
        if len(unique_ids) != len(value):
            raise ValueError("Config ids must be unique.")
        return unique_ids


def _to_response(run) -> RunResponse:
    return RunResponse(
        id=run.id,
        experiment_id=run.experiment_id,
        test_case_id=run.test_case_id,
        config_id=run.config_id,
        credential_id=run.credential_id,
        status=run.status,
        provider=run.provider,
        model=run.model,
        workflow_mode=run.workflow_mode,
        config_snapshot=ConfigSnapshot.model_validate(run.config_snapshot_json),
        input_snapshot=InputSnapshot.model_validate(run.input_snapshot_json),
        context_snapshot=(
            ContextSnapshot.model_validate(run.context_snapshot_json)
            if run.context_snapshot_json is not None
            else None
        ),
        output_text=run.output_text,
        error_message=run.error_message,
        usage_input_tokens=run.usage_input_tokens,
        usage_output_tokens=run.usage_output_tokens,
        usage_total_tokens=run.usage_total_tokens,
        latency_ms=run.latency_ms,
        estimated_cost_usd=run.estimated_cost_usd,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _not_found(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    )


def _conflict(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
    )


@router.post(
    "",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def launch_run(
    experiment_id: UUID,
    payload: LaunchRunRequest,
    current_user: CurrentUser,
    run_launch_service: Annotated[RunLaunchService, Depends(get_run_launch_service)],
) -> RunResponse:
    try:
        run = await run_launch_service.launch_single(
            user_id=current_user.id,
            experiment_id=experiment_id,
            test_case_id=payload.test_case_id,
            config_id=payload.config_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except (PromptRenderingError, UnsupportedExecutionWorkflowError) as exc:
        raise _conflict(str(exc)) from exc

    return _to_response(run)


@router.post(
    "/batch",
    response_model=list[RunResponse],
    status_code=status.HTTP_201_CREATED,
)
async def launch_batch_runs(
    experiment_id: UUID,
    payload: LaunchBatchRunsRequest,
    current_user: CurrentUser,
    run_launch_service: Annotated[RunLaunchService, Depends(get_run_launch_service)],
) -> list[RunResponse]:
    try:
        runs = await run_launch_service.launch_batch(
            user_id=current_user.id,
            experiment_id=experiment_id,
            test_case_id=payload.test_case_id,
            config_ids=payload.config_ids,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except (PromptRenderingError, UnsupportedExecutionWorkflowError) as exc:
        raise _conflict(str(exc)) from exc

    return [_to_response(run) for run in runs]
