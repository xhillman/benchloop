from alembic import command

from benchloop_api.db.migrations import build_alembic_config


def test_alembic_can_upgrade_head_and_check_autogenerate(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'alembic.db'}"
    config = build_alembic_config(database_url=database_url)

    command.upgrade(config, "head")
    command.check(config)
