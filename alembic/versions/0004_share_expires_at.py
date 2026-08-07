"""SEC-11 — Liens de partage : ajout de `expires_at` (expiration automatique après 90 j).

Revision ID: 0004_share_expires_at
Revises: 0003_user_onboarding_profile
Create Date: 2026-06-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_share_expires_at"
down_revision = "0003_user_onboarding_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {
        r[0]
        for r in conn.execute(
            sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='project_shares'")
        )
    }
    if "expires_at" not in cols:
        # 1) Ajout nullable (PostgreSQL interdit les refs à d'autres colonnes dans DEFAULT).
        op.add_column(
            "project_shares",
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        )
        # 2) Backfill : liens existants → 90 j à partir de leur date de création.
        conn.execute(sa.text("UPDATE project_shares SET expires_at = created_at + INTERVAL '90 days'"))
        # 3) NOT NULL maintenant que toutes les lignes ont une valeur.
        op.alter_column("project_shares", "expires_at", nullable=False)
        op.create_index("ix_project_shares_expires_at", "project_shares", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_project_shares_expires_at", table_name="project_shares")
    op.drop_column("project_shares", "expires_at")
