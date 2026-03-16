"""Add context bundles table.

Revision ID: 0009_add_context_bundles_table
Revises: 0008_add_run_evaluations_table
Create Date: 2026-03-14 02:05:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0009_add_context_bundles_table"
down_revision: str | None = "0008_add_run_evaluations_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "context_bundles",
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
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
            ["experiment_id"],
            ["experiments.id"],
            name=op.f("fk_context_bundles_experiment_id_experiments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_context_bundles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_context_bundles")),
    )
    op.create_index(
        op.f("ix_context_bundles_experiment_id"),
        "context_bundles",
        ["experiment_id"],
    )
    op.create_index(op.f("ix_context_bundles_user_id"), "context_bundles", ["user_id"])
    op.create_index(
        "ix_context_bundles_user_id_experiment_id",
        "context_bundles",
        ["user_id", "experiment_id"],
    )
    op.create_index(
        "ix_context_bundles_user_id_name",
        "context_bundles",
        ["user_id", "name"],
    )

    with op.batch_alter_table("configs") as batch_op:
        batch_op.create_index(op.f("ix_configs_context_bundle_id"), ["context_bundle_id"])
        batch_op.create_foreign_key(
            op.f("fk_configs_context_bundle_id_context_bundles"),
            "context_bundles",
            ["context_bundle_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("configs") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_configs_context_bundle_id_context_bundles"),
            type_="foreignkey",
        )
        batch_op.drop_index(op.f("ix_configs_context_bundle_id"))

    op.drop_index("ix_context_bundles_user_id_name", table_name="context_bundles")
    op.drop_index("ix_context_bundles_user_id_experiment_id", table_name="context_bundles")
    op.drop_index(op.f("ix_context_bundles_user_id"), table_name="context_bundles")
    op.drop_index(op.f("ix_context_bundles_experiment_id"), table_name="context_bundles")
    op.drop_table("context_bundles")
