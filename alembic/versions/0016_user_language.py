"""Bilingue — colonne users.language (préférence de langue).

Revision ID: 0016_user_language
Revises: 0015_email_verified
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0016_user_language"
down_revision = "0015_email_verified"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {
        r[0]
        for r in conn.execute(sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='users'"))
    }
    if "language" not in cols:
        op.add_column(
            "users",
            sa.Column("language", sa.String(length=2), nullable=False, server_default="fr"),
        )


def downgrade() -> None:
    op.drop_column("users", "language")
