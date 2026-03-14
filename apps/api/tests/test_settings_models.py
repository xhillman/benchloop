from sqlalchemy import String, Text

from benchloop_api.settings.models import UserProviderCredential, UserSettings


def test_user_settings_model_defines_one_row_per_user_defaults() -> None:
    table = UserSettings.__table__

    assert set(table.c.keys()) == {
        "id",
        "user_id",
        "default_provider",
        "default_model",
        "timezone",
        "created_at",
        "updated_at",
    }
    assert table.c.user_id.nullable is False
    assert isinstance(table.c.default_provider.type, String)
    assert isinstance(table.c.default_model.type, String)
    assert isinstance(table.c.timezone.type, String)
    assert any(
        constraint.columns.keys() == ["user_id"] for constraint in table.constraints
    )


def test_user_provider_credential_model_defines_secret_and_validation_columns() -> None:
    table = UserProviderCredential.__table__

    assert set(table.c.keys()) == {
        "id",
        "user_id",
        "provider",
        "encrypted_api_key",
        "key_label",
        "validation_status",
        "last_validated_at",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert table.c.user_id.nullable is False
    assert table.c.provider.nullable is False
    assert table.c.encrypted_api_key.nullable is False
    assert isinstance(table.c.encrypted_api_key.type, Text)
    assert table.c.validation_status.nullable is False
    assert table.c.is_active.nullable is False
