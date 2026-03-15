"""Add runs table.

Revision ID: 0007_add_runs_table
Revises: 0006_add_configs_table
Create Date: 2026-03-13 05:40:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0007_add_runs_table"
down_revision: str | None = "0006_add_configs_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("test_case_id", sa.Uuid(), nullable=False),
        sa.Column("config_id", sa.Uuid(), nullable=False),
        sa.Column("credential_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("workflow_mode", sa.String(length=50), nullable=False),
        sa.Column("config_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("input_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("context_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("usage_input_tokens", sa.Integer(), nullable=True),
        sa.Column("usage_output_tokens", sa.Integer(), nullable=True),
        sa.Column("usage_total_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_runs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
    )
    op.create_index(op.f("ix_runs_config_id"), "runs", ["config_id"])
    op.create_index(op.f("ix_runs_experiment_id"), "runs", ["experiment_id"])
    op.create_index(op.f("ix_runs_test_case_id"), "runs", ["test_case_id"])
    op.create_index(op.f("ix_runs_user_id"), "runs", ["user_id"])
    op.create_index("ix_runs_user_id_created_at", "runs", ["user_id", "created_at"])
    op.create_index(
        "ix_runs_user_id_experiment_id",
        "runs",
        ["user_id", "experiment_id"],
    )
    op.create_index("ix_runs_user_id_status", "runs", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_runs_user_id_status", table_name="runs")
    op.drop_index("ix_runs_user_id_experiment_id", table_name="runs")
    op.drop_index("ix_runs_user_id_created_at", table_name="runs")
    op.drop_index(op.f("ix_runs_user_id"), table_name="runs")
    op.drop_index(op.f("ix_runs_test_case_id"), table_name="runs")
    op.drop_index(op.f("ix_runs_experiment_id"), table_name="runs")
    op.drop_index(op.f("ix_runs_config_id"), table_name="runs")
    op.drop_table("runs")
