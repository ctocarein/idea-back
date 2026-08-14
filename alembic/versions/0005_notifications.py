"""V1-05 — Table notifications in-app (report_ready, new_lesson…).

Idempotent (guards d'existence table + index) pour cohabiter avec la baseline `create_all`
(0001) qui, sur une base fraîche, crée déjà la table et ses index depuis les modèles.

Revision ID: 0005_notifications
Revises: 0004_share_expires_at
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_notifications"
down_revision = "0004_share_expires_at"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    conn = op.get_bind()
    return {
        r[0]
        for r in conn.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
    }


def _indexes(table: str) -> set[str]:
    conn = op.get_bind()
    return {
        r[0]
        for r in conn.execute(
            sa.text("SELECT indexname FROM pg_indexes WHERE tablename=:t"), {"t": table}
        )
    }


def upgrade() -> None:
    if "notifications" not in _tables():
        op.create_table(
            "notifications",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column(
                "user_id",
                sa.UUID(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("type", sa.String(50), nullable=False),
            sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )

    idx = _indexes("notifications")
    if "ix_notifications_user_id" not in idx:
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    if "ix_notifications_created_at" not in idx:
        op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    idx = _indexes("notifications")
    if "ix_notifications_created_at" in idx:
        op.drop_index("ix_notifications_created_at", table_name="notifications")
    if "ix_notifications_user_id" in idx:
        op.drop_index("ix_notifications_user_id", table_name="notifications")
    if "notifications" in _tables():
        op.drop_table("notifications")
