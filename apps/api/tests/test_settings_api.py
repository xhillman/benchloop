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
from benchloop_api.settings.models import UserSettings
from benchloop_api.users.models import User


def request(
    app,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, object | None] | None = None,
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
    return f"sqlite+pysqlite:///{tmp_path / 'benchloop-settings.db'}"


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


def test_settings_endpoints_require_authentication() -> None:
    app = create_app()

    response = request(app, "GET", "/api/v1/settings")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "authentication_failed",
            "message": "Authentication required.",
            "details": None,
        }
    }


def test_read_settings_returns_null_defaults_when_user_has_no_settings(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    response = request(
        app,
        "GET",
        "/api/v1/settings",
        headers=auth_headers(rsa_private_key),
    )

    assert response.status_code == 200
    assert response.json() == {
        "default_provider": None,
        "default_model": None,
        "timezone": None,
    }


def test_update_settings_creates_row_and_allows_clearing_values(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    create_response = request(
        app,
        "PUT",
        "/api/v1/settings",
        headers=auth_headers(rsa_private_key),
        json_body={
            "default_provider": "openai",
            "default_model": "gpt-4o-mini",
            "timezone": "America/Chicago",
        },
    )

    assert create_response.status_code == 200
    assert create_response.json() == {
        "default_provider": "openai",
        "default_model": "gpt-4o-mini",
        "timezone": "America/Chicago",
    }

    clear_response = request(
        app,
        "PUT",
        "/api/v1/settings",
        headers=auth_headers(rsa_private_key),
        json_body={
            "default_provider": "anthropic",
            "default_model": None,
            "timezone": "UTC",
        },
    )

    assert clear_response.status_code == 200
    assert clear_response.json() == {
        "default_provider": "anthropic",
        "default_model": None,
        "timezone": "UTC",
    }

    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.clerk_user_id == "user_123"))
        settings = session.scalars(select(UserSettings)).all()

    assert user is not None
    assert len(settings) == 1
    assert settings[0].user_id == user.id
    assert settings[0].default_provider == "anthropic"
    assert settings[0].default_model is None
    assert settings[0].timezone == "UTC"


def test_update_settings_is_scoped_to_authenticated_user(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    with app.state.session_factory() as session:
        owner = User(clerk_user_id="user_123")
        other_user = User(clerk_user_id="user_456")
        session.add_all([owner, other_user])
        session.flush()
        session.add(
            UserSettings(
                user_id=other_user.id,
                default_provider="openai",
                default_model="gpt-4.1",
                timezone="America/New_York",
            )
        )
        session.commit()

    response = request(
        app,
        "PUT",
        "/api/v1/settings",
        headers=auth_headers(rsa_private_key, subject="user_123"),
        json_body={
            "default_provider": "anthropic",
            "default_model": "claude-3-5-sonnet",
            "timezone": "UTC",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "default_provider": "anthropic",
        "default_model": "claude-3-5-sonnet",
        "timezone": "UTC",
    }

    with app.state.session_factory() as session:
        settings = session.scalars(select(UserSettings).order_by(UserSettings.user_id)).all()

    assert len(settings) == 2
    by_user_id = {setting.user_id: setting for setting in settings}
    owner_settings = by_user_id[owner.id]
    other_settings = by_user_id[other_user.id]

    assert owner_settings.default_provider == "anthropic"
    assert owner_settings.default_model == "claude-3-5-sonnet"
    assert owner_settings.timezone == "UTC"
    assert other_settings.default_provider == "openai"
    assert other_settings.default_model == "gpt-4.1"
    assert other_settings.timezone == "America/New_York"
