"""Add experiments table.

Revision ID: 0004_add_experiments_table
Revises: 0003_add_settings_tables
Create Date: 2026-03-13 00:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_add_experiments_table"
down_revision: str | None = "0003_add_settings_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
            name=op.f("fk_experiments_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_experiments")),
    )
    op.create_index(op.f("ix_experiments_user_id"), "experiments", ["user_id"])
    op.create_index("ix_experiments_user_id_name", "experiments", ["user_id", "name"])


def downgrade() -> None:
    op.drop_index("ix_experiments_user_id_name", table_name="experiments")
    op.drop_index(op.f("ix_experiments_user_id"), table_name="experiments")
    op.drop_table("experiments")
