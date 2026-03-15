from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.configs.models import Config
from benchloop_api.execution.adapters import (
    ProviderAdapterRegistry,
    ProviderExecutionError,
    SingleShotProviderRequest,
)
from benchloop_api.execution.snapshots import RunSnapshotBundle
from benchloop_api.runs.models import Run
from benchloop_api.runs.service import RunService
from benchloop_api.settings.encryption import EncryptionService
from benchloop_api.settings.repository import UserProviderCredentialRepository
from benchloop_api.test_cases.models import TestCase


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
