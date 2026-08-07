"""Vérification email — colonne users.email_verified.

Revision ID: 0015_email_verified
Revises: 0014_logo
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0015_email_verified"
down_revision = "0014_logo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {
        r[0]
        for r in conn.execute(sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='users'"))
    }
    if "email_verified" not in cols:
        op.add_column(
            "users",
            sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        )


def downgrade() -> None:
    op.drop_column("users", "email_verified")
