from __future__ import annotations

import base64
import hashlib
from collections.abc import Mapping
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request

from benchloop_api.config import AppSettings

REDACTED_VALUE = "[REDACTED]"
_SENSITIVE_KEY_FRAGMENTS = (
    "api_key",
    "authorization",
    "password",
    "secret",
    "token",
)


class EncryptionError(Exception):
    pass


class EncryptionService:
    def __init__(self, key_material: str) -> None:
        normalized_key_material = key_material.strip()
        if not normalized_key_material:
            raise ValueError("Encryption key material must not be empty.")

        derived_key = base64.urlsafe_b64encode(
            hashlib.sha256(normalized_key_material.encode("utf-8")).digest()
        )
        self._fernet = Fernet(derived_key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            decrypted = self._fernet.decrypt(ciphertext.encode("utf-8"))
        except (InvalidToken, ValueError, TypeError) as exc:
            raise EncryptionError("Encrypted value could not be decrypted.") from exc
        return decrypted.decode("utf-8")


def create_encryption_service(settings: AppSettings) -> EncryptionService:
    return EncryptionService(settings.encryption_key)


def get_encryption_service(request: Request) -> EncryptionService:
    return request.app.state.encryption_service


def redact_secret_values(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        redacted: dict[Any, Any] = {}
        for key, value in payload.items():
            if _is_sensitive_key(key):
                redacted[key] = REDACTED_VALUE
            else:
                redacted[key] = redact_secret_values(value)
        return redacted

    if isinstance(payload, list):
        return [redact_secret_values(item) for item in payload]

    if isinstance(payload, tuple):
        return tuple(redact_secret_values(item) for item in payload)

    return payload


def _is_sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False

    normalized_key = key.strip().lower()
    return any(fragment in normalized_key for fragment in _SENSITIVE_KEY_FRAGMENTS)
