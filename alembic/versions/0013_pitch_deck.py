"""Pitch deck visuel — template_id + slides sur pitches.

Revision ID: 0013_pitch_deck
Revises: 0012_pitch
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0013_pitch_deck"
down_revision = "0012_pitch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {
        r[0]
        for r in conn.execute(sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='pitches'"))
    }
    if "template_id" not in cols:
        op.add_column(
            "pitches",
            sa.Column("template_id", sa.String(40), nullable=False, server_default="base"),
        )
    if "slides" not in cols:
        op.add_column(
            "pitches",
            sa.Column("slides", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    op.drop_column("pitches", "slides")
    op.drop_column("pitches", "template_id")
