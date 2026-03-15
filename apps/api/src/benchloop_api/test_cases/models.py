from uuid import UUID

from sqlalchemy import ForeignKey, Index, JSON, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from benchloop_api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from benchloop_api.ownership.models import UserOwnedMixin


class TestCase(UserOwnedMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "test_cases"
    __table_args__ = (
        Index("ix_test_cases_user_id_experiment_id", "user_id", "experiment_id"),
    )

    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    input_text: Mapped[str] = mapped_column(Text(), nullable=False)
    expected_output_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        JSON(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
