from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from benchloop_api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from benchloop_api.ownership.models import UserOwnedMixin


class ContextBundle(UserOwnedMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "context_bundles"
    __table_args__ = (
        Index("ix_context_bundles_user_id_experiment_id", "user_id", "experiment_id"),
        Index("ix_context_bundles_user_id_name", "user_id", "name"),
    )

    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_text: Mapped[str] = mapped_column(Text(), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
