import asyncio
import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from benchloop_api.app import create_app
from benchloop_api.auth.service import ClerkJwtVerifier
from benchloop_api.configs.models import Config
from benchloop_api.db.base import Base
from benchloop_api.execution.adapters import (
    ProviderAdapterRegistry,
    ProviderExecutionError,
    ProviderExecutionResult,
    ProviderUsage,
    SingleShotProviderRequest,
)
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


def request(
    app,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, object | list[object] | None] | None = None,
) -> httpx.Response:
    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(
                method,
                path,
                headers=headers,
                json=json_body,
            )

    return asyncio.run(run_request())


@pytest.fixture()
def rsa_private_key() -> Generator:
    yield rsa.generate_private_key(public_exponent=65537, key_size=2048)


def build_signed_token(
    private_key,
    *,
    kid: str = "test-key",
    subject: str = "user_123",
) -> str:
    now = datetime.now(tz=UTC)
    claims = {
        "sub": subject,
        "iss": "https://clerk.example.com",
        "aud": "benchloop",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=5),
    }

    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


def build_jwks_transport(public_key, *, kid: str = "test-key") -> httpx.MockTransport:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))
    jwk["kid"] = kid

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://clerk.example.com/.well-known/jwks.json")
        return httpx.Response(200, json={"keys": [jwk]})

    return httpx.MockTransport(handler)


@pytest.fixture()
def sqlite_database_url(tmp_path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'benchloop-runs.db'}"


def build_test_app(
    rsa_private_key,
    sqlite_database_url,
    *,
    adapters: list[StubProviderAdapter] | None = None,
):
    app = create_app(
        {
            "database_url": sqlite_database_url,
            "clerk_jwks_url": "https://clerk.example.com/.well-known/jwks.json",
            "clerk_jwt_issuer": "https://clerk.example.com",
            "clerk_jwt_audience": "benchloop",
            "encryption_key": "test-encryption-key-material",
        }
    )
    Base.metadata.create_all(app.state.db_engine)
    app.state.auth_verifier = ClerkJwtVerifier(
        app.state.settings,
        transport=build_jwks_transport(rsa_private_key.public_key()),
    )
    app.state.provider_adapter_registry = ProviderAdapterRegistry(adapters=adapters or [])
    return app


def auth_headers(rsa_private_key, *, subject: str = "user_123") -> dict[str, str]:
    token = build_signed_token(rsa_private_key, subject=subject)
    return {"Authorization": f"Bearer {token}"}


def seed_run_launch_records(
    session,
    encryption_service: EncryptionService,
    *,
    workflow_mode: str = "single_shot",
) -> dict[str, object]:
    user = User(clerk_user_id="user_123")
    session.add(user)
    session.flush()

    experiment = Experiment(
        user_id=user.id,
        name="Support triage",
        description="Run launch test experiment.",
        tags=["support"],
        is_archived=False,
    )
    session.add(experiment)
    session.flush()

    test_case = BenchloopTestCase(
        user_id=user.id,
        experiment_id=experiment.id,
        input_text="Refund the customer for the duplicate charge.",
        expected_output_text="Acknowledge the refund timeline.",
        notes="High-priority billing issue.",
        tags=["refund"],
    )
    config = Config(
        user_id=user.id,
        experiment_id=experiment.id,
        name="Direct answer",
        version_label="v1",
        description="Primary execution config.",
        provider="openai",
        model="gpt-4.1-mini",
        workflow_mode=workflow_mode,
        system_prompt="You are a concise support assistant.",
        user_prompt_template="Reply to this ticket: {{input}}",
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
        encrypted_api_key=encryption_service.encrypt("sk-openai-secret"),
        key_label="Primary OpenAI key",
        validation_status="valid",
    )
    session.add_all([test_case, config, credential])
    session.flush()

    return {
        "user": user,
        "experiment": experiment,
        "test_case": test_case,
        "config": config,
        "credential": credential,
    }


def test_run_launch_endpoints_require_authentication() -> None:
    app = create_app()

    response = request(
        app,
        "POST",
        "/api/v1/experiments/11111111-1111-1111-1111-111111111111/runs",
        json_body={
            "test_case_id": "22222222-2222-2222-2222-222222222222",
            "config_id": "33333333-3333-3333-3333-333333333333",
        },
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "authentication_failed",
            "message": "Authentication required.",
            "details": None,
        }
    }


