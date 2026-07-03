"""Studio — table logos (tranche 2).

Revision ID: 0014_logo
Revises: 0013_pitch_deck
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_logo"
down_revision = "0013_pitch_deck"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    tables = {
        r[0]
        for r in conn.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
    }
    if "logos" not in tables:
        op.create_table(
            "logos",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column(
                "owner_id",
                sa.UUID(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "project_id",
                sa.UUID(),
                sa.ForeignKey("projects.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column("spec", sa.dialects.postgresql.JSONB(), nullable=True),
            sa.Column(
                "variations", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
        )


def downgrade() -> None:
    op.drop_table("logos")
