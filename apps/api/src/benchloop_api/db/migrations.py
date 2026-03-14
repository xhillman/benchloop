from pathlib import Path

from alembic.config import Config

from benchloop_api.db.base import Base

API_DIR = Path(__file__).resolve().parents[3]
ALEMBIC_INI_PATH = API_DIR / "alembic.ini"


def get_target_metadata():
    import benchloop_api.users.models  # noqa: F401

    return Base.metadata


def build_alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(ALEMBIC_INI_PATH))
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)
    return config
