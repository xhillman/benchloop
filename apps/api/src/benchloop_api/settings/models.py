from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from benchloop_api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from benchloop_api.ownership.models import UserOwnedMixin


class UserSettings(UserOwnedMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_settings"
    __table_args__ = (UniqueConstraint("user_id"),)

    default_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)


class UserProviderCredential(UserOwnedMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_provider_credentials"
    __table_args__ = (
        Index(
            "ix_user_provider_credentials_user_id_provider",
            "user_id",
            "provider",
        ),
    )

    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text(), nullable=False)
    key_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    validation_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="not_validated",
        server_default="not_validated",
    )
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=True,
        server_default=text("1"),
    )
