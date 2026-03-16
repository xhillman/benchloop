from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from benchloop_api.configs.models import Config
from benchloop_api.configs.repository import ConfigRepository
from benchloop_api.context_bundles.repository import ContextBundleRepository
from benchloop_api.execution.adapters import (
    ProviderAdapterRegistry,
    ProviderExecutionError,
    SingleShotProviderRequest,
)
from benchloop_api.execution.rendering import PromptRenderingError
from benchloop_api.execution.snapshots import ContextSnapshot, RunSnapshotBundle, build_run_snapshot_bundle
from benchloop_api.experiments.repository import ExperimentRepository
from benchloop_api.ownership.service import UserOwnedResourceNotFoundError
from benchloop_api.runs.models import Run
from benchloop_api.runs.repository import RunRepository
from benchloop_api.runs.service import RunService
from benchloop_api.settings.encryption import EncryptionService
from benchloop_api.settings.repository import UserProviderCredentialRepository
from benchloop_api.test_cases.models import TestCase
from benchloop_api.test_cases.repository import TestCaseRepository


class UnsupportedExecutionWorkflowError(ValueError):
    def __init__(self, *, workflow_mode: str) -> None:
        self.workflow_mode = workflow_mode
        super().__init__(
            f"Config workflow mode '{workflow_mode}' is not supported by single-shot execution."
        )


class StoredRunSnapshotInvalidError(ValueError):
    def __init__(self, *, run_id: UUID) -> None:
        self.run_id = run_id
        super().__init__(f"Stored snapshot for run '{run_id}' is invalid and cannot be rerun.")


@dataclass(frozen=True)
class InlineExecutionContext:
    content_text: str
    name: str | None = None
    notes: str | None = None


class MissingExecutionContextError(ValueError):
    def __init__(self, *, config_id: UUID) -> None:
        self.config_id = config_id
        super().__init__(
            f"Config '{config_id}' requires a saved or inline context before execution."
        )


class SingleShotExecutionService:
    def __init__(
        self,
        *,
        session: Session,
        encryption_service: EncryptionService,
        provider_registry: ProviderAdapterRegistry,
    ) -> None:
        self._session = session
        self._encryption_service = encryption_service
        self._provider_registry = provider_registry
        self._credential_repository = UserProviderCredentialRepository(session)
        self._run_service = RunService(session)

    async def execute_single_shot(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        test_case: TestCase,
        config: Config,
        snapshot_bundle: RunSnapshotBundle,
    ) -> Run:
        return await self.execute_snapshot(
            user_id=user_id,
            experiment_id=experiment_id,
            config_id=config.id,
            test_case_id=test_case.id,
            snapshot_bundle=snapshot_bundle,
        )

    async def execute_rerun(
        self,
        *,
        user_id: UUID,
        source_run: Run,
        snapshot_bundle: RunSnapshotBundle,
    ) -> Run:
        return await self.execute_snapshot(
            user_id=user_id,
            experiment_id=source_run.experiment_id,
            config_id=source_run.config_id,
            test_case_id=source_run.test_case_id,
            snapshot_bundle=snapshot_bundle,
        )

    async def execute_snapshot(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        config_id: UUID,
        test_case_id: UUID,
        snapshot_bundle: RunSnapshotBundle,
    ) -> Run:
        config_snapshot = snapshot_bundle.config_snapshot
        run = self._run_service.create_pending_from_snapshot(
            user_id=user_id,
            experiment_id=experiment_id,
            config_id=config_id,
            test_case_id=test_case_id,
            snapshot_bundle=snapshot_bundle,
        )
        adapter = self._provider_registry.get(provider=config_snapshot.provider)
        if adapter is None:
            self._run_service.mark_failed(
                run=run,
                error_message=(
                    f"Provider '{config_snapshot.provider}' is not supported for execution."
                ),
            )
            self._session.refresh(run)
            return run

        credential = self._credential_repository.get_active_for_provider(
            user_id=user_id,
            provider=config_snapshot.provider,
        )
        if credential is None:
            self._run_service.mark_failed(
                run=run,
                error_message=(
                    f"No active credential is configured for provider '{config_snapshot.provider}'."
                ),
            )
            self._session.refresh(run)
            return run

        if credential.validation_status == "invalid":
            self._run_service.mark_failed(
                run=run,
                error_message=(
                    f"Stored credential for provider '{config_snapshot.provider}' is marked invalid."
                ),
            )
            self._session.refresh(run)
            return run

        self._run_service.mark_running(run=run, credential_id=credential.id)
        api_key = self._encryption_service.decrypt(credential.encrypted_api_key)
        request = SingleShotProviderRequest(
            provider=config_snapshot.provider,
            model=config_snapshot.model,
            system_prompt=config_snapshot.rendered_system_prompt,
            user_prompt=config_snapshot.rendered_user_prompt,
            temperature=config_snapshot.temperature,
            max_output_tokens=config_snapshot.max_output_tokens,
            top_p=config_snapshot.top_p,
            api_key=api_key,
        )

        try:
            result = await adapter.execute(request=request)
        except ProviderExecutionError as exc:
            self._run_service.mark_failed(run=run, error_message=str(exc))
        else:
            self._run_service.mark_completed(run=run, result=result)
        finally:
            del api_key

        self._session.refresh(run)
        return run


