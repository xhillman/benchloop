import asyncio
import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from benchloop_api.app import create_app
from benchloop_api.auth.service import ClerkJwtVerifier
from benchloop_api.configs.models import Config as BenchloopConfig
from benchloop_api.context_bundles.models import ContextBundle
from benchloop_api.db.base import Base


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
    return f"sqlite+pysqlite:///{tmp_path / 'benchloop-context-bundles.db'}"


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


def test_context_bundle_endpoints_require_authentication() -> None:
    app = create_app()

    response = request(
        app,
        "GET",
        "/api/v1/experiments/11111111-1111-1111-1111-111111111111/context-bundles",
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


def test_create_list_update_and_delete_context_bundles(
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
            "description": "Compare support flows.",
            "tags": ["support"],
        },
    )
    experiment_id = create_experiment_response.json()["id"]

    create_response = request(
        app,
        "POST",
        f"/api/v1/experiments/{experiment_id}/context-bundles",
        headers=auth_headers(rsa_private_key),
        json_body={
            "name": "Refund policy",
            "content_text": "Refunds clear within five business days for duplicate charges.",
            "notes": "Latest approved billing guidance.",
        },
    )

    assert create_response.status_code == 201
    created_bundle = create_response.json()
    assert created_bundle["experiment_id"] == experiment_id
    assert created_bundle["name"] == "Refund policy"
    assert created_bundle["content_text"].startswith("Refunds clear")

    list_response = request(
        app,
        "GET",
        f"/api/v1/experiments/{experiment_id}/context-bundles",
        headers=auth_headers(rsa_private_key),
    )

    assert list_response.status_code == 200
    assert list_response.json() == [created_bundle]

    update_response = request(
        app,
        "PUT",
        f"/api/v1/experiments/{experiment_id}/context-bundles/{created_bundle['id']}",
        headers=auth_headers(rsa_private_key),
        json_body={
            "name": "Refund policy revised",
            "content_text": "Refunds clear within three business days for duplicate charges.",
            "notes": "Updated after finance review.",
        },
    )

    assert update_response.status_code == 200
    updated_bundle = update_response.json()
    assert updated_bundle["name"] == "Refund policy revised"
    assert updated_bundle["notes"] == "Updated after finance review."

    delete_response = request(
        app,
        "DELETE",
        f"/api/v1/experiments/{experiment_id}/context-bundles/{created_bundle['id']}",
        headers=auth_headers(rsa_private_key),
    )

    assert delete_response.status_code == 204

    with app.state.session_factory() as session:
        remaining_bundles = session.scalars(select(ContextBundle)).all()

    assert remaining_bundles == []


def test_deleting_context_bundle_clears_attached_config_reference(
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
            "description": "Compare support flows.",
            "tags": ["support"],
        },
    )
    experiment_id = create_experiment_response.json()["id"]

    create_bundle_response = request(
        app,
        "POST",
        f"/api/v1/experiments/{experiment_id}/context-bundles",
        headers=auth_headers(rsa_private_key),
        json_body={
            "name": "Billing policy",
            "content_text": "Always mention the refund timeline.",
            "notes": None,
        },
    )
    context_bundle_id = create_bundle_response.json()["id"]

    create_config_response = request(
        app,
        "POST",
        f"/api/v1/experiments/{experiment_id}/configs",
        headers=auth_headers(rsa_private_key),
        json_body={
            "name": "Context answer",
            "version_label": "v1",
            "description": "Context-backed support reply.",
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "workflow_mode": "prompt_plus_context",
            "system_prompt": "Use the supplied policy.",
            "user_prompt_template": "Answer with context: {{ input_text }} / {{ context }}",
            "temperature": 0.2,
            "max_output_tokens": 300,
            "top_p": 0.9,
            "context_bundle_id": context_bundle_id,
            "tags": ["context"],
            "is_baseline": False,
        },
    )

    assert create_config_response.status_code == 201
    assert create_config_response.json()["context_bundle_id"] == context_bundle_id

    delete_response = request(
        app,
        "DELETE",
        f"/api/v1/experiments/{experiment_id}/context-bundles/{context_bundle_id}",
        headers=auth_headers(rsa_private_key),
    )

    assert delete_response.status_code == 204

    with app.state.session_factory() as session:
        config = session.scalar(select(BenchloopConfig))

    assert config is not None
    assert config.context_bundle_id is None


def test_context_bundle_routes_enforce_experiment_and_user_scope(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    owner_experiment_response = request(
        app,
        "POST",
        "/api/v1/experiments",
        headers=auth_headers(rsa_private_key, subject="user_123"),
        json_body={
            "name": "Owner experiment",
            "description": "Owner lane.",
            "tags": ["owner"],
        },
    )
    owner_experiment_id = owner_experiment_response.json()["id"]

    second_experiment_response = request(
        app,
        "POST",
        "/api/v1/experiments",
        headers=auth_headers(rsa_private_key, subject="user_123"),
        json_body={
            "name": "Second owner experiment",
            "description": "Second lane.",
            "tags": ["owner"],
        },
    )
    second_experiment_id = second_experiment_response.json()["id"]

    other_experiment_response = request(
        app,
        "POST",
        "/api/v1/experiments",
        headers=auth_headers(rsa_private_key, subject="user_456"),
        json_body={
            "name": "Other experiment",
            "description": "Other lane.",
            "tags": ["other"],
        },
    )
    other_experiment_id = other_experiment_response.json()["id"]

    create_owner_bundle_response = request(
        app,
        "POST",
        f"/api/v1/experiments/{second_experiment_id}/context-bundles",
        headers=auth_headers(rsa_private_key, subject="user_123"),
        json_body={
            "name": "Owner policy",
            "content_text": "Owner-only context.",
            "notes": None,
        },
    )
    owner_bundle_id = create_owner_bundle_response.json()["id"]

    create_other_bundle_response = request(
        app,
        "POST",
        f"/api/v1/experiments/{other_experiment_id}/context-bundles",
        headers=auth_headers(rsa_private_key, subject="user_456"),
        json_body={
            "name": "Other policy",
            "content_text": "Other-user context.",
            "notes": None,
        },
    )
    other_bundle_id = create_other_bundle_response.json()["id"]

    cross_user_list_response = request(
        app,
        "GET",
        f"/api/v1/experiments/{other_experiment_id}/context-bundles",
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
        f"/api/v1/experiments/{owner_experiment_id}/context-bundles/{owner_bundle_id}",
        headers=auth_headers(rsa_private_key, subject="user_123"),
        json_body={
            "name": "Wrong experiment",
            "content_text": "Should not resolve.",
            "notes": None,
        },
    )

    assert wrong_experiment_response.status_code == 404
    assert wrong_experiment_response.json() == {
        "error": {
            "code": "not_found",
            "message": "Context bundle was not found.",
            "details": None,
        }
    }

    cross_user_delete_response = request(
        app,
        "DELETE",
        f"/api/v1/experiments/{owner_experiment_id}/context-bundles/{other_bundle_id}",
        headers=auth_headers(rsa_private_key, subject="user_123"),
    )

    assert cross_user_delete_response.status_code == 404
    assert cross_user_delete_response.json() == {
        "error": {
            "code": "not_found",
            "message": "Context bundle was not found.",
            "details": None,
        }
    }
