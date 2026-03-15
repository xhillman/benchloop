import asyncio
import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from benchloop_api.app import create_app
from benchloop_api.auth.service import ClerkJwtVerifier
from benchloop_api.db.base import Base
from benchloop_api.settings.models import UserProviderCredential, UserSettings
from benchloop_api.settings.validation import (
    ProviderCredentialValidationError,
    UnsupportedCredentialProviderError,
)
from benchloop_api.users.models import User


class StubProviderCredentialValidator:
    def __init__(self, *, outcomes: dict[str, str | Exception]) -> None:
        self._outcomes = outcomes
        self.calls: list[dict[str, str]] = []

    async def validate(self, *, provider: str, api_key: str) -> SimpleNamespace:
        self.calls.append({"provider": provider, "api_key": api_key})
        outcome = self._outcomes[provider]
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(status=outcome)


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


def test_credential_endpoints_require_authentication() -> None:
    app = create_app()

    response = request(app, "GET", "/api/v1/settings/credentials")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "authentication_failed",
            "message": "Authentication required.",
            "details": None,
        }
    }


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("GET", "/api/v1/settings", None),
        (
            "PUT",
            "/api/v1/settings",
            {
                "default_provider": "openai",
                "default_model": "gpt-4o-mini",
                "timezone": "UTC",
            },
        ),
        ("GET", "/api/v1/settings/credentials", None),
        (
            "POST",
            "/api/v1/settings/credentials",
            {
                "provider": "openai",
                "api_key": "sk-test-secret-1234",
                "key_label": "Primary key",
            },
        ),
        (
            "PUT",
            f"/api/v1/settings/credentials/{uuid4()}",
            {
                "api_key": "sk-test-secret-5678",
                "key_label": "Rotated key",
            },
        ),
        ("DELETE", f"/api/v1/settings/credentials/{uuid4()}", None),
        ("POST", f"/api/v1/settings/credentials/{uuid4()}/validate", None),
    ],
)
def test_all_settings_routes_require_authentication(
    method: str,
    path: str,
    json_body: dict[str, object | None] | None,
) -> None:
    app = create_app()

    response = request(
        app,
        method,
        path,
        json_body=json_body,
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


def test_create_and_list_credentials_return_masked_metadata_only(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    create_response = request(
        app,
        "POST",
        "/api/v1/settings/credentials",
        headers=auth_headers(rsa_private_key),
        json_body={
            "provider": "openai",
            "api_key": "sk-test-secret-1234",
            "key_label": "Primary key",
        },
    )

    assert create_response.status_code == 201
    created_payload = create_response.json()
    assert created_payload["provider"] == "openai"
    assert created_payload["key_label"] == "Primary key"
    assert created_payload["masked_api_key"] == "********1234"
    assert created_payload["validation_status"] == "not_validated"
    assert created_payload["last_validated_at"] is None
    assert created_payload["created_at"] is not None
    assert created_payload["updated_at"] is not None
    assert "api_key" not in created_payload
    assert "encrypted_api_key" not in created_payload

    list_response = request(
        app,
        "GET",
        "/api/v1/settings/credentials",
        headers=auth_headers(rsa_private_key),
    )

    assert list_response.status_code == 200
    assert list_response.json() == [created_payload]

    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.clerk_user_id == "user_123"))
        credentials = session.scalars(select(UserProviderCredential)).all()

    assert user is not None
    assert len(credentials) == 1
    assert credentials[0].user_id == user.id
    assert credentials[0].provider == "openai"
    assert credentials[0].key_label == "Primary key"
    assert credentials[0].encrypted_api_key != "sk-test-secret-1234"
    assert (
        app.state.encryption_service.decrypt(credentials[0].encrypted_api_key)
        == "sk-test-secret-1234"
    )


