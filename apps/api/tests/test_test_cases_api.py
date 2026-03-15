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
from benchloop_api.db.base import Base
from benchloop_api.experiments.models import Experiment
from benchloop_api.test_cases.models import TestCase as BenchloopCase
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
    return f"sqlite+pysqlite:///{tmp_path / 'benchloop-test-cases.db'}"


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


def test_test_case_endpoints_require_authentication() -> None:
    app = create_app()

    response = request(
        app,
        "GET",
        "/api/v1/experiments/11111111-1111-1111-1111-111111111111/test-cases",
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


def test_create_list_update_duplicate_and_delete_test_cases(
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
            "description": "Compare support prompts.",
            "tags": ["support"],
        },
    )
    experiment_id = create_experiment_response.json()["id"]

    create_test_case_response = request(
        app,
        "POST",
        f"/api/v1/experiments/{experiment_id}/test-cases",
        headers=auth_headers(rsa_private_key),
        json_body={
            "input_text": "A customer reports repeated billing failures.",
            "expected_output_text": "Ask for account details and offer troubleshooting steps.",
            "notes": "Baseline support scenario.",
            "tags": ["billing", "priority"],
        },
    )

    assert create_test_case_response.status_code == 201
    created_test_case = create_test_case_response.json()
    assert created_test_case["experiment_id"] == experiment_id
    assert created_test_case["input_text"] == "A customer reports repeated billing failures."
    assert created_test_case["expected_output_text"] == (
        "Ask for account details and offer troubleshooting steps."
    )
    assert created_test_case["notes"] == "Baseline support scenario."
    assert created_test_case["tags"] == ["billing", "priority"]

    list_response = request(
        app,
        "GET",
        f"/api/v1/experiments/{experiment_id}/test-cases",
        headers=auth_headers(rsa_private_key),
    )

    assert list_response.status_code == 200
    assert [test_case["id"] for test_case in list_response.json()] == [created_test_case["id"]]

    update_response = request(
        app,
        "PUT",
        f"/api/v1/experiments/{experiment_id}/test-cases/{created_test_case['id']}",
        headers=auth_headers(rsa_private_key),
        json_body={
            "input_text": "A customer reports card declines after replacing their card.",
            "expected_output_text": "Confirm billing details and advise retry timing.",
            "notes": "Updated scenario text.",
            "tags": ["billing", "retry"],
        },
    )

    assert update_response.status_code == 200
    updated_test_case = update_response.json()
    assert updated_test_case["input_text"] == (
        "A customer reports card declines after replacing their card."
    )
    assert updated_test_case["tags"] == ["billing", "retry"]

    duplicate_response = request(
        app,
        "POST",
        f"/api/v1/experiments/{experiment_id}/test-cases/{created_test_case['id']}/duplicate",
        headers=auth_headers(rsa_private_key),
    )

    assert duplicate_response.status_code == 201
    duplicated_test_case = duplicate_response.json()
    assert duplicated_test_case["id"] != created_test_case["id"]
    assert duplicated_test_case["experiment_id"] == experiment_id
    assert duplicated_test_case["input_text"] == updated_test_case["input_text"]
    assert duplicated_test_case["expected_output_text"] == updated_test_case["expected_output_text"]
    assert duplicated_test_case["notes"] == updated_test_case["notes"]
    assert duplicated_test_case["tags"] == updated_test_case["tags"]

    delete_response = request(
        app,
        "DELETE",
        f"/api/v1/experiments/{experiment_id}/test-cases/{created_test_case['id']}",
        headers=auth_headers(rsa_private_key),
    )

    assert delete_response.status_code == 204

    with app.state.session_factory() as session:
        remaining_test_cases = session.scalars(select(BenchloopCase)).all()

    assert [test_case.id for test_case in remaining_test_cases] == [
        UUID(duplicated_test_case["id"])
    ]


def test_test_case_routes_enforce_experiment_and_user_scope(
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

        owner_test_case = BenchloopCase(
            id=UUID("3841f9ef-4086-49dd-9329-cf4b0f8c7846"),
            user_id=owner.id,
            experiment_id=second_owner_experiment.id,
            input_text="Owner-only scenario",
            expected_output_text="Owner-only answer",
            notes="Owner note",
            tags=["owner"],
        )
        other_test_case = BenchloopCase(
            id=UUID("4c11f1ca-6642-4da2-84d3-0e0db8e42e68"),
            user_id=other_user.id,
            experiment_id=other_experiment.id,
            input_text="Other user scenario",
            expected_output_text="Other answer",
            notes="Other note",
            tags=["other"],
        )
        session.add_all([owner_test_case, other_test_case])
        session.commit()

    cross_user_list_response = request(
        app,
        "GET",
        "/api/v1/experiments/7b1ce46e-b16e-422d-bbdf-e18af2dc6e77/test-cases",
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
        "/test-cases/3841f9ef-4086-49dd-9329-cf4b0f8c7846",
        headers=auth_headers(rsa_private_key, subject="user_123"),
        json_body={
            "input_text": "Owner-only scenario revised",
            "expected_output_text": "Owner-only answer revised",
            "notes": "Owner note revised",
            "tags": ["owner", "revised"],
        },
    )

    assert wrong_experiment_response.status_code == 404
    assert wrong_experiment_response.json() == {
        "error": {
            "code": "not_found",
            "message": "Test case was not found.",
            "details": None,
        }
    }

    cross_user_duplicate_response = request(
        app,
        "POST",
        "/api/v1/experiments/ec5b2d79-c5af-4f9d-b0f6-57f1eb04c693"
        "/test-cases/4c11f1ca-6642-4da2-84d3-0e0db8e42e68/duplicate",
        headers=auth_headers(rsa_private_key, subject="user_123"),
    )

    assert cross_user_duplicate_response.status_code == 404
    assert cross_user_duplicate_response.json() == {
        "error": {
            "code": "not_found",
            "message": "Test case was not found.",
            "details": None,
        }
    }
