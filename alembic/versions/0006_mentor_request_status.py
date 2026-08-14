"""Mentor request — updated_at + session_at + status index.

Idempotent (guards d'existence colonnes + index) pour cohabiter avec la baseline `create_all`
(0001) qui, sur une base fraîche, crée déjà ces colonnes et l'index `ix_mentor_requests_status`
depuis les modèles. Sans ces guards, `upgrade head` sur une base vide échouait avec
`DuplicateColumnError: column "session_at" ... already exists`.

Revision ID: 0006_mentor_request_status
Revises: 0005_notifications
Create Date: 2026-06-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_mentor_request_status"
down_revision = "0005_notifications"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    conn = op.get_bind()
    return {
        r[0]
        for r in conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns WHERE table_name=:t"
            ),
            {"t": table},
        )
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
    cols = _columns("mentor_requests")
    if "session_at" not in cols:
        op.add_column(
            "mentor_requests",
            sa.Column("session_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "updated_at" not in cols:
        op.add_column(
            "mentor_requests",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
        )
    if "ix_mentor_requests_status" not in _indexes("mentor_requests"):
        op.create_index("ix_mentor_requests_status", "mentor_requests", ["status"])


def downgrade() -> None:
    if "ix_mentor_requests_status" in _indexes("mentor_requests"):
        op.drop_index("ix_mentor_requests_status", table_name="mentor_requests")
    cols = _columns("mentor_requests")
    if "updated_at" in cols:
        op.drop_column("mentor_requests", "updated_at")
    if "session_at" in cols:
        op.drop_column("mentor_requests", "session_at")
