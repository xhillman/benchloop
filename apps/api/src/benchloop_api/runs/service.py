from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.configs.models import Config
from benchloop_api.execution.adapters import ProviderExecutionResult
from benchloop_api.execution.snapshots import RunSnapshotBundle
from benchloop_api.ownership.service import UserOwnedResourceNotFoundError
from benchloop_api.experiments.repository import ExperimentRepository
from benchloop_api.runs.models import Run, RunEvaluation
from benchloop_api.runs.repository import RunEvaluationRepository, RunRepository
from benchloop_api.test_cases.models import TestCase

RUN_STATUS_PENDING = "pending"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"

RunHistorySortField = Literal["created_at", "estimated_cost_usd", "finished_at", "latency_ms"]
RunHistorySortOrder = Literal["asc", "desc"]


@dataclass(frozen=True)
class RunHistoryFilters:
    experiment_ids: tuple[UUID, ...] = ()
    config_ids: tuple[UUID, ...] = ()
    providers: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    created_from: datetime | None = None
    created_to: datetime | None = None
    sort_by: RunHistorySortField = "created_at"
    sort_order: RunHistorySortOrder = "desc"


@dataclass(frozen=True)
class RunHistoryEntry:
    id: UUID
    experiment_id: UUID
    experiment_name: str | None
    test_case_id: UUID
    config_id: UUID
    config_name: str
    config_version_label: str
    test_case_input_preview: str
    status: str
    provider: str
    model: str
    workflow_mode: str
    tags: list[str]
    latency_ms: int | None
    estimated_cost_usd: float | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    evaluation: RunEvaluation | None = None


@dataclass(frozen=True)
class RunDetailEntry:
    run: Run
    experiment_name: str | None
    evaluation: RunEvaluation | None = None


class RunService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = RunRepository(session)

    def create_pending(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        config: Config,
        test_case: TestCase,
        snapshot_bundle: RunSnapshotBundle,
    ) -> Run:
        return self.create_pending_from_snapshot(
            user_id=user_id,
            experiment_id=experiment_id,
            config_id=config.id,
            test_case_id=test_case.id,
            snapshot_bundle=snapshot_bundle,
        )

    def create_pending_from_snapshot(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        config_id: UUID,
        test_case_id: UUID,
        snapshot_bundle: RunSnapshotBundle,
    ) -> Run:
        run = self._repository.add(
            Run(
                user_id=user_id,
                experiment_id=experiment_id,
                test_case_id=test_case_id,
                config_id=config_id,
                credential_id=None,
                status=RUN_STATUS_PENDING,
                provider=snapshot_bundle.config_snapshot.provider,
                model=snapshot_bundle.config_snapshot.model,
                workflow_mode=snapshot_bundle.config_snapshot.workflow_mode,
                config_snapshot_json=snapshot_bundle.config_snapshot.model_dump(mode="json"),
                input_snapshot_json=snapshot_bundle.input_snapshot.model_dump(mode="json"),
                context_snapshot_json=(
                    snapshot_bundle.context_snapshot.model_dump(mode="json")
                    if snapshot_bundle.context_snapshot is not None
                    else None
                ),
            )
        )
        self._session.flush()
        return run

    def mark_running(self, *, run: Run, credential_id: UUID) -> Run:
        run.status = RUN_STATUS_RUNNING
        run.credential_id = credential_id
        run.started_at = datetime.now(tz=UTC)
        self._session.flush()
        return run

    def mark_completed(
        self,
        *,
        run: Run,
        result: ProviderExecutionResult,
    ) -> Run:
        run.status = RUN_STATUS_COMPLETED
        run.provider = result.provider
        run.model = result.model
        run.output_text = result.output_text
        run.error_message = None
        run.usage_input_tokens = result.usage.input_tokens
        run.usage_output_tokens = result.usage.output_tokens
        run.usage_total_tokens = result.usage.total_tokens
        run.latency_ms = result.latency_ms
        run.estimated_cost_usd = result.estimated_cost_usd
        run.finished_at = datetime.now(tz=UTC)
        self._session.flush()
        return run

    def mark_failed(self, *, run: Run, error_message: str) -> Run:
        run.status = RUN_STATUS_FAILED
        run.output_text = None
        run.error_message = error_message
        run.usage_input_tokens = None
        run.usage_output_tokens = None
        run.usage_total_tokens = None
        run.latency_ms = None
        run.estimated_cost_usd = None
        run.finished_at = datetime.now(tz=UTC)
        self._session.flush()
        return run


