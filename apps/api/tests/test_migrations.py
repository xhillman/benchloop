from alembic import command
from sqlalchemy import create_engine, inspect

from benchloop_api.db.migrations import build_alembic_config


def test_alembic_can_upgrade_head_and_check_autogenerate(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'alembic.db'}"
    config = build_alembic_config(database_url=database_url)

    command.upgrade(config, "head")
    command.check(config)


def test_alembic_head_creates_settings_and_experiments_tables(tmp_path) -> None:
    database_path = tmp_path / "settings-schema.db"
    database_url = f"sqlite+pysqlite:///{database_path}"
    config = build_alembic_config(database_url=database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)

        assert "user_settings" in inspector.get_table_names()
        assert "user_provider_credentials" in inspector.get_table_names()
        assert "experiments" in inspector.get_table_names()

        user_settings_columns = {
            column["name"]: column for column in inspector.get_columns("user_settings")
        }
        assert {
            "id",
            "user_id",
            "default_provider",
            "default_model",
            "timezone",
            "created_at",
            "updated_at",
        } <= set(user_settings_columns)
        assert user_settings_columns["user_id"]["nullable"] is False

        settings_uniques = inspector.get_unique_constraints("user_settings")
        assert any(
            constraint["column_names"] == ["user_id"] for constraint in settings_uniques
        )

        credential_columns = {
            column["name"]: column
            for column in inspector.get_columns("user_provider_credentials")
        }
        assert {
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
        } <= set(credential_columns)
        assert credential_columns["user_id"]["nullable"] is False
        assert credential_columns["provider"]["nullable"] is False
        assert credential_columns["encrypted_api_key"]["nullable"] is False
        assert credential_columns["validation_status"]["nullable"] is False
        assert credential_columns["is_active"]["nullable"] is False

        experiment_columns = {
            column["name"]: column for column in inspector.get_columns("experiments")
        }
        assert {
            "id",
            "user_id",
            "name",
            "description",
            "tags",
            "is_archived",
            "created_at",
            "updated_at",
        } <= set(experiment_columns)
        assert experiment_columns["user_id"]["nullable"] is False
        assert experiment_columns["name"]["nullable"] is False
        assert experiment_columns["tags"]["nullable"] is False
        assert experiment_columns["is_archived"]["nullable"] is False
    finally:
        engine.dispose()
