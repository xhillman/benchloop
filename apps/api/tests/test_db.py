from collections.abc import Generator
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.schema import Table

from benchloop_api.app import create_app
from benchloop_api.config import AppSettings
from benchloop_api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from benchloop_api.db.session import (
    create_database_engine,
    create_session_factory,
    session_scope,
)


@pytest.fixture()
def sqlite_settings(tmp_path) -> AppSettings:
    return AppSettings.model_validate(
        {
            "database_url": f"sqlite+pysqlite:///{tmp_path / 'benchloop.db'}",
            "db_echo": False,
        }
    )


@pytest.fixture()
def database_engine(sqlite_settings) -> Generator:
    engine = create_database_engine(sqlite_settings)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def example_record_model() -> Generator[type[Base]]:
    model_name = f"SessionExampleRecord{uuid4().hex}"
    table_name = f"example_records_{uuid4().hex[:8]}"
    session_example_record = type(
        model_name,
        (UUIDPrimaryKeyMixin, TimestampMixin, Base),
        {
            "__tablename__": table_name,
            "__annotations__": {"name": Mapped[str]},
            "name": mapped_column(nullable=False),
        },
    )

    try:
        yield session_example_record
    finally:
        Base.metadata.remove(cast(Table, getattr(session_example_record, "__table__")))


def test_app_initializes_database_runtime() -> None:
    app = create_app({"database_url": "sqlite+pysqlite:///:memory:"})

    assert app.state.db_engine is not None
    assert app.state.session_factory is not None

    app.state.db_engine.dispose()


def test_uuid_and_timestamp_mixins_define_foundational_columns() -> None:
    class ColumnExampleRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
        __tablename__ = "example_record_columns"

        name: Mapped[str] = mapped_column(nullable=False)

    table = ColumnExampleRecord.__table__

    assert set(table.c.keys()) == {"name", "id", "created_at", "updated_at"}
    assert table.c.id.primary_key is True
    assert isinstance(ColumnExampleRecord(id=UUID(int=0), name="example").id, UUID)
    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is False

    Base.metadata.remove(cast(Table, ColumnExampleRecord.__table__))


def test_session_scope_commits_changes(database_engine, example_record_model) -> None:
    session_factory = create_session_factory(database_engine)
    Base.metadata.create_all(database_engine)

    with session_scope(session_factory) as session:
        session.add(example_record_model(name="saved"))

    with session_factory() as session:
        records = session.scalars(select(example_record_model)).all()

    assert [record.name for record in records] == ["saved"]


def test_session_scope_rolls_back_changes_on_error(
    database_engine,
    example_record_model,
) -> None:
    session_factory = create_session_factory(database_engine)
    Base.metadata.create_all(database_engine)

    with pytest.raises(RuntimeError):
        with session_scope(session_factory) as session:
            session.add(example_record_model(name="discarded"))
            raise RuntimeError("force rollback")

    with session_factory() as session:
        records = session.scalars(select(example_record_model)).all()

    assert records == []