class RunHistoryService:
    def __init__(self, session: Session) -> None:
        self._repository = RunRepository(session)
        self._evaluation_repository = RunEvaluationRepository(session)
        self._experiment_repository = ExperimentRepository(session)

    def list(
        self,
        *,
        user_id: UUID,
        filters: RunHistoryFilters,
    ) -> Sequence[RunHistoryEntry]:
        runs = self._repository.list_for_user(user_id=user_id)
        filtered_runs = [run for run in runs if self._matches_filters(run=run, filters=filters)]
        sorted_runs = self._sort_runs(runs=filtered_runs, filters=filters)
        experiment_names = {
            experiment.id: experiment.name
            for experiment in self._experiment_repository.list_for_user(
                user_id=user_id,
                include_archived=True,
            )
        }
        evaluations_by_run_id = self._evaluation_repository.list_for_runs(
            user_id=user_id,
            run_ids=[run.id for run in sorted_runs],
        )
        return [
            self._to_history_entry(
                run=run,
                experiment_name=experiment_names.get(run.experiment_id),
                evaluation=evaluations_by_run_id.get(run.id),
            )
            for run in sorted_runs
        ]

    def get(self, *, user_id: UUID, run_id: UUID) -> RunDetailEntry:
        run = self._repository.get_owned(user_id=user_id, resource_id=run_id)
        if run is None:
            raise UserOwnedResourceNotFoundError(
                resource_name="Run",
                resource_id=run_id,
                user_id=user_id,
            )

        experiment = self._experiment_repository.get_owned(
            user_id=user_id,
            resource_id=run.experiment_id,
        )
        return RunDetailEntry(
            run=run,
            experiment_name=experiment.name if experiment is not None else None,
            evaluation=self._evaluation_repository.get_for_run(
                user_id=user_id,
                run_id=run.id,
            ),
        )

    def _matches_filters(self, *, run: Run, filters: RunHistoryFilters) -> bool:
        created_at = _coerce_utc_datetime(run.created_at)
        if filters.experiment_ids and run.experiment_id not in filters.experiment_ids:
            return False
        if filters.config_ids and run.config_id not in filters.config_ids:
            return False
        if filters.providers and run.provider.lower() not in filters.providers:
            return False
        if filters.models and run.model.lower() not in filters.models:
            return False
        if filters.statuses and run.status.lower() not in filters.statuses:
            return False
        if filters.created_from is not None and created_at < _coerce_utc_datetime(filters.created_from):
            return False
        if filters.created_to is not None and created_at > _coerce_utc_datetime(filters.created_to):
            return False
        if filters.tags and not self._matches_tags(run=run, tags=filters.tags):
            return False
        return True

    @staticmethod
    def _matches_tags(*, run: Run, tags: Sequence[str]) -> bool:
        snapshot_tags = {
            tag.strip().lower()
            for tag in [
                *run.config_snapshot_json.get("tags", []),
                *run.input_snapshot_json.get("tags", []),
            ]
            if isinstance(tag, str) and tag.strip()
        }
        return any(tag in snapshot_tags for tag in tags)

    def _sort_runs(self, *, runs: Sequence[Run], filters: RunHistoryFilters) -> Sequence[Run]:
        sort_key_getter = self._get_sort_value
        non_null_runs = [
            run for run in runs if sort_key_getter(run=run, sort_by=filters.sort_by) is not None
        ]
        null_runs = [run for run in runs if sort_key_getter(run=run, sort_by=filters.sort_by) is None]

        non_null_runs.sort(
            key=lambda run: (
                sort_key_getter(run=run, sort_by=filters.sort_by),
                str(run.id),
            ),
            reverse=filters.sort_order == "desc",
        )
        return [*non_null_runs, *null_runs]

    @staticmethod
    def _get_sort_value(*, run: Run, sort_by: RunHistorySortField):
        if sort_by == "latency_ms":
            return run.latency_ms
        if sort_by == "finished_at":
            return _coerce_utc_datetime(run.finished_at) if run.finished_at is not None else None
        if sort_by == "estimated_cost_usd":
            return run.estimated_cost_usd
        return _coerce_utc_datetime(run.created_at)

    @staticmethod
    def _to_history_entry(
        *,
        run: Run,
        experiment_name: str | None,
        evaluation: RunEvaluation | None,
    ) -> RunHistoryEntry:
        return RunHistoryEntry(
            id=run.id,
            experiment_id=run.experiment_id,
            experiment_name=experiment_name,
            test_case_id=run.test_case_id,
            config_id=run.config_id,
            config_name=str(run.config_snapshot_json.get("name", "Unknown config")),
            config_version_label=str(run.config_snapshot_json.get("version_label", "")),
            test_case_input_preview=_build_input_preview(
                str(run.input_snapshot_json.get("input_text", "")),
            ),
            status=run.status,
            provider=run.provider,
            model=run.model,
            workflow_mode=run.workflow_mode,
            tags=_merge_snapshot_tags(run=run),
            latency_ms=run.latency_ms,
            estimated_cost_usd=run.estimated_cost_usd,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            evaluation=evaluation,
        )


class RunEvaluationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._run_repository = RunRepository(session)
        self._evaluation_repository = RunEvaluationRepository(session)

    def get(self, *, user_id: UUID, run_id: UUID) -> RunEvaluation | None:
        self._get_run_or_raise(user_id=user_id, run_id=run_id)
        return self._evaluation_repository.get_for_run(user_id=user_id, run_id=run_id)

    def upsert(
        self,
        *,
        user_id: UUID,
        run_id: UUID,
        overall_score: int | None,
        dimension_scores: dict[str, int],
        thumbs_signal: str | None,
        notes: str | None,
    ) -> RunEvaluation:
        self._get_run_or_raise(user_id=user_id, run_id=run_id)
        evaluation = self._evaluation_repository.get_for_run(user_id=user_id, run_id=run_id)
        if evaluation is None:
            evaluation = self._evaluation_repository.add(
                RunEvaluation(
                    user_id=user_id,
                    run_id=run_id,
                    overall_score=overall_score,
                    dimension_scores=dict(dimension_scores),
                    thumbs_signal=thumbs_signal,
                    notes=notes,
                )
            )
        else:
            evaluation.overall_score = overall_score
            evaluation.dimension_scores = dict(dimension_scores)
            evaluation.thumbs_signal = thumbs_signal
            evaluation.notes = notes

        self._session.flush()
        return evaluation

    def delete(self, *, user_id: UUID, run_id: UUID) -> None:
        self._get_run_or_raise(user_id=user_id, run_id=run_id)
        deleted = self._evaluation_repository.delete_for_run(user_id=user_id, run_id=run_id)
        if not deleted:
            raise UserOwnedResourceNotFoundError(
                resource_name="Run evaluation",
                resource_id=run_id,
                user_id=user_id,
            )

        self._session.flush()

    def _get_run_or_raise(self, *, user_id: UUID, run_id: UUID) -> Run:
        run = self._run_repository.get_owned(user_id=user_id, resource_id=run_id)
        if run is None:
            raise UserOwnedResourceNotFoundError(
                resource_name="Run",
                resource_id=run_id,
                user_id=user_id,
            )
        return run


def _merge_snapshot_tags(*, run: Run) -> list[str]:
    merged_tags: list[str] = []
    seen: set[str] = set()

    for raw_tag in [
        *run.config_snapshot_json.get("tags", []),
        *run.input_snapshot_json.get("tags", []),
    ]:
        if not isinstance(raw_tag, str):
            continue

        tag = raw_tag.strip().lower()
        if not tag or tag in seen:
            continue

        seen.add(tag)
        merged_tags.append(tag)

    return merged_tags


def _build_input_preview(value: str) -> str:
    compact = " ".join(value.split())
    if len(compact) <= 80:
        return compact
    return f"{compact[:77]}..."


def _coerce_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
