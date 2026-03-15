import asyncio
import json
from collections.abc import Generator, Sequence
from datetime import UTC, datetime, timedelta
from typing import TypedDict
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
    SingleShotProviderAdapter,
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


class RunLaunchRecords(TypedDict):
    user: User
    experiment: Experiment
    test_case: BenchloopTestCase
    config: Config
    credential: UserProviderCredential


class RunHistoryRecords(TypedDict):
    owner: User
    billing_experiment: Experiment
    outbound_experiment: Experiment
    refund_config: Config
    escalation_config: Config
    other_run: Run
    runs: list[Run]


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
    adapters: Sequence[SingleShotProviderAdapter] | None = None,
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
    app.state.provider_adapter_registry = ProviderAdapterRegistry(adapters=list(adapters or []))
    return app


def auth_headers(rsa_private_key, *, subject: str = "user_123") -> dict[str, str]:
    token = build_signed_token(rsa_private_key, subject=subject)
    return {"Authorization": f"Bearer {token}"}


def seed_run_launch_records(
    session,
    encryption_service: EncryptionService,
    *,
    workflow_mode: str = "single_shot",
) -> RunLaunchRecords:
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


def build_config_snapshot(config: Config, *, rendered_user_prompt: str) -> dict[str, object]:
    return {
        "config_id": str(config.id),
        "name": config.name,
        "version_label": config.version_label,
        "description": config.description,
        "provider": config.provider,
        "model": config.model,
        "workflow_mode": config.workflow_mode,
        "system_prompt_template": config.system_prompt,
        "rendered_system_prompt": config.system_prompt,
        "user_prompt_template": config.user_prompt_template,
        "rendered_user_prompt": rendered_user_prompt,
        "temperature": config.temperature,
        "max_output_tokens": config.max_output_tokens,
        "top_p": config.top_p,
        "context_bundle_id": str(config.context_bundle_id) if config.context_bundle_id else None,
        "tags": list(config.tags),
        "is_baseline": config.is_baseline,
    }


def build_input_snapshot(test_case: BenchloopTestCase) -> dict[str, object]:
    return {
        "test_case_id": str(test_case.id),
        "input_text": test_case.input_text,
        "expected_output_text": test_case.expected_output_text,
        "notes": test_case.notes,
        "tags": list(test_case.tags),
    }


def build_context_snapshot() -> dict[str, object]:
    return {
        "source": "inline",
        "bundle_id": None,
        "name": "Refund policy excerpt",
        "content_text": "Refunds for duplicate charges are completed within 5 business days.",
        "notes": "Ground the answer in the billing policy.",
    }


