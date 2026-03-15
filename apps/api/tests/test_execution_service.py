import asyncio
from collections.abc import Generator

import pytest
from sqlalchemy import select

from benchloop_api.config import AppSettings
from benchloop_api.configs.models import Config
from benchloop_api.db.base import Base
from benchloop_api.db.session import create_database_engine, create_session_factory
from benchloop_api.execution.adapters import (
    ProviderAdapterRegistry,
    ProviderExecutionError,
    ProviderExecutionResult,
    ProviderUsage,
    SingleShotProviderRequest,
)
from benchloop_api.execution.service import SingleShotExecutionService
from benchloop_api.execution.snapshots import build_run_snapshot_bundle
from benchloop_api.experiments.models import Experiment
from benchloop_api.runs.models import Run
from benchloop_api.settings.encryption import EncryptionService
from benchloop_api.settings.models import UserProviderCredential
from benchloop_api.test_cases.models import TestCase as BenchloopTestCase
from benchloop_api.users.models import User


class StubProviderAdapter:
    def __init__(
        self,
        *,
        provider: str,
        result: ProviderExecutionResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.provider = provider
        self._result = result
        self._error = error
        self.calls: list[SingleShotProviderRequest] = []

    async def execute(
        self,
        *,
        request: SingleShotProviderRequest,
    ) -> ProviderExecutionResult:
        self.calls.append(request)
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


@pytest.fixture()
def sqlite_settings(tmp_path) -> AppSettings:
    return AppSettings.model_validate(
        {
            "database_url": f"sqlite+pysqlite:///{tmp_path / 'benchloop-execution.db'}",
            "db_echo": False,
        }
    )


@pytest.fixture()
def database_engine(sqlite_settings) -> Generator:
    engine = create_database_engine(sqlite_settings)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def session_factory(database_engine):
    Base.metadata.create_all(database_engine)
    return create_session_factory(database_engine)


def build_records(
    session,
    encryption_service: EncryptionService,
) -> tuple[User, Experiment, BenchloopTestCase, Config]:
    user = User(clerk_user_id="user_123")
    session.add(user)
    session.flush()

    experiment = Experiment(
        user_id=user.id,
        name="Refund handling",
        description="Support experiment.",
        tags=["support"],
        is_archived=False,
    )
    session.add(experiment)
    session.flush()

    test_case = BenchloopTestCase(
        user_id=user.id,
        experiment_id=experiment.id,
        input_text="Refund the customer for the duplicate charge.",
        expected_output_text="Confirm the refund and timeline.",
        notes="High-priority billing case.",
        tags=["billing"],
    )
    config = Config(
        user_id=user.id,
        experiment_id=experiment.id,
        name="Refund responder",
        version_label="v1",
        description="Single-shot support response.",
        provider="openai",
        model="gpt-4.1-mini",
        workflow_mode="single_shot",
        system_prompt="You are a concise support assistant.",
        user_prompt_template="Answer the request: {{input}}",
        temperature=0.2,
        max_output_tokens=256,
        top_p=0.9,
        context_bundle_id=None,
        tags=["baseline"],
        is_baseline=True,
    )
    credential = UserProviderCredential(
        user_id=user.id,
        provider="openai",
        encrypted_api_key=encryption_service.encrypt("sk-test-secret"),
        key_label="Primary OpenAI key",
        validation_status="valid",
    )

    session.add_all([test_case, config, credential])
    session.flush()
    return user, experiment, test_case, config


def test_execute_single_shot_persists_completed_run(session_factory) -> None:
    encryption_service = EncryptionService("test-encryption-key-material")
    adapter = StubProviderAdapter(
        provider="openai",
        result=ProviderExecutionResult(
            provider="openai",
            model="gpt-4.1-mini-2025-04-14",
            output_text="Refund approved. The duplicate charge will be reversed.",
            usage=ProviderUsage(
                input_tokens=111,
                output_tokens=29,
                total_tokens=140,
            ),
            latency_ms=245,
        ),
    )

    with session_factory() as session:
        user, experiment, test_case, config = build_records(session, encryption_service)
        snapshot_bundle = build_run_snapshot_bundle(config=config, test_case=test_case)
        service = SingleShotExecutionService(
            session=session,
            encryption_service=encryption_service,
            provider_registry=ProviderAdapterRegistry(adapters=[adapter]),
        )

        run = asyncio.run(
            service.execute_single_shot(
                user_id=user.id,
                experiment_id=experiment.id,
                test_case=test_case,
                config=config,
                snapshot_bundle=snapshot_bundle,
            )
        )
        session.commit()

        persisted_run = session.scalar(select(Run).where(Run.id == run.id))

    assert persisted_run is not None
    assert len(adapter.calls) == 1
    assert adapter.calls[0].api_key == "sk-test-secret"
    assert persisted_run.status == "completed"
    assert persisted_run.provider == "openai"
    assert persisted_run.model == "gpt-4.1-mini-2025-04-14"
    assert persisted_run.output_text == "Refund approved. The duplicate charge will be reversed."
    assert persisted_run.error_message is None
    assert persisted_run.usage_input_tokens == 111
    assert persisted_run.usage_output_tokens == 29
    assert persisted_run.usage_total_tokens == 140
    assert persisted_run.latency_ms == 245
    assert persisted_run.started_at is not None
    assert persisted_run.finished_at is not None
    assert persisted_run.config_snapshot_json["config_id"] == str(config.id)
    assert persisted_run.input_snapshot_json["test_case_id"] == str(test_case.id)
    assert persisted_run.context_snapshot_json is None


def test_execute_single_shot_persists_failed_run_for_missing_credential(session_factory) -> None:
    encryption_service = EncryptionService("test-encryption-key-material")
    adapter = StubProviderAdapter(
        provider="openai",
        result=ProviderExecutionResult(
            provider="openai",
            model="gpt-4.1-mini",
            output_text="unused",
            usage=ProviderUsage(input_tokens=1, output_tokens=1, total_tokens=2),
            latency_ms=1,
        ),
    )

    with session_factory() as session:
        user = User(clerk_user_id="user_123")
        session.add(user)
        session.flush()

        experiment = Experiment(
            user_id=user.id,
            name="Refund handling",
            description=None,
            tags=[],
            is_archived=False,
        )
        session.add(experiment)
        session.flush()

        test_case = BenchloopTestCase(
            user_id=user.id,
            experiment_id=experiment.id,
            input_text="Refund the customer for the duplicate charge.",
            expected_output_text=None,
            notes=None,
            tags=[],
        )
        config = Config(
            user_id=user.id,
            experiment_id=experiment.id,
            name="Refund responder",
            version_label="v1",
            description=None,
            provider="openai",
            model="gpt-4.1-mini",
            workflow_mode="single_shot",
            system_prompt=None,
            user_prompt_template="Answer the request: {{input}}",
            temperature=0.2,
            max_output_tokens=256,
            top_p=None,
            context_bundle_id=None,
            tags=[],
            is_baseline=False,
        )
        session.add_all([test_case, config])
        session.flush()

        snapshot_bundle = build_run_snapshot_bundle(config=config, test_case=test_case)
        service = SingleShotExecutionService(
            session=session,
            encryption_service=encryption_service,
            provider_registry=ProviderAdapterRegistry(adapters=[adapter]),
        )

        run = asyncio.run(
            service.execute_single_shot(
                user_id=user.id,
                experiment_id=experiment.id,
                test_case=test_case,
                config=config,
                snapshot_bundle=snapshot_bundle,
            )
        )
        session.commit()

        persisted_run = session.scalar(select(Run).where(Run.id == run.id))

    assert persisted_run is not None
    assert persisted_run.status == "failed"
    assert persisted_run.error_message == "No active credential is configured for provider 'openai'."
    assert persisted_run.finished_at is not None
    assert persisted_run.output_text is None
    assert adapter.calls == []


def test_execute_single_shot_persists_failed_run_for_provider_error(session_factory) -> None:
    encryption_service = EncryptionService("test-encryption-key-material")
    adapter = StubProviderAdapter(
        provider="openai",
        error=ProviderExecutionError(
            provider="openai",
            message="Authentication failed for provider 'openai'.",
        ),
    )

    with session_factory() as session:
        user, experiment, test_case, config = build_records(session, encryption_service)
        snapshot_bundle = build_run_snapshot_bundle(config=config, test_case=test_case)
        service = SingleShotExecutionService(
            session=session,
            encryption_service=encryption_service,
            provider_registry=ProviderAdapterRegistry(adapters=[adapter]),
        )

        run = asyncio.run(
            service.execute_single_shot(
                user_id=user.id,
                experiment_id=experiment.id,
                test_case=test_case,
                config=config,
                snapshot_bundle=snapshot_bundle,
            )
        )
        session.commit()

        persisted_run = session.scalar(select(Run).where(Run.id == run.id))

    assert persisted_run is not None
    assert len(adapter.calls) == 1
    assert persisted_run.status == "failed"
    assert persisted_run.error_message == "Authentication failed for provider 'openai'."
    assert persisted_run.finished_at is not None
    assert persisted_run.output_text is None
    assert "sk-test-secret" not in persisted_run.error_message
