from sqlalchemy import Boolean, Index, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from benchloop_api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from benchloop_api.ownership.models import UserOwnedMixin


class Experiment(UserOwnedMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiments"
    __table_args__ = (
        Index("ix_experiments_user_id_name", "user_id", "name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        JSON(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=False,
        server_default=text("false"),
    )
