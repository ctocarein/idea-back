"""V1-08 — Suivi des vues sur les liens de partage : view_count, last_viewed_at, token.

Revision ID: 0007_share_view_tracking
Revises: 0006_mentor_request_status
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_share_view_tracking"
down_revision = "0006_mentor_request_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {r[0] for r in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name='project_shares'"
    ))}
    if "token" not in cols:
        op.add_column("project_shares", sa.Column("token", sa.String(64), nullable=True))
    if "view_count" not in cols:
        op.add_column("project_shares", sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"))
    if "last_viewed_at" not in cols:
        op.add_column("project_shares", sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("project_shares", "last_viewed_at")
    op.drop_column("project_shares", "view_count")
    op.drop_column("project_shares", "token")
