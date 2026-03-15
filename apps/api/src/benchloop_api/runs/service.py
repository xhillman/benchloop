from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.configs.models import Config
from benchloop_api.execution.adapters import ProviderExecutionResult
from benchloop_api.execution.snapshots import RunSnapshotBundle
from benchloop_api.runs.models import Run
from benchloop_api.runs.repository import RunRepository
from benchloop_api.test_cases.models import TestCase

RUN_STATUS_PENDING = "pending"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"


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
        run = self._repository.add(
            Run(
                user_id=user_id,
                experiment_id=experiment_id,
                test_case_id=test_case.id,
                config_id=config.id,
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