def test_launch_single_run_returns_a_completed_run(rsa_private_key, sqlite_database_url) -> None:
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
    app = build_test_app(rsa_private_key, sqlite_database_url, adapters=[adapter])

    with app.state.session_factory() as session:
        records = seed_run_launch_records(
            session,
            app.state.encryption_service,
        )
        session.commit()

    response = request(
        app,
        "POST",
        f"/api/v1/experiments/{records['experiment'].id}/runs",
        headers=auth_headers(rsa_private_key),
        json_body={
            "test_case_id": str(records["test_case"].id),
            "config_id": str(records["config"].id),
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["experiment_id"] == str(records["experiment"].id)
    assert payload["test_case_id"] == str(records["test_case"].id)
    assert payload["config_id"] == str(records["config"].id)
    assert payload["provider"] == "openai"
    assert payload["model"] == "gpt-4.1-mini-2025-04-14"
    assert payload["output_text"] == "Refund approved. The duplicate charge will be reversed."
    assert payload["config_snapshot"]["rendered_user_prompt"] == (
        "Reply to this ticket: Refund the customer for the duplicate charge."
    )
    assert payload["input_snapshot"]["input_text"] == (
        "Refund the customer for the duplicate charge."
    )
    assert payload["context_snapshot"] is None

    with app.state.session_factory() as session:
        persisted_runs = session.scalars(select(Run)).all()

    assert len(persisted_runs) == 1
    assert len(adapter.calls) == 1
    assert adapter.calls[0].api_key == "sk-openai-secret"


def test_launch_multiple_runs_returns_one_run_per_selected_config(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    openai_adapter = StubProviderAdapter(
        provider="openai",
        result=ProviderExecutionResult(
            provider="openai",
            model="gpt-4.1-mini",
            output_text="OpenAI answer",
            usage=ProviderUsage(input_tokens=12, output_tokens=8, total_tokens=20),
            latency_ms=100,
        ),
    )
    anthropic_adapter = StubProviderAdapter(
        provider="anthropic",
        result=ProviderExecutionResult(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            output_text="Anthropic answer",
            usage=ProviderUsage(input_tokens=14, output_tokens=9, total_tokens=23),
            latency_ms=120,
        ),
    )
    app = build_test_app(
        rsa_private_key,
        sqlite_database_url,
        adapters=[openai_adapter, anthropic_adapter],
    )

    with app.state.session_factory() as session:
        records = seed_run_launch_records(
            session,
            app.state.encryption_service,
        )
        anthropic_config = Config(
            user_id=records["user"].id,
            experiment_id=records["experiment"].id,
            name="Thorough answer",
            version_label="v2",
            description="Anthropic variant.",
            provider="anthropic",
            model="claude-3-5-sonnet-latest",
            workflow_mode="single_shot",
            system_prompt="You are a careful support assistant.",
            user_prompt_template="Review this issue: {{input}}",
            temperature=0.3,
            max_output_tokens=300,
            top_p=None,
            context_bundle_id=None,
            tags=["comparison"],
            is_baseline=False,
        )
        anthropic_credential = UserProviderCredential(
            user_id=records["user"].id,
            provider="anthropic",
            encrypted_api_key=app.state.encryption_service.encrypt("sk-anthropic-secret"),
            key_label="Anthropic key",
            validation_status="valid",
        )
        session.add_all([anthropic_config, anthropic_credential])
        session.commit()

    response = request(
        app,
        "POST",
        f"/api/v1/experiments/{records['experiment'].id}/runs/batch",
        headers=auth_headers(rsa_private_key),
        json_body={
            "test_case_id": str(records["test_case"].id),
            "config_ids": [
                str(records["config"].id),
                str(anthropic_config.id),
            ],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert [run["config_id"] for run in payload] == [
        str(records["config"].id),
        str(anthropic_config.id),
    ]
    assert [run["status"] for run in payload] == ["completed", "completed"]
    assert [run["provider"] for run in payload] == ["openai", "anthropic"]

    with app.state.session_factory() as session:
        persisted_runs = session.scalars(select(Run).order_by(Run.created_at.asc())).all()

    assert len(persisted_runs) == 2
    assert len(openai_adapter.calls) == 1
    assert len(anthropic_adapter.calls) == 1


def test_launch_routes_reject_non_single_shot_configs(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    with app.state.session_factory() as session:
        records = seed_run_launch_records(
            session,
            app.state.encryption_service,
            workflow_mode="prompt_plus_context",
        )
        session.commit()

    response = request(
        app,
        "POST",
        f"/api/v1/experiments/{records['experiment'].id}/runs",
        headers=auth_headers(rsa_private_key),
        json_body={
            "test_case_id": str(records["test_case"].id),
            "config_id": str(records["config"].id),
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "Config workflow mode 'prompt_plus_context' is not supported by single-shot execution.",
            "details": None,
        }
    }

    with app.state.session_factory() as session:
        persisted_runs = session.scalars(select(Run)).all()

    assert persisted_runs == []


def test_launch_routes_enforce_experiment_and_user_scope(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    adapter = StubProviderAdapter(
        provider="openai",
        error=ProviderExecutionError(
            provider="openai",
            message="should not execute",
        ),
    )
    app = build_test_app(rsa_private_key, sqlite_database_url, adapters=[adapter])

    with app.state.session_factory() as session:
        owner = User(clerk_user_id="user_123")
        other_user = User(clerk_user_id="user_456")
        session.add_all([owner, other_user])
        session.flush()

        owner_experiment = Experiment(
            user_id=owner.id,
            name="Owner experiment",
            description=None,
            tags=["owner"],
            is_archived=False,
        )
        other_experiment = Experiment(
            user_id=other_user.id,
            name="Other experiment",
            description=None,
            tags=["other"],
            is_archived=False,
        )
        session.add_all([owner_experiment, other_experiment])
        session.flush()

        owner_test_case = BenchloopTestCase(
            user_id=owner.id,
            experiment_id=owner_experiment.id,
            input_text="Owner case",
            expected_output_text=None,
            notes=None,
            tags=[],
        )
        other_config = Config(
            user_id=other_user.id,
            experiment_id=other_experiment.id,
            name="Other config",
            version_label="v1",
            description=None,
            provider="openai",
            model="gpt-4.1-mini",
            workflow_mode="single_shot",
            system_prompt=None,
            user_prompt_template="Other config {{input}}",
            temperature=0.2,
            max_output_tokens=128,
            top_p=None,
            context_bundle_id=None,
            tags=[],
            is_baseline=False,
        )
        session.add_all([owner_test_case, other_config])
        session.commit()

    response = request(
        app,
        "POST",
        f"/api/v1/experiments/{owner_experiment.id}/runs",
        headers=auth_headers(rsa_private_key),
        json_body={
            "test_case_id": str(owner_test_case.id),
            "config_id": str(other_config.id),
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Config was not found.",
            "details": None,
        }
    }
    assert adapter.calls == []
