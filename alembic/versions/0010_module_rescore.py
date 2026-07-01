"""Module re-scoring — score avant/après par axe sur guided_sessions.

Revision ID: 0010_module_rescore
Revises: 0009_academy_modules
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_module_rescore"
down_revision = "0009_academy_modules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {
        r[0]
        for r in conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='guided_sessions'"
            )
        )
    }
    if "axis_score_before" not in existing_cols:
        op.add_column(
            "guided_sessions",
            sa.Column("axis_score_before", sa.Integer(), nullable=True),
        )
    if "axis_score_after" not in existing_cols:
        op.add_column(
            "guided_sessions",
            sa.Column("axis_score_after", sa.Integer(), nullable=True),
        )
    if "rescored_at" not in existing_cols:
        op.add_column(
            "guided_sessions",
            sa.Column("rescored_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("guided_sessions", "rescored_at")
    op.drop_column("guided_sessions", "axis_score_after")
    op.drop_column("guided_sessions", "axis_score_before")
