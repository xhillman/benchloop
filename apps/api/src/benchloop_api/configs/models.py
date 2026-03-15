from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, JSON, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from benchloop_api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from benchloop_api.ownership.models import UserOwnedMixin


class Config(UserOwnedMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "configs"
    __table_args__ = (
        Index("ix_configs_user_id_experiment_id", "user_id", "experiment_id"),
    )

    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version_label: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text(), nullable=True)
    user_prompt_template: Mapped[str] = mapped_column(Text(), nullable=False)
    temperature: Mapped[float] = mapped_column(Float(), nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer(), nullable=False)
    top_p: Mapped[float | None] = mapped_column(Float(), nullable=True)
    context_bundle_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        JSON(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    is_baseline: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=False,
        server_default=text("false"),
    )