def seed_run_history_records(session) -> RunHistoryRecords:
    owner = User(clerk_user_id="user_123")
    other_user = User(clerk_user_id="user_456")
    session.add_all([owner, other_user])
    session.flush()

    billing_experiment = Experiment(
        user_id=owner.id,
        name="Billing support lab",
        description="Support response comparisons.",
        tags=["support"],
        is_archived=False,
    )
    outbound_experiment = Experiment(
        user_id=owner.id,
        name="Outbound follow-up",
        description="Sales outreach variants.",
        tags=["sales"],
        is_archived=False,
    )
    other_experiment = Experiment(
        user_id=other_user.id,
        name="Other user's lab",
        description=None,
        tags=["other"],
        is_archived=False,
    )
    session.add_all([billing_experiment, outbound_experiment, other_experiment])
    session.flush()

    billing_case = BenchloopTestCase(
        user_id=owner.id,
        experiment_id=billing_experiment.id,
        input_text="Refund the duplicate charge and confirm the timeline.",
        expected_output_text="Acknowledge the refund process.",
        notes="Priority refund case.",
        tags=["priority", "refund"],
    )
    escalation_case = BenchloopTestCase(
        user_id=owner.id,
        experiment_id=billing_experiment.id,
        input_text="Escalate the account lockout issue.",
        expected_output_text=None,
        notes="Security handoff.",
        tags=["priority", "security"],
    )
    outbound_case = BenchloopTestCase(
        user_id=owner.id,
        experiment_id=outbound_experiment.id,
        input_text="Write a warm follow-up after a demo.",
        expected_output_text="Friendly follow-up email.",
        notes=None,
        tags=["outbound"],
    )
    other_case = BenchloopTestCase(
        user_id=other_user.id,
        experiment_id=other_experiment.id,
        input_text="Other user test case.",
        expected_output_text=None,
        notes=None,
        tags=["other"],
    )
    session.add_all([billing_case, escalation_case, outbound_case, other_case])
    session.flush()

    refund_config = Config(
        user_id=owner.id,
        experiment_id=billing_experiment.id,
        name="Refund baseline",
        version_label="v1",
        description="Quick refund response.",
        provider="openai",
        model="gpt-4.1-mini",
        workflow_mode="single_shot",
        system_prompt="You are a billing assistant.",
        user_prompt_template="Respond to: {{input}}",
        temperature=0.2,
        max_output_tokens=256,
        top_p=0.9,
        context_bundle_id=None,
        tags=["priority", "baseline"],
        is_baseline=True,
    )
    escalation_config = Config(
        user_id=owner.id,
        experiment_id=billing_experiment.id,
        name="Escalation variant",
        version_label="v2",
        description="Route the issue carefully.",
        provider="openai",
        model="gpt-4.1-nano",
        workflow_mode="single_shot",
        system_prompt="You are a security assistant.",
        user_prompt_template="Handle escalation: {{input}}",
        temperature=0.1,
        max_output_tokens=180,
        top_p=None,
        context_bundle_id=None,
        tags=["priority", "analysis"],
        is_baseline=False,
    )
    outbound_config = Config(
        user_id=owner.id,
        experiment_id=outbound_experiment.id,
        name="Sales follow-up",
        version_label="v3",
        description="Warm outbound draft.",
        provider="anthropic",
        model="claude-3-5-sonnet",
        workflow_mode="single_shot",
        system_prompt="You are a concise sales assistant.",
        user_prompt_template="Follow up on: {{input}}",
        temperature=0.5,
        max_output_tokens=300,
        top_p=0.95,
        context_bundle_id=None,
        tags=["outbound"],
        is_baseline=False,
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
        user_prompt_template="Other: {{input}}",
        temperature=0.2,
        max_output_tokens=128,
        top_p=None,
        context_bundle_id=None,
        tags=["other"],
        is_baseline=False,
    )
    session.add_all([refund_config, escalation_config, outbound_config, other_config])
    session.flush()

    run_one = Run(
        user_id=owner.id,
        experiment_id=billing_experiment.id,
        test_case_id=billing_case.id,
        config_id=refund_config.id,
        credential_id=None,
        status="completed",
        provider="openai",
        model="gpt-4.1-mini-2025-04-14",
        workflow_mode="single_shot",
        config_snapshot_json=build_config_snapshot(
            refund_config,
            rendered_user_prompt="Respond to: Refund the duplicate charge and confirm the timeline.",
        ),
        input_snapshot_json=build_input_snapshot(billing_case),
        context_snapshot_json=None,
        output_text="Refund approved and timeline confirmed.",
        error_message=None,
        usage_input_tokens=120,
        usage_output_tokens=24,
        usage_total_tokens=144,
        latency_ms=240,
        estimated_cost_usd=0.0014,
        created_at=datetime(2025, 1, 10, 15, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 10, 15, 1, tzinfo=UTC),
        started_at=datetime(2025, 1, 10, 15, 0, tzinfo=UTC),
        finished_at=datetime(2025, 1, 10, 15, 0, 2, tzinfo=UTC),
    )
    run_two = Run(
        user_id=owner.id,
        experiment_id=billing_experiment.id,
        test_case_id=escalation_case.id,
        config_id=escalation_config.id,
        credential_id=None,
        status="completed",
        provider="openai",
        model="gpt-4.1-nano-2025-04-14",
        workflow_mode="single_shot",
        config_snapshot_json=build_config_snapshot(
            escalation_config,
            rendered_user_prompt="Handle escalation: Escalate the account lockout issue.",
        ),
        input_snapshot_json=build_input_snapshot(escalation_case),
        context_snapshot_json=build_context_snapshot(),
        output_text="Escalated to security with the required context.",
        error_message=None,
        usage_input_tokens=98,
        usage_output_tokens=20,
        usage_total_tokens=118,
        latency_ms=120,
        estimated_cost_usd=0.0008,
        created_at=datetime(2025, 1, 11, 9, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 11, 9, 1, tzinfo=UTC),
        started_at=datetime(2025, 1, 11, 9, 0, tzinfo=UTC),
        finished_at=datetime(2025, 1, 11, 9, 0, 1, tzinfo=UTC),
    )
    run_three = Run(
        user_id=owner.id,
        experiment_id=outbound_experiment.id,
        test_case_id=outbound_case.id,
        config_id=outbound_config.id,
        credential_id=None,
        status="failed",
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        workflow_mode="single_shot",
        config_snapshot_json=build_config_snapshot(
            outbound_config,
            rendered_user_prompt="Follow up on: Write a warm follow-up after a demo.",
        ),
        input_snapshot_json=build_input_snapshot(outbound_case),
        context_snapshot_json=None,
        output_text=None,
        error_message="Provider timed out.",
        usage_input_tokens=None,
        usage_output_tokens=None,
        usage_total_tokens=None,
        latency_ms=None,
        estimated_cost_usd=None,
        created_at=datetime(2025, 1, 12, 8, 30, tzinfo=UTC),
        updated_at=datetime(2025, 1, 12, 8, 31, tzinfo=UTC),
        started_at=datetime(2025, 1, 12, 8, 30, tzinfo=UTC),
        finished_at=datetime(2025, 1, 12, 8, 30, 5, tzinfo=UTC),
    )
    other_run = Run(
        user_id=other_user.id,
        experiment_id=other_experiment.id,
        test_case_id=other_case.id,
        config_id=other_config.id,
        credential_id=None,
        status="completed",
        provider="openai",
        model="gpt-4.1-mini-2025-04-14",
        workflow_mode="single_shot",
        config_snapshot_json=build_config_snapshot(
            other_config,
            rendered_user_prompt="Other: Other user test case.",
        ),
        input_snapshot_json=build_input_snapshot(other_case),
        context_snapshot_json=None,
        output_text="Other user's output.",
        error_message=None,
        usage_input_tokens=10,
        usage_output_tokens=5,
        usage_total_tokens=15,
        latency_ms=80,
        estimated_cost_usd=0.0002,
        created_at=datetime(2025, 1, 13, 10, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 13, 10, 1, tzinfo=UTC),
        started_at=datetime(2025, 1, 13, 10, 0, tzinfo=UTC),
        finished_at=datetime(2025, 1, 13, 10, 0, 1, tzinfo=UTC),
    )
    session.add_all([run_one, run_two, run_three, other_run])
    session.commit()

    return {
        "owner": owner,
        "billing_experiment": billing_experiment,
        "outbound_experiment": outbound_experiment,
        "refund_config": refund_config,
        "escalation_config": escalation_config,
        "other_run": other_run,
        "runs": [run_one, run_two, run_three],
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


def test_run_history_endpoint_requires_authentication() -> None:
    app = create_app()

    response = request(app, "GET", "/api/v1/runs")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "authentication_failed",
            "message": "Authentication required.",
            "details": None,
        }
    }