class RunLaunchService:
    def __init__(
        self,
        *,
        session: Session,
        execution_service: SingleShotExecutionService,
    ) -> None:
        self._session = session
        self._execution_service = execution_service
        self._experiment_repository = ExperimentRepository(session)
        self._config_repository = ConfigRepository(session)
        self._context_bundle_repository = ContextBundleRepository(session)
        self._run_repository = RunRepository(session)
        self._test_case_repository = TestCaseRepository(session)

    async def launch_single(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        test_case_id: UUID,
        config_id: UUID,
        context_bundle_id: UUID | None = None,
        inline_context: InlineExecutionContext | None = None,
    ) -> Run:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        test_case = self._get_test_case_or_raise(
            user_id=user_id,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
        )
        config = self._get_config_or_raise(
            user_id=user_id,
            experiment_id=experiment_id,
            config_id=config_id,
        )
        self._ensure_single_shot(config=config)
        snapshot_bundle = self._build_snapshot_bundle(
            user_id=user_id,
            experiment_id=experiment_id,
            config=config,
            test_case=test_case,
            context_bundle_id=context_bundle_id,
            inline_context=inline_context,
        )
        return await self._execution_service.execute_single_shot(
            user_id=user_id,
            experiment_id=experiment_id,
            test_case=test_case,
            config=config,
            snapshot_bundle=snapshot_bundle,
        )

    async def launch_batch(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        test_case_id: UUID,
        config_ids: list[UUID],
        context_bundle_id: UUID | None = None,
        inline_context: InlineExecutionContext | None = None,
    ) -> list[Run]:
        runs: list[Run] = []
        for config_id in config_ids:
            runs.append(
                await self.launch_single(
                    user_id=user_id,
                    experiment_id=experiment_id,
                    test_case_id=test_case_id,
                    config_id=config_id,
                    context_bundle_id=context_bundle_id,
                    inline_context=inline_context,
                )
            )
        return runs

    async def rerun_from_snapshot(
        self,
        *,
        user_id: UUID,
        run_id: UUID,
    ) -> Run:
        source_run = self._get_run_or_raise(user_id=user_id, run_id=run_id)
        snapshot_bundle = self._build_snapshot_bundle_from_run(run=source_run)
        self._ensure_single_shot_workflow_mode(
            workflow_mode=snapshot_bundle.config_snapshot.workflow_mode
        )
        return await self._execution_service.execute_rerun(
            user_id=user_id,
            source_run=source_run,
            snapshot_bundle=snapshot_bundle,
        )

    def _build_snapshot_bundle(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        config: Config,
        test_case: TestCase,
        context_bundle_id: UUID | None = None,
        inline_context: InlineExecutionContext | None = None,
    ) -> RunSnapshotBundle:
        context_snapshot = self._resolve_context_snapshot(
            user_id=user_id,
            experiment_id=experiment_id,
            config=config,
            context_bundle_id=context_bundle_id,
            inline_context=inline_context,
        )
        try:
            return build_run_snapshot_bundle(
                config=config,
                test_case=test_case,
                context_snapshot=context_snapshot,
            )
        except PromptRenderingError:
            raise

    def _ensure_single_shot(self, *, config: Config) -> None:
        self._ensure_single_shot_workflow_mode(workflow_mode=config.workflow_mode)

    def _ensure_single_shot_workflow_mode(self, *, workflow_mode: str) -> None:
        if workflow_mode not in {"prompt_plus_context", "single_shot"}:
            raise UnsupportedExecutionWorkflowError(workflow_mode=workflow_mode)

    def _resolve_context_snapshot(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        config: Config,
        context_bundle_id: UUID | None,
        inline_context: InlineExecutionContext | None,
    ) -> ContextSnapshot | None:
        if config.workflow_mode != "prompt_plus_context":
            if context_bundle_id is not None or inline_context is not None:
                raise UnsupportedExecutionWorkflowError(workflow_mode=config.workflow_mode)
            return None

        if inline_context is not None:
            return ContextSnapshot(
                source="inline",
                name=inline_context.name,
                content_text=inline_context.content_text,
                notes=inline_context.notes,
            )

        resolved_context_bundle_id = context_bundle_id or config.context_bundle_id
        if resolved_context_bundle_id is None:
            raise MissingExecutionContextError(config_id=config.id)

        context_bundle = self._context_bundle_repository.get_owned_for_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            context_bundle_id=resolved_context_bundle_id,
        )
        if context_bundle is None:
            raise UserOwnedResourceNotFoundError(
                resource_name="Context bundle",
                resource_id=resolved_context_bundle_id,
                user_id=user_id,
            )

        return ContextSnapshot(
            source="bundle",
            bundle_id=context_bundle.id,
            name=context_bundle.name,
            content_text=context_bundle.content_text,
            notes=context_bundle.notes,
        )

    def _build_snapshot_bundle_from_run(self, *, run: Run) -> RunSnapshotBundle:
        try:
            return RunSnapshotBundle.model_validate(
                {
                    "config_snapshot": run.config_snapshot_json,
                    "input_snapshot": run.input_snapshot_json,
                    "context_snapshot": run.context_snapshot_json,
                }
            )
        except ValidationError as exc:
            raise StoredRunSnapshotInvalidError(run_id=run.id) from exc

    def _get_experiment_or_raise(self, *, user_id: UUID, experiment_id: UUID) -> None:
        experiment = self._experiment_repository.get_owned(
            user_id=user_id,
            resource_id=experiment_id,
        )
        if experiment is None:
            raise UserOwnedResourceNotFoundError(
                resource_name="Experiment",
                resource_id=experiment_id,
                user_id=user_id,
            )

    def _get_config_or_raise(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        config_id: UUID,
    ) -> Config:
        config = self._config_repository.get_owned_for_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            config_id=config_id,
        )
        if config is None:
            raise UserOwnedResourceNotFoundError(
                resource_name="Config",
                resource_id=config_id,
                user_id=user_id,
            )
        return config

    def _get_run_or_raise(self, *, user_id: UUID, run_id: UUID) -> Run:
        run = self._run_repository.get_owned(user_id=user_id, resource_id=run_id)
        if run is None:
            raise UserOwnedResourceNotFoundError(
                resource_name="Run",
                resource_id=run_id,
                user_id=user_id,
            )
        return run

    def _get_test_case_or_raise(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        test_case_id: UUID,
    ) -> TestCase:
        test_case = self._test_case_repository.get_owned_for_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
        )
        if test_case is None:
            raise UserOwnedResourceNotFoundError(
                resource_name="Test case",
                resource_id=test_case_id,
                user_id=user_id,
            )
        return test_case
