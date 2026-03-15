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
    return f"sqlite+pysqlite:///{tmp_path / 'benchloop-experiments.db'}"


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


def test_experiment_endpoints_require_authentication() -> None:
    app = create_app()

    response = request(app, "GET", "/api/v1/experiments")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "authentication_failed",
            "message": "Authentication required.",
            "details": None,
        }
    }


def test_create_list_and_filter_experiments(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    create_first_response = request(
        app,
        "POST",
        "/api/v1/experiments",
        headers=auth_headers(rsa_private_key),
        json_body={
            "name": "Support triage",
            "description": "Compare prompt variants for inbound support tickets.",
            "tags": ["support", "triage"],
        },
    )

    assert create_first_response.status_code == 201
    first_experiment = create_first_response.json()
    assert first_experiment["name"] == "Support triage"
    assert first_experiment["description"] == "Compare prompt variants for inbound support tickets."
    assert first_experiment["tags"] == ["support", "triage"]
    assert first_experiment["is_archived"] is False

    create_second_response = request(
        app,
        "POST",
        "/api/v1/experiments",
        headers=auth_headers(rsa_private_key),
        json_body={
            "name": "Sales follow-up",
            "description": "Test warmer reply structures.",
            "tags": ["sales"],
        },
    )

    assert create_second_response.status_code == 201

    list_response = request(
        app,
        "GET",
        "/api/v1/experiments",
        headers=auth_headers(rsa_private_key),
    )

    assert list_response.status_code == 200
    listed_experiments = list_response.json()
    assert [experiment["name"] for experiment in listed_experiments] == [
        "Sales follow-up",
        "Support triage",
    ]

    search_response = request(
        app,
        "GET",
        "/api/v1/experiments?search=support",
        headers=auth_headers(rsa_private_key),
    )

    assert search_response.status_code == 200
    assert [experiment["name"] for experiment in search_response.json()] == ["Support triage"]

    tag_response = request(
        app,
        "GET",
        "/api/v1/experiments?tag=triage",
        headers=auth_headers(rsa_private_key),
    )

    assert tag_response.status_code == 200
    assert [experiment["name"] for experiment in tag_response.json()] == ["Support triage"]

    multi_tag_response = request(
        app,
        "GET",
        "/api/v1/experiments?tag=sales&tag=triage",
        headers=auth_headers(rsa_private_key),
    )

    assert multi_tag_response.status_code == 200
    assert [experiment["name"] for experiment in multi_tag_response.json()] == [
        "Sales follow-up",
        "Support triage",
    ]


def test_read_and_update_experiment_are_scoped_to_authenticated_user(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    with app.state.session_factory() as session:
        owner = User(clerk_user_id="user_123")
        other_user = User(clerk_user_id="user_456")
        session.add_all([owner, other_user])
        session.flush()
        session.add_all(
            [
                Experiment(
                    id=UUID("b955dacc-2d44-453d-a88c-2e49f7a4f7c2"),
                    user_id=owner.id,
                    name="Owner experiment",
                    description="Owner description",
                    tags=["alpha"],
                ),
                Experiment(
                    id=UUID("65382a2a-d8b0-4d9f-8cb8-53608f6eec6b"),
                    user_id=other_user.id,
                    name="Other experiment",
                    description="Other description",
                    tags=["beta"],
                ),
            ]
        )
        session.commit()

    read_response = request(
        app,
        "GET",
        "/api/v1/experiments/b955dacc-2d44-453d-a88c-2e49f7a4f7c2",
        headers=auth_headers(rsa_private_key, subject="user_123"),
    )

    assert read_response.status_code == 200
    assert read_response.json()["name"] == "Owner experiment"

    update_response = request(
        app,
        "PUT",
        "/api/v1/experiments/b955dacc-2d44-453d-a88c-2e49f7a4f7c2",
        headers=auth_headers(rsa_private_key, subject="user_123"),
        json_body={
            "name": "Owner experiment revised",
            "description": "Updated notes",
            "tags": ["alpha", "gamma"],
            "is_archived": True,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "id": "b955dacc-2d44-453d-a88c-2e49f7a4f7c2",
        "name": "Owner experiment revised",
        "description": "Updated notes",
        "tags": ["alpha", "gamma"],
        "is_archived": True,
        "created_at": update_response.json()["created_at"],
        "updated_at": update_response.json()["updated_at"],
    }

    cross_user_response = request(
        app,
        "GET",
        "/api/v1/experiments/65382a2a-d8b0-4d9f-8cb8-53608f6eec6b",
        headers=auth_headers(rsa_private_key, subject="user_123"),
    )

    assert cross_user_response.status_code == 404
    assert cross_user_response.json() == {
        "error": {
            "code": "not_found",
            "message": "Experiment was not found.",
            "details": None,
        }
    }


def test_archived_experiments_are_excluded_by_default_and_can_be_deleted(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    create_response = request(
        app,
        "POST",
        "/api/v1/experiments",
        headers=auth_headers(rsa_private_key),
        json_body={
            "name": "Archive candidate",
            "description": None,
            "tags": ["cleanup"],
        },
    )
    experiment_id = create_response.json()["id"]

    archive_response = request(
        app,
        "PUT",
        f"/api/v1/experiments/{experiment_id}",
        headers=auth_headers(rsa_private_key),
        json_body={
            "name": "Archive candidate",
            "description": None,
            "tags": ["cleanup"],
            "is_archived": True,
        },
    )

    assert archive_response.status_code == 200
    assert archive_response.json()["is_archived"] is True

    default_list_response = request(
        app,
        "GET",
        "/api/v1/experiments",
        headers=auth_headers(rsa_private_key),
    )
    assert default_list_response.status_code == 200
    assert default_list_response.json() == []

    archived_list_response = request(
        app,
        "GET",
        "/api/v1/experiments?include_archived=true",
        headers=auth_headers(rsa_private_key),
    )
    assert archived_list_response.status_code == 200
    assert [experiment["name"] for experiment in archived_list_response.json()] == [
        "Archive candidate"
    ]

    delete_response = request(
        app,
        "DELETE",
        f"/api/v1/experiments/{experiment_id}",
        headers=auth_headers(rsa_private_key),
    )
    assert delete_response.status_code == 204

    with app.state.session_factory() as session:
        experiments = session.scalars(select(Experiment)).all()

    assert experiments == []

    missing_response = request(
        app,
        "GET",
        f"/api/v1/experiments/{experiment_id}",
        headers=auth_headers(rsa_private_key),
    )
    assert missing_response.status_code == 404
