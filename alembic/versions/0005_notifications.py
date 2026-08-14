"""V1-05 — Table notifications in-app (report_ready, new_lesson…).

Idempotent (guards d'existence table + index) pour cohabiter avec la baseline `create_all`
(0001) qui, sur une base fraîche, crée déjà la table et ses index depuis les modèles.

Revision ID: 0005_notifications
Revises: 0004_share_expires_at
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0005_notifications"
down_revision = "0004_share_expires_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("notifications"):
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

    # Ré-inspection : la table vient peut-être d'être créée juste au-dessus.
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("notifications")}
    if "ix_notifications_user_id" not in indexes:
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    if "ix_notifications_created_at" not in indexes:
        op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("notifications"):
        return

    indexes = {index["name"] for index in inspector.get_indexes("notifications")}
    if "ix_notifications_created_at" in indexes:
        op.drop_index("ix_notifications_created_at", table_name="notifications")
    if "ix_notifications_user_id" in indexes:
        op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
