"""Partage de fiche — share_token_hash sur need_fiches.

Revision ID: 0011_fiche_share
Revises: 0010_module_rescore
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_fiche_share"
down_revision = "0010_module_rescore"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {
        r[0]
        for r in conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='need_fiches'"
            )
        )
    }
    if "share_token_hash" not in existing_cols:
        op.add_column(
            "need_fiches",
            sa.Column("share_token_hash", sa.String(64), nullable=True),
        )
        op.create_unique_constraint(
            "uq_need_fiches_share_token_hash", "need_fiches", ["share_token_hash"]
        )


def downgrade() -> None:
    op.drop_constraint("uq_need_fiches_share_token_hash", "need_fiches", type_="unique")
    op.drop_column("need_fiches", "share_token_hash")
