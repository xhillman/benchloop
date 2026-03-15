"""Add settings tables.

Revision ID: 0003_add_settings_tables
Revises: 0002_add_users_table
Create Date: 2026-03-13 00:02:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_add_settings_tables"
down_revision: str | None = "0002_add_users_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("default_provider", sa.String(length=100), nullable=True),
        sa.Column("default_model", sa.String(length=255), nullable=True),
        sa.Column("timezone", sa.String(length=100), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_settings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_settings")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_settings_user_id")),
    )
    op.create_index(op.f("ix_user_settings_user_id"), "user_settings", ["user_id"])

    op.create_table(
        "user_provider_credentials",
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("key_label", sa.String(length=255), nullable=True),
        sa.Column(
            "validation_status",
            sa.String(length=32),
            server_default="not_validated",
            nullable=False,
        ),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_provider_credentials_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_provider_credentials")),
    )
    op.create_index(
        op.f("ix_user_provider_credentials_user_id"),
        "user_provider_credentials",
        ["user_id"],
    )
    op.create_index(
        "ix_user_provider_credentials_user_id_provider",
        "user_provider_credentials",
        ["user_id", "provider"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_provider_credentials_user_id_provider",
        table_name="user_provider_credentials",
    )
    op.drop_index(
        op.f("ix_user_provider_credentials_user_id"),
        table_name="user_provider_credentials",
    )
    op.drop_table("user_provider_credentials")

    op.drop_index(op.f("ix_user_settings_user_id"), table_name="user_settings")
    op.drop_table("user_settings")
