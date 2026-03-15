"""Add test cases table.

Revision ID: 0005_add_test_cases_table
Revises: 0004_add_experiments_table
Create Date: 2026-03-13 01:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_add_test_cases_table"
down_revision: str | None = "0004_add_experiments_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_cases",
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("expected_output_text", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
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
            ["experiment_id"],
            ["experiments.id"],
            name=op.f("fk_test_cases_experiment_id_experiments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_test_cases_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_cases")),
    )
    op.create_index(op.f("ix_test_cases_experiment_id"), "test_cases", ["experiment_id"])
    op.create_index(op.f("ix_test_cases_user_id"), "test_cases", ["user_id"])
    op.create_index(
        "ix_test_cases_user_id_experiment_id",
        "test_cases",
        ["user_id", "experiment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_test_cases_user_id_experiment_id", table_name="test_cases")
    op.drop_index(op.f("ix_test_cases_user_id"), table_name="test_cases")
    op.drop_index(op.f("ix_test_cases_experiment_id"), table_name="test_cases")
    op.drop_table("test_cases")
