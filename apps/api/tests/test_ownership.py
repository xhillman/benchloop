from inspect import signature
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.schema import Table

from benchloop_api.config import AppSettings
from benchloop_api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from benchloop_api.db.session import create_database_engine, create_session_factory
from benchloop_api.ownership import (
    UserOwnedMixin,
    UserOwnedRepository,
    UserOwnedResourceNotFoundError,
    UserOwnedService,
)
from benchloop_api.users.models import User


@pytest.fixture()
def sqlite_settings(tmp_path) -> AppSettings:
    return AppSettings.model_validate(
        {
            "database_url": f"sqlite+pysqlite:///{tmp_path / 'benchloop-ownership.db'}",
            "db_echo": False,
        }
    )


@pytest.fixture()
def database_engine(sqlite_settings):
    engine = create_database_engine(sqlite_settings)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def session_factory(database_engine):
    return create_session_factory(database_engine)


@pytest.fixture()
def owned_record_model():
    model_name = f"OwnedRecord{uuid4().hex}"
    table_name = f"owned_records_{uuid4().hex[:8]}"
    owned_record = type(
        model_name,
        (UserOwnedMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base),
        {
            "__tablename__": table_name,
            "__annotations__": {
                "title": Mapped[str],
            },
            "title": mapped_column(String(255), nullable=False),
        },
    )

    try:
        yield owned_record
    finally:
        Base.metadata.remove(cast(Table, owned_record.__table__))


def test_user_owned_mixin_defines_required_user_id_column() -> None:
    class OwnedColumnExample(UserOwnedMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
        __tablename__ = "owned_column_example"

        title: Mapped[str] = mapped_column(String(255), nullable=False)

    table = OwnedColumnExample.__table__

    assert "user_id" in table.c
    assert table.c.user_id.nullable is False
    assert table.c.user_id.foreign_keys
    foreign_key = next(iter(table.c.user_id.foreign_keys))
    assert foreign_key.target_fullname == "users.id"

    Base.metadata.remove(cast(Table, OwnedColumnExample.__table__))


def test_user_owned_repository_public_methods_require_explicit_user_id() -> None:
    get_owned_parameters = signature(UserOwnedRepository.get_owned).parameters
    list_owned_parameters = signature(UserOwnedRepository.list_owned).parameters
    delete_owned_parameters = signature(UserOwnedRepository.delete_owned).parameters
    get_owned_or_raise_parameters = signature(UserOwnedService.get_owned_or_raise).parameters

    assert "user_id" in get_owned_parameters
    assert "user_id" in list_owned_parameters
    assert "user_id" in delete_owned_parameters
    assert "user_id" in get_owned_or_raise_parameters


def test_user_owned_repository_scopes_reads_and_deletes_by_user_id(
    database_engine,
    session_factory,
    owned_record_model,
) -> None:
    Base.metadata.create_all(database_engine)

    with session_factory() as session:
        owner = User(clerk_user_id="owner")
        other_user = User(clerk_user_id="other")
        session.add_all([owner, other_user])
        session.flush()

        owner_record = owned_record_model(user_id=owner.id, title="owner record")
        other_record = owned_record_model(user_id=other_user.id, title="other record")

        session.add_all([owner_record, other_record])
        session.commit()

        repository = UserOwnedRepository(session, owned_record_model)

        owned_records = repository.list_owned(user_id=owner.id)
        inaccessible_record = repository.get_owned(
            user_id=owner.id,
            resource_id=other_record.id,
        )
        deleted = repository.delete_owned(
            user_id=owner.id,
            resource_id=other_record.id,
        )

        assert [record.title for record in owned_records] == ["owner record"]
        assert inaccessible_record is None
        assert deleted is False

        remaining_records = session.scalars(select(owned_record_model)).all()
        assert [record.title for record in remaining_records] == [
            "owner record",
            "other record",
        ]


def test_user_owned_service_fails_closed_on_cross_user_access(
    database_engine,
    session_factory,
    owned_record_model,
) -> None:
    Base.metadata.create_all(database_engine)

    with session_factory() as session:
        owner = User(clerk_user_id="owner")
        other_user = User(clerk_user_id="other")
        session.add_all([owner, other_user])
        session.flush()

        owner_record = owned_record_model(user_id=owner.id, title="owner record")

        session.add(owner_record)
        session.commit()

        repository = UserOwnedRepository(session, owned_record_model)
        service = UserOwnedService(repository, resource_name="owned record")

        with pytest.raises(UserOwnedResourceNotFoundError) as exc_info:
            service.get_owned_or_raise(
                user_id=other_user.id,
                resource_id=owner_record.id,
            )

        assert exc_info.value.resource_name == "owned record"
        assert str(exc_info.value) == "owned record was not found."
