from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.configs.models import Config
from benchloop_api.configs.repository import ConfigRepository
from benchloop_api.execution.adapters import (
    ProviderAdapterRegistry,
    ProviderExecutionError,
    SingleShotProviderRequest,
)
from benchloop_api.execution.rendering import PromptRenderingError
from benchloop_api.execution.snapshots import RunSnapshotBundle
from benchloop_api.execution.snapshots import build_run_snapshot_bundle
from benchloop_api.experiments.repository import ExperimentRepository
from benchloop_api.ownership.service import UserOwnedResourceNotFoundError
from benchloop_api.runs.models import Run
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
        run = self._run_service.create_pending(
            user_id=user_id,
            experiment_id=experiment_id,
            config=config,
            test_case=test_case,
            snapshot_bundle=snapshot_bundle,
        )
        adapter = self._provider_registry.get(provider=config.provider)
        if adapter is None:
            self._run_service.mark_failed(
                run=run,
                error_message=f"Provider '{config.provider}' is not supported for execution.",
            )
            self._session.refresh(run)
            return run

        credential = self._credential_repository.get_active_for_provider(
            user_id=user_id,
            provider=config.provider,
        )
        if credential is None:
            self._run_service.mark_failed(
                run=run,
                error_message=f"No active credential is configured for provider '{config.provider}'.",
            )
            self._session.refresh(run)
            return run

        if credential.validation_status == "invalid":
            self._run_service.mark_failed(
                run=run,
                error_message=(
                    f"Stored credential for provider '{config.provider}' is marked invalid."
                ),
            )
            self._session.refresh(run)
            return run

        self._run_service.mark_running(run=run, credential_id=credential.id)
        api_key = self._encryption_service.decrypt(credential.encrypted_api_key)
        request = SingleShotProviderRequest(
            provider=config.provider,
            model=snapshot_bundle.config_snapshot.model,
            system_prompt=snapshot_bundle.config_snapshot.rendered_system_prompt,
            user_prompt=snapshot_bundle.config_snapshot.rendered_user_prompt,
            temperature=snapshot_bundle.config_snapshot.temperature,
            max_output_tokens=snapshot_bundle.config_snapshot.max_output_tokens,
            top_p=snapshot_bundle.config_snapshot.top_p,
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
        self._test_case_repository = TestCaseRepository(session)

    async def launch_single(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        test_case_id: UUID,
        config_id: UUID,
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
        snapshot_bundle = self._build_snapshot_bundle(config=config, test_case=test_case)
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
    ) -> list[Run]:
        runs: list[Run] = []
        for config_id in config_ids:
            runs.append(
                await self.launch_single(
                    user_id=user_id,
                    experiment_id=experiment_id,
                    test_case_id=test_case_id,
                    config_id=config_id,
                )
            )
        return runs

    def _build_snapshot_bundle(
        self,
        *,
        config: Config,
        test_case: TestCase,
    ) -> RunSnapshotBundle:
        try:
            return build_run_snapshot_bundle(
                config=config,
                test_case=test_case,
            )
        except PromptRenderingError:
            raise

    def _ensure_single_shot(self, *, config: Config) -> None:
        if config.workflow_mode != "single_shot":
            raise UnsupportedExecutionWorkflowError(workflow_mode=config.workflow_mode)

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
