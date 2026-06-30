"""Projet privé par défaut — colonne is_public (default False).

Revision ID: 0008_project_is_public
Revises: 0007_share_view_tracking
Create Date: 2026-06-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_project_is_public"
down_revision = "0007_share_view_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {r[0] for r in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name='projects'"
    ))}
    if "is_public" not in cols:
        op.add_column(
            "projects",
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
        )


def downgrade() -> None:
    op.drop_column("projects", "is_public")
