"""Add configs table.

Revision ID: 0006_add_configs_table
Revises: 0005_add_test_cases_table
Create Date: 2026-03-13 02:05:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_add_configs_table"
down_revision: str | None = "0005_add_test_cases_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "configs",
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version_label", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("workflow_mode", sa.String(length=50), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("top_p", sa.Float(), nullable=True),
        sa.Column("context_bundle_id", sa.Uuid(), nullable=True),
        sa.Column("tags", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("is_baseline", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
            name=op.f("fk_configs_experiment_id_experiments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_configs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configs")),
    )
    op.create_index(op.f("ix_configs_experiment_id"), "configs", ["experiment_id"])
    op.create_index(op.f("ix_configs_user_id"), "configs", ["user_id"])
    op.create_index(
        "ix_configs_user_id_experiment_id",
        "configs",
        ["user_id", "experiment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_configs_user_id_experiment_id", table_name="configs")
    op.drop_index(op.f("ix_configs_user_id"), table_name="configs")
    op.drop_index(op.f("ix_configs_experiment_id"), table_name="configs")
    op.drop_table("configs")