def test_credential_validation_errors_redact_plaintext_api_keys(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)
    secret_api_key = "sk-test-secret-1234"

    response = request(
        app,
        "POST",
        "/api/v1/settings/credentials",
        headers=auth_headers(rsa_private_key),
        json_body={
            "api_key": secret_api_key,
            "key_label": "Primary key",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    serialized_payload = json.dumps(payload)

    assert secret_api_key not in serialized_payload
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["message"] == "Request validation failed."
    assert payload["error"]["details"][0]["input"]["api_key"] == "[REDACTED]"


def test_create_credential_rejects_duplicate_active_provider_for_same_user(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    first_response = request(
        app,
        "POST",
        "/api/v1/settings/credentials",
        headers=auth_headers(rsa_private_key),
        json_body={
            "provider": "openai",
            "api_key": "sk-test-secret-1234",
            "key_label": "Primary key",
        },
    )
    assert first_response.status_code == 201

    duplicate_response = request(
        app,
        "POST",
        "/api/v1/settings/credentials",
        headers=auth_headers(rsa_private_key),
        json_body={
            "provider": "openai",
            "api_key": "sk-test-secret-9999",
            "key_label": "Backup key",
        },
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "error": {
            "code": "http_error",
            "message": "An active credential already exists for provider 'openai'.",
            "details": None,
        }
    }


def test_replace_credential_updates_secret_and_resets_validation_metadata(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    with app.state.session_factory() as session:
        user = User(clerk_user_id="user_123")
        session.add(user)
        session.flush()
        credential = UserProviderCredential(
            user_id=user.id,
            provider="openai",
            encrypted_api_key=app.state.encryption_service.encrypt("sk-old-secret-1234"),
            key_label="Primary key",
            validation_status="valid",
            last_validated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        session.add(credential)
        session.commit()
        credential_id = credential.id

    replace_response = request(
        app,
        "PUT",
        f"/api/v1/settings/credentials/{credential_id}",
        headers=auth_headers(rsa_private_key),
        json_body={
            "api_key": "sk-new-secret-5678",
            "key_label": "Rotated key",
        },
    )

    assert replace_response.status_code == 200
    assert replace_response.json() == {
        "id": str(credential_id),
        "provider": "openai",
        "key_label": "Rotated key",
        "masked_api_key": "********5678",
        "validation_status": "not_validated",
        "last_validated_at": None,
        "created_at": replace_response.json()["created_at"],
        "updated_at": replace_response.json()["updated_at"],
    }

    with app.state.session_factory() as session:
        stored_credential = session.get(UserProviderCredential, credential_id)

    assert stored_credential is not None
    assert stored_credential.key_label == "Rotated key"
    assert stored_credential.validation_status == "not_validated"
    assert stored_credential.last_validated_at is None
    assert stored_credential.encrypted_api_key != "sk-new-secret-5678"
    assert (
        app.state.encryption_service.decrypt(stored_credential.encrypted_api_key)
        == "sk-new-secret-5678"
    )


def test_delete_credential_marks_it_inactive_and_removes_it_from_list(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    with app.state.session_factory() as session:
        user = User(clerk_user_id="user_123")
        session.add(user)
        session.flush()
        credential = UserProviderCredential(
            user_id=user.id,
            provider="anthropic",
            encrypted_api_key=app.state.encryption_service.encrypt("sk-ant-secret-4321"),
            key_label="Claude key",
        )
        session.add(credential)
        session.commit()
        credential_id = credential.id

    delete_response = request(
        app,
        "DELETE",
        f"/api/v1/settings/credentials/{credential_id}",
        headers=auth_headers(rsa_private_key),
    )

    assert delete_response.status_code == 204
    assert delete_response.content == b""

    list_response = request(
        app,
        "GET",
        "/api/v1/settings/credentials",
        headers=auth_headers(rsa_private_key),
    )

    assert list_response.status_code == 200
    assert list_response.json() == []

    with app.state.session_factory() as session:
        stored_credential = session.get(UserProviderCredential, credential_id)

    assert stored_credential is not None
    assert stored_credential.is_active is False


def test_replace_and_delete_credential_are_scoped_to_authenticated_user(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)

    with app.state.session_factory() as session:
        owner = User(clerk_user_id="user_123")
        other_user = User(clerk_user_id="user_456")
        session.add_all([owner, other_user])
        session.flush()
        credential = UserProviderCredential(
            user_id=other_user.id,
            provider="openai",
            encrypted_api_key=app.state.encryption_service.encrypt("sk-other-secret-0000"),
            key_label="Other key",
        )
        session.add(credential)
        session.commit()
        credential_id = credential.id

    replace_response = request(
        app,
        "PUT",
        f"/api/v1/settings/credentials/{credential_id}",
        headers=auth_headers(rsa_private_key, subject="user_123"),
        json_body={
            "api_key": "sk-new-secret-5678",
            "key_label": "Rotated key",
        },
    )

    assert replace_response.status_code == 404
    assert replace_response.json() == {
        "error": {
            "code": "not_found",
            "message": "Credential was not found.",
            "details": None,
        }
    }

    delete_response = request(
        app,
        "DELETE",
        f"/api/v1/settings/credentials/{credential_id}",
        headers=auth_headers(rsa_private_key, subject="user_123"),
    )

    assert delete_response.status_code == 404
    assert delete_response.json() == {
        "error": {
            "code": "not_found",
            "message": "Credential was not found.",
            "details": None,
        }
    }

    with app.state.session_factory() as session:
        stored_credential = session.get(UserProviderCredential, credential_id)

    assert stored_credential is not None
    assert stored_credential.is_active is True
    assert stored_credential.key_label == "Other key"
    assert (
        app.state.encryption_service.decrypt(stored_credential.encrypted_api_key)
        == "sk-other-secret-0000"
    )


def test_validate_credential_marks_it_valid_and_persists_timestamp(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)
    validator = StubProviderCredentialValidator(outcomes={"openai": "valid"})
    app.state.provider_credential_validator = validator

    with app.state.session_factory() as session:
        user = User(clerk_user_id="user_123")
        session.add(user)
        session.flush()
        credential = UserProviderCredential(
            user_id=user.id,
            provider="openai",
            encrypted_api_key=app.state.encryption_service.encrypt("sk-valid-secret-1234"),
            key_label="Primary key",
        )
        session.add(credential)
        session.commit()
        credential_id = credential.id

    response = request(
        app,
        "POST",
        f"/api/v1/settings/credentials/{credential_id}/validate",
        headers=auth_headers(rsa_private_key),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(credential_id)
    assert payload["provider"] == "openai"
    assert payload["key_label"] == "Primary key"
    assert payload["masked_api_key"] == "********1234"
    assert payload["validation_status"] == "valid"
    assert payload["last_validated_at"] is not None

    assert validator.calls == [
        {"provider": "openai", "api_key": "sk-valid-secret-1234"},
    ]

    with app.state.session_factory() as session:
        stored_credential = session.get(UserProviderCredential, credential_id)

    assert stored_credential is not None
    assert stored_credential.validation_status == "valid"
    assert stored_credential.last_validated_at is not None


def test_validate_credential_marks_it_invalid_when_provider_rejects_key(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)
    validator = StubProviderCredentialValidator(outcomes={"anthropic": "invalid"})
    app.state.provider_credential_validator = validator

    with app.state.session_factory() as session:
        user = User(clerk_user_id="user_123")
        session.add(user)
        session.flush()
        credential = UserProviderCredential(
            user_id=user.id,
            provider="anthropic",
            encrypted_api_key=app.state.encryption_service.encrypt("sk-ant-secret-4321"),
            key_label="Claude key",
        )
        session.add(credential)
        session.commit()
        credential_id = credential.id

    response = request(
        app,
        "POST",
        f"/api/v1/settings/credentials/{credential_id}/validate",
        headers=auth_headers(rsa_private_key),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation_status"] == "invalid"
    assert payload["last_validated_at"] is not None

    assert validator.calls == [
        {"provider": "anthropic", "api_key": "sk-ant-secret-4321"},
    ]

    with app.state.session_factory() as session:
        stored_credential = session.get(UserProviderCredential, credential_id)

    assert stored_credential is not None
    assert stored_credential.validation_status == "invalid"
    assert stored_credential.last_validated_at is not None


def test_validate_credential_rejects_unsupported_provider_without_mutating_metadata(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)
    app.state.provider_credential_validator = StubProviderCredentialValidator(
        outcomes={
            "mistral": UnsupportedCredentialProviderError(provider="mistral"),
        }
    )

    with app.state.session_factory() as session:
        user = User(clerk_user_id="user_123")
        session.add(user)
        session.flush()
        credential = UserProviderCredential(
            user_id=user.id,
            provider="mistral",
            encrypted_api_key=app.state.encryption_service.encrypt("sk-mistral-secret"),
            key_label="Unsupported",
        )
        session.add(credential)
        session.commit()
        credential_id = credential.id

    response = request(
        app,
        "POST",
        f"/api/v1/settings/credentials/{credential_id}/validate",
        headers=auth_headers(rsa_private_key),
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "Provider 'mistral' is not supported for credential validation.",
            "details": None,
        }
    }

    with app.state.session_factory() as session:
        stored_credential = session.get(UserProviderCredential, credential_id)

    assert stored_credential is not None
    assert stored_credential.validation_status == "not_validated"
    assert stored_credential.last_validated_at is None


def test_validate_credential_returns_502_when_provider_check_fails(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)
    app.state.provider_credential_validator = StubProviderCredentialValidator(
        outcomes={
            "openai": ProviderCredentialValidationError(provider="openai"),
        }
    )

    with app.state.session_factory() as session:
        user = User(clerk_user_id="user_123")
        session.add(user)
        session.flush()
        credential = UserProviderCredential(
            user_id=user.id,
            provider="openai",
            encrypted_api_key=app.state.encryption_service.encrypt("sk-error-secret-1234"),
            key_label="Primary key",
        )
        session.add(credential)
        session.commit()
        credential_id = credential.id

    response = request(
        app,
        "POST",
        f"/api/v1/settings/credentials/{credential_id}/validate",
        headers=auth_headers(rsa_private_key),
    )

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "Credential validation could not be completed for provider 'openai'.",
            "details": None,
        }
    }

    with app.state.session_factory() as session:
        stored_credential = session.get(UserProviderCredential, credential_id)

    assert stored_credential is not None
    assert stored_credential.validation_status == "not_validated"
    assert stored_credential.last_validated_at is None


def test_validate_credential_is_scoped_to_authenticated_user(
    rsa_private_key,
    sqlite_database_url,
) -> None:
    app = build_test_app(rsa_private_key, sqlite_database_url)
    validator = StubProviderCredentialValidator(outcomes={"openai": "valid"})
    app.state.provider_credential_validator = validator

    with app.state.session_factory() as session:
        owner = User(clerk_user_id="user_123")
        other_user = User(clerk_user_id="user_456")
        session.add_all([owner, other_user])
        session.flush()
        credential = UserProviderCredential(
            user_id=other_user.id,
            provider="openai",
            encrypted_api_key=app.state.encryption_service.encrypt("sk-other-secret-0000"),
            key_label="Other key",
        )
        session.add(credential)
        session.commit()
        credential_id = credential.id

    response = request(
        app,
        "POST",
        f"/api/v1/settings/credentials/{credential_id}/validate",
        headers=auth_headers(rsa_private_key, subject="user_123"),
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Credential was not found.",
            "details": None,
        }
    }
    assert validator.calls == []
