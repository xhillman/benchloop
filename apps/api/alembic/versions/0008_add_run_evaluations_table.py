"""Add run evaluations table.

Revision ID: 0008_add_run_evaluations_table
Revises: 0007_add_runs_table
Create Date: 2026-03-15 03:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008_add_run_evaluations_table"
down_revision: str | None = "0007_add_runs_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "run_evaluations",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("dimension_scores_json", sa.JSON(), nullable=False),
        sa.Column("thumbs_signal", sa.String(length=16), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
            ["run_id"],
            ["runs.id"],
            name=op.f("fk_run_evaluations_run_id_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_run_evaluations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run_evaluations")),
        sa.UniqueConstraint("user_id", "run_id", name="uq_run_evaluations_user_id_run_id"),
    )
    op.create_index(op.f("ix_run_evaluations_run_id"), "run_evaluations", ["run_id"])
    op.create_index(op.f("ix_run_evaluations_user_id"), "run_evaluations", ["user_id"])
    op.create_index(
        "ix_run_evaluations_user_id_run_id",
        "run_evaluations",
        ["user_id", "run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_run_evaluations_user_id_run_id", table_name="run_evaluations")
    op.drop_index(op.f("ix_run_evaluations_user_id"), table_name="run_evaluations")
    op.drop_index(op.f("ix_run_evaluations_run_id"), table_name="run_evaluations")
    op.drop_table("run_evaluations")
