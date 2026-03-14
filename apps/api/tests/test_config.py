from benchloop_api.config import AppSettings


def test_settings_accept_comma_separated_cors_origins() -> None:
    settings = AppSettings.model_validate(
        {"cors_allowed_origins": "http://localhost:3000, http://localhost:3001"},
    )

    assert settings.cors_allowed_origins == [
        "http://localhost:3000",
        "http://localhost:3001",
    ]


def test_settings_accept_json_array_cors_origins() -> None:
    settings = AppSettings.model_validate(
        {"cors_allowed_origins": '["http://localhost:3000", "http://localhost:3001"]'},
    )

    assert settings.cors_allowed_origins == [
        "http://localhost:3000",
        "http://localhost:3001",
    ]


def test_settings_accept_encryption_key() -> None:
    settings = AppSettings.model_validate(
        {"encryption_key": "test-encryption-key-material"},
    )

    assert settings.encryption_key == "test-encryption-key-material"
