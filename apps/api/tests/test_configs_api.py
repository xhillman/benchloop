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
from benchloop_api.configs.models import Config as BenchloopConfig
from benchloop_api.db.base import Base
from benchloop_api.experiments.models import Experiment
from benchloop_api.users.models import User


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
    return f"sqlite+pysqlite:///{tmp_path / 'benchloop-configs.db'}"


def build_test_app(rsa_private_key, sqlite_database_url):
    app = create_app(
        {
            "database_url": sqlite_database_url,
            "clerk_jwks_url": "https://clerk.example.com/.well-known/jwks.json",
            "clerk_jwt_issuer": "https://clerk.example.com",
            "clerk_jwt_audience": "benchloop",
        }
    )
    Base.metadata.create_all(app.state.db_engine)
    app.state.auth_verifier = ClerkJwtVerifier(
        app.state.settings,
        transport=build_jwks_transport(rsa_private_key.public_key()),
    )
    return app


def auth_headers(rsa_private_key, *, subject: str = "user_123") -> dict[str, str]:
    token = build_signed_token(rsa_private_key, subject=subject)
    return {"Authorization": f"Bearer {token}"}


def test_config_endpoints_require_authentication() -> None:
    app = create_app()

    response = request(
        app,
        "GET",
        "/api/v1/experiments/11111111-1111-1111-1111-111111111111/configs",
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


def test_create_list_update_clone_mark_baseline_and_delete_configs(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    create_experiment_response = request(
        app,
        "POST",
        "/api/v1/experiments",
        headers=auth_headers(rsa_private_key),
        json_body={
            "name": "Support triage",
            "description": "Compare support configs.",
            "tags": ["support"],
        },
    )
    experiment_id = create_experiment_response.json()["id"]

    create_first_response = request(
        app,
        "POST",
        f"/api/v1/experiments/{experiment_id}/configs",
        headers=auth_headers(rsa_private_key),
        json_body={
            "name": "Direct answer",
            "version_label": "v1",
            "description": "Fast baseline answer.",
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "workflow_mode": "single_shot",
            "system_prompt": "You are a support assistant.",
            "user_prompt_template": "Reply to this ticket: {{ input_text }}",
            "temperature": 0.2,
            "max_output_tokens": 400,
            "top_p": 0.9,
            "context_bundle_id": None,
            "tags": ["cheap", "fast"],
            "is_baseline": False,
        },
    )

    assert create_first_response.status_code == 201
    created_first = create_first_response.json()
    assert created_first["experiment_id"] == experiment_id
    assert created_first["version_label"] == "v1"
    assert created_first["provider"] == "openai"
    assert created_first["model"] == "gpt-4.1-mini"
    assert created_first["workflow_mode"] == "single_shot"
    assert created_first["is_baseline"] is False

    create_second_response = request(
        app,
        "POST",
        f"/api/v1/experiments/{experiment_id}/configs",
        headers=auth_headers(rsa_private_key),
        json_body={
            "name": "Direct answer",
            "version_label": "v2",
            "description": "Stronger answer variant.",
            "provider": "anthropic",
            "model": "claude-3-5-sonnet",
            "workflow_mode": "prompt_plus_context",
            "system_prompt": "You are a precise support assistant.",
            "user_prompt_template": "Resolve this ticket with context: {{ input_text }}",
            "temperature": 0.4,
            "max_output_tokens": 500,
            "top_p": None,
            "context_bundle_id": None,
            "tags": ["thorough"],
            "is_baseline": True,
        },
    )

    assert create_second_response.status_code == 201
    created_second = create_second_response.json()
    assert created_second["is_baseline"] is True

    list_response = request(
        app,
        "GET",
        f"/api/v1/experiments/{experiment_id}/configs",
        headers=auth_headers(rsa_private_key),
    )

    assert list_response.status_code == 200
    listed_configs = list_response.json()
    assert [config["id"] for config in listed_configs] == [
        created_second["id"],
        created_first["id"],
    ]

    update_response = request(
        app,
        "PUT",
        f"/api/v1/experiments/{experiment_id}/configs/{created_first['id']}",
        headers=auth_headers(rsa_private_key),
        json_body={
            "name": "Direct answer revised",
            "version_label": "v1",
            "description": "Tighter support reply.",
            "provider": "openai",
            "model": "gpt-4.1",
            "workflow_mode": "single_shot",
            "system_prompt": "You are a concise support assistant.",
            "user_prompt_template": "Reply clearly to this ticket: {{ input_text }}",
            "temperature": 0.1,
            "max_output_tokens": 350,
            "top_p": 0.8,
            "context_bundle_id": None,
            "tags": ["cheap", "revised"],
            "is_baseline": False,
        },
    )

    assert update_response.status_code == 200
    updated_first = update_response.json()
    assert updated_first["name"] == "Direct answer revised"
    assert updated_first["model"] == "gpt-4.1"
    assert updated_first["tags"] == ["cheap", "revised"]

    clone_response = request(
        app,
        "POST",
        f"/api/v1/experiments/{experiment_id}/configs/{created_first['id']}/clone",
        headers=auth_headers(rsa_private_key),
    )

    assert clone_response.status_code == 201
    cloned_config = clone_response.json()
    assert cloned_config["id"] != created_first["id"]
    assert cloned_config["name"] == updated_first["name"]
    assert cloned_config["version_label"] == "v1-copy"
    assert cloned_config["provider"] == updated_first["provider"]
    assert cloned_config["model"] == updated_first["model"]
    assert cloned_config["workflow_mode"] == updated_first["workflow_mode"]
    assert cloned_config["system_prompt"] == updated_first["system_prompt"]
    assert cloned_config["user_prompt_template"] == updated_first["user_prompt_template"]
    assert cloned_config["temperature"] == updated_first["temperature"]
    assert cloned_config["max_output_tokens"] == updated_first["max_output_tokens"]
    assert cloned_config["top_p"] == updated_first["top_p"]
    assert cloned_config["tags"] == updated_first["tags"]
    assert cloned_config["is_baseline"] is False

    mark_baseline_response = request(
        app,
        "POST",
        f"/api/v1/experiments/{experiment_id}/configs/{cloned_config['id']}/baseline",
        headers=auth_headers(rsa_private_key),
    )

    assert mark_baseline_response.status_code == 200
    assert mark_baseline_response.json()["is_baseline"] is True

    refreshed_list_response = request(
        app,
        "GET",
        f"/api/v1/experiments/{experiment_id}/configs",
        headers=auth_headers(rsa_private_key),
    )

    assert refreshed_list_response.status_code == 200
    refreshed_configs = refreshed_list_response.json()
    assert refreshed_configs[0]["id"] == cloned_config["id"]
    assert refreshed_configs[0]["is_baseline"] is True
    assert next(
        config for config in refreshed_configs if config["id"] == created_second["id"]
    )["is_baseline"] is False

    delete_response = request(
        app,
        "DELETE",
        f"/api/v1/experiments/{experiment_id}/configs/{created_first['id']}",
        headers=auth_headers(rsa_private_key),
    )

    assert delete_response.status_code == 204

    with app.state.session_factory() as session:
        remaining_configs = session.scalars(
            select(BenchloopConfig).order_by(BenchloopConfig.created_at.asc())
        ).all()

    assert [config.id for config in remaining_configs] == [
        UUID(created_second["id"]),
        UUID(cloned_config["id"]),
    ]


def test_config_routes_enforce_experiment_and_user_scope(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    with app.state.session_factory() as session:
        owner = User(clerk_user_id="user_123")
        other_user = User(clerk_user_id="user_456")
        session.add_all([owner, other_user])
        session.flush()

        owner_experiment = Experiment(
            id=UUID("ec5b2d79-c5af-4f9d-b0f6-57f1eb04c693"),
            user_id=owner.id,
            name="Owner experiment",
            description="Owner experiment",
            tags=["owner"],
        )
        second_owner_experiment = Experiment(
            id=UUID("b2c8d2f0-8516-4d9b-87f1-d3b2914b87ed"),
            user_id=owner.id,
            name="Second owner experiment",
            description="Second owner experiment",
            tags=["owner"],
        )
        other_experiment = Experiment(
            id=UUID("7b1ce46e-b16e-422d-bbdf-e18af2dc6e77"),
            user_id=other_user.id,
            name="Other experiment",
            description="Other experiment",
            tags=["other"],
        )
        session.add_all([owner_experiment, second_owner_experiment, other_experiment])
        session.flush()

        owner_config = BenchloopConfig(
            id=UUID("3841f9ef-4086-49dd-9329-cf4b0f8c7846"),
            user_id=owner.id,
            experiment_id=second_owner_experiment.id,
            name="Owner config",
            version_label="v1",
            description="Owner config",
            provider="openai",
            model="gpt-4.1-mini",
            workflow_mode="single_shot",
            system_prompt="Owner system",
            user_prompt_template="Owner prompt {{ input_text }}",
            temperature=0.2,
            max_output_tokens=300,
            top_p=0.9,
            context_bundle_id=None,
            tags=["owner"],
            is_baseline=True,
        )
        other_config = BenchloopConfig(
            id=UUID("4c11f1ca-6642-4da2-84d3-0e0db8e42e68"),
            user_id=other_user.id,
            experiment_id=other_experiment.id,
            name="Other config",
            version_label="v1",
            description="Other config",
            provider="anthropic",
            model="claude-3-5-sonnet",
            workflow_mode="single_shot",
            system_prompt="Other system",
            user_prompt_template="Other prompt {{ input_text }}",
            temperature=0.4,
            max_output_tokens=400,
            top_p=None,
            context_bundle_id=None,
            tags=["other"],
            is_baseline=False,
        )
        session.add_all([owner_config, other_config])
        session.commit()

    cross_user_list_response = request(
        app,
        "GET",
        "/api/v1/experiments/7b1ce46e-b16e-422d-bbdf-e18af2dc6e77/configs",
        headers=auth_headers(rsa_private_key, subject="user_123"),
    )

    assert cross_user_list_response.status_code == 404
    assert cross_user_list_response.json() == {
        "error": {
            "code": "not_found",
            "message": "Experiment was not found.",
            "details": None,
        }
    }

    wrong_experiment_response = request(
        app,
        "PUT",
        "/api/v1/experiments/ec5b2d79-c5af-4f9d-b0f6-57f1eb04c693"
        "/configs/3841f9ef-4086-49dd-9329-cf4b0f8c7846",
        headers=auth_headers(rsa_private_key, subject="user_123"),
        json_body={
            "name": "Owner config revised",
            "version_label": "v1",
            "description": "Owner config revised",
            "provider": "openai",
            "model": "gpt-4.1",
            "workflow_mode": "single_shot",
            "system_prompt": "Owner system revised",
            "user_prompt_template": "Owner prompt revised {{ input_text }}",
            "temperature": 0.1,
            "max_output_tokens": 256,
            "top_p": 0.8,
            "context_bundle_id": None,
            "tags": ["owner", "revised"],
            "is_baseline": False,
        },
    )

    assert wrong_experiment_response.status_code == 404
    assert wrong_experiment_response.json() == {
        "error": {
            "code": "not_found",
            "message": "Config was not found.",
            "details": None,
        }
    }

    cross_user_clone_response = request(
        app,
        "POST",
        "/api/v1/experiments/ec5b2d79-c5af-4f9d-b0f6-57f1eb04c693"
        "/configs/4c11f1ca-6642-4da2-84d3-0e0db8e42e68/clone",
        headers=auth_headers(rsa_private_key, subject="user_123"),
    )

    assert cross_user_clone_response.status_code == 404
    assert cross_user_clone_response.json() == {
        "error": {
            "code": "not_found",
            "message": "Config was not found.",
            "details": None,
        }
    }
