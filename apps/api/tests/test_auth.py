import asyncio
import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from benchloop_api.app import create_app
from benchloop_api.auth.service import ClerkJwtVerifier


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


def build_signed_token(private_key, *, kid: str = "test-key") -> str:
    now = datetime.now(tz=UTC)
    return jwt.encode(
        {
            "sub": "user_123",
            "iss": "https://clerk.example.com",
            "aud": "benchloop",
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=5),
        },
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


def test_protected_endpoint_returns_authenticated_subject(rsa_private_key) -> None:
    app = create_app(
        {
            "clerk_jwks_url": "https://clerk.example.com/.well-known/jwks.json",
            "clerk_jwt_issuer": "https://clerk.example.com",
            "clerk_jwt_audience": "benchloop",
        }
    )
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