def test_run_detail_endpoint_requires_authentication() -> None:
    app = create_app()

    response = request(app, "GET", "/api/v1/runs/11111111-1111-1111-1111-111111111111")

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


def test_run_history_lists_only_owned_runs_with_experiment_context(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    with app.state.session_factory() as session:
        records = seed_run_history_records(session)

    response = request(
        app,
        "GET",
        "/api/v1/runs",
        headers=auth_headers(rsa_private_key),
    )

    assert response.status_code == 200
    payload = response.json()
    assert [run["id"] for run in payload] == [str(run.id) for run in reversed(records["runs"])]
    assert [run["experiment_name"] for run in payload] == [
        "Outbound follow-up",
        "Billing support lab",
        "Billing support lab",
    ]
    assert payload[0]["status"] == "failed"
    assert payload[0]["config_name"] == "Sales follow-up"
    assert payload[1]["test_case_input_preview"] == "Escalate the account lockout issue."
    assert payload[2]["provider"] == "openai"
    assert all(run["experiment_name"] != "Other user's lab" for run in payload)


def test_run_history_supports_filters_and_sorting(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    with app.state.session_factory() as session:
        records = seed_run_history_records(session)

    filtered_response = request(
        app,
        "GET",
        (
            f"/api/v1/runs?experiment_id={records['billing_experiment'].id}"
            f"&provider=openai&config_id={records['refund_config'].id}"
            "&tag=priority&created_from=2025-01-09T00:00:00Z&created_to=2025-01-10T23:59:59Z"
        ),
        headers=auth_headers(rsa_private_key),
    )

    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert [run["config_name"] for run in filtered_payload] == ["Refund baseline"]
    assert [run["status"] for run in filtered_payload] == ["completed"]

    sorted_response = request(
        app,
        "GET",
        (
            f"/api/v1/runs?experiment_id={records['billing_experiment'].id}"
            "&provider=openai&tag=priority&sort_by=latency_ms&sort_order=asc"
        ),
        headers=auth_headers(rsa_private_key),
    )

    assert sorted_response.status_code == 200
    sorted_payload = sorted_response.json()
    assert [run["config_name"] for run in sorted_payload] == [
        "Escalation variant",
        "Refund baseline",
    ]
    assert [run["latency_ms"] for run in sorted_payload] == [120, 240]


def test_run_detail_returns_owned_snapshot_and_execution_fields(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    with app.state.session_factory() as session:
        records = seed_run_history_records(session)

    response = request(
        app,
        "GET",
        f"/api/v1/runs/{records['runs'][1].id}",
        headers=auth_headers(rsa_private_key),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(records["runs"][1].id)
    assert payload["experiment_name"] == "Billing support lab"
    assert payload["status"] == "completed"
    assert payload["config_snapshot"]["name"] == "Escalation variant"
    assert payload["config_snapshot"]["rendered_user_prompt"] == (
        "Handle escalation: Escalate the account lockout issue."
    )
    assert payload["input_snapshot"]["input_text"] == "Escalate the account lockout issue."
    assert payload["context_snapshot"] == build_context_snapshot()
    assert payload["output_text"] == "Escalated to security with the required context."
    assert payload["usage_total_tokens"] == 118
    assert payload["latency_ms"] == 120
    assert payload["estimated_cost_usd"] == 0.0008


def test_run_detail_returns_failure_state_for_failed_runs(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    with app.state.session_factory() as session:
        records = seed_run_history_records(session)

    response = request(
        app,
        "GET",
        f"/api/v1/runs/{records['runs'][2].id}",
        headers=auth_headers(rsa_private_key),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["experiment_name"] == "Outbound follow-up"
    assert payload["output_text"] is None
    assert payload["error_message"] == "Provider timed out."
    assert payload["usage_total_tokens"] is None
    assert payload["estimated_cost_usd"] is None


def test_run_detail_hides_runs_owned_by_other_users(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    with app.state.session_factory() as session:
        records = seed_run_history_records(session)

    response = request(
        app,
        "GET",
        f"/api/v1/runs/{records['other_run'].id}",
        headers=auth_headers(rsa_private_key),
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Run was not found.",
            "details": None,
        }
    }


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
