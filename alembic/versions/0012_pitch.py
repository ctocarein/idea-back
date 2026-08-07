"""Éditeur de pitch — table pitches.

Revision ID: 0012_pitch
Revises: 0011_fiche_share
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0012_pitch"
down_revision = "0011_fiche_share"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    tables = {r[0] for r in conn.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))}
    if "pitches" not in tables:
        op.create_table(
            "pitches",
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
            sa.Column("title", sa.String(200), nullable=False, server_default="Mon pitch"),
            sa.Column("sections", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("pitches")
