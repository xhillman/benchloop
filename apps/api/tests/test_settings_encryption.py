import pytest

from benchloop_api.settings.encryption import (
    EncryptionError,
    EncryptionService,
    redact_secret_values,
)


def test_encryption_service_encrypts_and_decrypts_without_leaking_plaintext() -> None:
    service = EncryptionService("test-encryption-key-material")

    first_ciphertext = service.encrypt("sk-test-123")
    second_ciphertext = service.encrypt("sk-test-123")

    assert first_ciphertext != "sk-test-123"
    assert second_ciphertext != "sk-test-123"
    assert first_ciphertext != second_ciphertext
    assert service.decrypt(first_ciphertext) == "sk-test-123"


def test_encryption_service_raises_generic_error_for_invalid_ciphertext() -> None:
    service = EncryptionService("test-encryption-key-material")

    with pytest.raises(EncryptionError, match="could not be decrypted"):
        service.decrypt("not-a-valid-ciphertext")


def test_redact_secret_values_masks_nested_secret_fields() -> None:
    payload = {
        "provider": "openai",
        "api_key": "sk-test-123",
        "metadata": {
            "authorization": "Bearer secret-token",
            "key_label": "Personal key",
        },
        "items": [
            {"token": "abc123"},
            {"value": "safe"},
        ],
    }

    assert redact_secret_values(payload) == {
        "provider": "openai",
        "api_key": "[REDACTED]",
        "metadata": {
            "authorization": "[REDACTED]",
            "key_label": "Personal key",
        },
        "items": [
            {"token": "[REDACTED]"},
            {"value": "safe"},
        ],
    }
