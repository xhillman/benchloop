from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Float, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from benchloop_api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from benchloop_api.ownership.models import UserOwnedMixin


class Run(UserOwnedMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_runs_user_id_created_at", "user_id", "created_at"),
        Index("ix_runs_user_id_experiment_id", "user_id", "experiment_id"),
        Index("ix_runs_user_id_status", "user_id", "status"),
    )

    experiment_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    test_case_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    config_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    credential_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    config_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    input_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    context_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    output_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    usage_input_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    usage_output_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    usage_total_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
