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
from benchloop_api.db.base import Base
from benchloop_api.users.models import User


def request(
    app,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, headers=headers)

    return asyncio.run(run_request())


@pytest.fixture()
def rsa_private_key() -> Generator:
    yield rsa.generate_private_key(public_exponent=65537, key_size=2048)


def build_signed_token(
    private_key,
    *,
    kid: str = "test-key",
    subject: str = "user_123",
    email: str | None = None,
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
    if email is not None:
        claims["email"] = email

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
    return f"sqlite+pysqlite:///{tmp_path / 'benchloop.db'}"


def test_protected_endpoint_rejects_missing_bearer_token() -> None:
    app = create_app()

    response = request(app, "GET", "/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "authentication_failed",
            "message": "Authentication required.",
            "details": None,
        }
    }


def test_protected_endpoint_rejects_invalid_bearer_token() -> None:
    app = create_app()

    response = request(
        app,
        "GET",
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
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


def test_protected_endpoint_returns_authenticated_subject(
    rsa_private_key,
    sqlite_database_url,
) -> None:
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
    token = build_signed_token(rsa_private_key)

    response = request(
        app,
        "GET",
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "external_user_id": "user_123",
    }


def test_first_authenticated_request_creates_internal_user(
    rsa_private_key,
    sqlite_database_url,
) -> None:
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
    token = build_signed_token(rsa_private_key, email="first@example.com")

    response = request(
        app,
        "GET",
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    with app.state.session_factory() as session:
        users = session.scalars(select(User)).all()

    assert len(users) == 1
    assert users[0].clerk_user_id == "user_123"
    assert users[0].email == "first@example.com"


def test_authenticated_request_updates_existing_internal_user_email(
    rsa_private_key,
    sqlite_database_url,
) -> None:
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

    first_token = build_signed_token(rsa_private_key, email="first@example.com")
    second_token = build_signed_token(rsa_private_key, email="updated@example.com")

    first_response = request(
        app,
        "GET",
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    second_response = request(
        app,
        "GET",
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    with app.state.session_factory() as session:
        users = session.scalars(select(User)).all()

    assert len(users) == 1
    assert users[0].clerk_user_id == "user_123"
    assert users[0].email == "updated@example.com"
