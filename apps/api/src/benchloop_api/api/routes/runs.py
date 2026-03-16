from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import Field, field_validator, model_validator
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
    StoredRunSnapshotInvalidError,
    UnsupportedExecutionWorkflowError,
)
from benchloop_api.execution.snapshots import ConfigSnapshot, ContextSnapshot, InputSnapshot
from benchloop_api.ownership.service import UserOwnedResourceNotFoundError
from benchloop_api.runs.service import (
    RunEvaluationService,
    RunHistoryFilters,
    RunHistoryService,
)
from benchloop_api.settings.encryption import EncryptionService, get_encryption_service

router = APIRouter(
    prefix="/experiments/{experiment_id}/runs",
    tags=["runs"],
    responses=documented_error_statuses(include_auth=True, extra_statuses=(404, 409)),
)

history_router = APIRouter(
    prefix="/runs",
    tags=["runs"],
    responses=documented_error_statuses(include_auth=True),
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


def get_run_history_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> RunHistoryService:
    return RunHistoryService(session)


def get_run_evaluation_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> RunEvaluationService:
    return RunEvaluationService(session)


class RunEvaluationResponse(ApiResponseModel):
    run_id: UUID
    overall_score: int | None = None
    dimension_scores: dict[str, int] = Field(default_factory=dict)
    thumbs_signal: Literal["down", "up"] | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class RunEvaluationWriteRequest(ApiRequestModel):
    overall_score: int | None = Field(default=None, ge=1, le=5)
    dimension_scores: dict[str, int] = Field(default_factory=dict)
    thumbs_signal: Literal["down", "up"] | None = None
    notes: str | None = None

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("dimension_scores")
    @classmethod
    def normalize_dimension_scores(cls, value: dict[str, int]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for raw_dimension, raw_score in value.items():
            dimension = "_".join(raw_dimension.strip().lower().split())
            if not dimension:
                raise ValueError("Dimension score keys must be non-empty strings.")
            if raw_score < 1 or raw_score > 5:
                raise ValueError("Dimension scores must be between 1 and 5.")
            normalized[dimension] = raw_score
        return normalized

    @model_validator(mode="after")
    def ensure_meaningful_payload(self):
        if (
            self.overall_score is None
            and self.thumbs_signal is None
            and self.notes is None
            and not self.dimension_scores
        ):
            raise ValueError("Provide at least one evaluation field or delete the evaluation.")
        return self


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
    evaluation: RunEvaluationResponse | None = None
    created_at: datetime
    updated_at: datetime


class RunDetailResponse(RunResponse):
    experiment_name: str | None = None


class RunHistoryResponse(ApiResponseModel):
    id: UUID
    experiment_id: UUID
    experiment_name: str | None = None
    test_case_id: UUID
    config_id: UUID
    config_name: str
    config_version_label: str
    test_case_input_preview: str
    status: str
    provider: str
    model: str
    workflow_mode: str
    tags: list[str] = Field(default_factory=list)
    latency_ms: int | None = None
    estimated_cost_usd: float | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    evaluation: RunEvaluationResponse | None = None


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


def _to_response(run, *, evaluation=None) -> RunResponse:
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
        evaluation=_to_evaluation_response(evaluation),
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _to_detail_response(entry) -> RunDetailResponse:
    response = _to_response(entry.run, evaluation=entry.evaluation)
    return RunDetailResponse(
        **response.model_dump(),
        experiment_name=entry.experiment_name,
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


def _normalize_query_values(values: list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()

    for raw_value in values:
        value = raw_value.strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)

    return tuple(normalized)


def _to_history_response(run) -> RunHistoryResponse:
    return RunHistoryResponse(
        id=run.id,
        experiment_id=run.experiment_id,
        experiment_name=run.experiment_name,
        test_case_id=run.test_case_id,
        config_id=run.config_id,
        config_name=run.config_name,
        config_version_label=run.config_version_label,
        test_case_input_preview=run.test_case_input_preview,
        status=run.status,
        provider=run.provider,
        model=run.model,
        workflow_mode=run.workflow_mode,
        tags=run.tags,
        latency_ms=run.latency_ms,
        estimated_cost_usd=run.estimated_cost_usd,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        evaluation=_to_evaluation_response(run.evaluation),
    )


def _to_evaluation_response(evaluation) -> RunEvaluationResponse | None:
    if evaluation is None:
        return None
    return RunEvaluationResponse(
        run_id=evaluation.run_id,
        overall_score=evaluation.overall_score,
        dimension_scores=dict(evaluation.dimension_scores),
        thumbs_signal=evaluation.thumbs_signal,
        notes=evaluation.notes,
        created_at=_coerce_utc_datetime(evaluation.created_at),
        updated_at=_coerce_utc_datetime(evaluation.updated_at),
    )


def _coerce_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@history_router.get("", response_model=list[RunHistoryResponse])
async def list_runs(
    current_user: CurrentUser,
    run_history_service: Annotated[RunHistoryService, Depends(get_run_history_service)],
    experiment_id: list[UUID] = Query(default_factory=list),
    config_id: list[UUID] = Query(default_factory=list),
    provider: list[str] = Query(default_factory=list),
    model: list[str] = Query(default_factory=list),
    status_filter: list[str] = Query(default_factory=list, alias="status"),
    tag: list[str] = Query(default_factory=list),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: Literal["created_at", "estimated_cost_usd", "finished_at", "latency_ms"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> list[RunHistoryResponse]:
    runs = run_history_service.list(
        user_id=current_user.id,
        filters=RunHistoryFilters(
            experiment_ids=tuple(experiment_id),
            config_ids=tuple(config_id),
            providers=_normalize_query_values(provider),
            models=_normalize_query_values(model),
            statuses=_normalize_query_values(status_filter),
            tags=_normalize_query_values(tag),
            created_from=created_from,
            created_to=created_to,
            sort_by=sort_by,
            sort_order=sort_order,
        ),
    )
    return [_to_history_response(run) for run in runs]


@history_router.get(
    "/{run_id}",
    response_model=RunDetailResponse,
    responses=documented_error_statuses(include_auth=True, extra_statuses=(404,)),
)
async def get_run(
    run_id: UUID,
    current_user: CurrentUser,
    run_history_service: Annotated[RunHistoryService, Depends(get_run_history_service)],
) -> RunDetailResponse:
    try:
        run = run_history_service.get(
            user_id=current_user.id,
            run_id=run_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return _to_detail_response(run)


@history_router.get(
    "/{run_id}/evaluation",
    response_model=RunEvaluationResponse,
    responses=documented_error_statuses(include_auth=True, extra_statuses=(404,)),
)
async def get_run_evaluation(
    run_id: UUID,
    current_user: CurrentUser,
    run_evaluation_service: Annotated[RunEvaluationService, Depends(get_run_evaluation_service)],
) -> RunEvaluationResponse:
    try:
        evaluation = run_evaluation_service.get(
            user_id=current_user.id,
            run_id=run_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    if evaluation is None:
        raise _not_found("Run evaluation was not found.")

    return _to_evaluation_response(evaluation)


@history_router.put(
    "/{run_id}/evaluation",
    response_model=RunEvaluationResponse,
    responses=documented_error_statuses(include_auth=True, extra_statuses=(404,)),
)
async def put_run_evaluation(
    run_id: UUID,
    payload: RunEvaluationWriteRequest,
    current_user: CurrentUser,
    run_evaluation_service: Annotated[RunEvaluationService, Depends(get_run_evaluation_service)],
) -> RunEvaluationResponse:
    try:
        evaluation = run_evaluation_service.upsert(
            user_id=current_user.id,
            run_id=run_id,
            overall_score=payload.overall_score,
            dimension_scores=payload.dimension_scores,
            thumbs_signal=payload.thumbs_signal,
            notes=payload.notes,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return _to_evaluation_response(evaluation)


@history_router.delete(
    "/{run_id}/evaluation",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=documented_error_statuses(include_auth=True, extra_statuses=(404,)),
)
async def delete_run_evaluation(
    run_id: UUID,
    current_user: CurrentUser,
    run_evaluation_service: Annotated[RunEvaluationService, Depends(get_run_evaluation_service)],
) -> Response:
    try:
        run_evaluation_service.delete(
            user_id=current_user.id,
            run_id=run_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@history_router.post(
    "/{run_id}/rerun",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    responses=documented_error_statuses(include_auth=True, extra_statuses=(404, 409)),
)
async def rerun_from_snapshot(
    run_id: UUID,
    current_user: CurrentUser,
    run_launch_service: Annotated[RunLaunchService, Depends(get_run_launch_service)],
) -> RunResponse:
    try:
        run = await run_launch_service.rerun_from_snapshot(
            user_id=current_user.id,
            run_id=run_id,
        )
    except UserOwnedResourceNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except (StoredRunSnapshotInvalidError, UnsupportedExecutionWorkflowError) as exc:
        raise _conflict(str(exc)) from exc

    return _to_response(run)


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
