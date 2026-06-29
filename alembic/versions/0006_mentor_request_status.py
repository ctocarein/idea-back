"""Mentor request — updated_at + session_at + status index.

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


def upgrade() -> None:
    op.add_column(
        "mentor_requests",
        sa.Column("session_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mentor_requests",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_mentor_requests_status", "mentor_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_mentor_requests_status", table_name="mentor_requests")
    op.drop_column("mentor_requests", "updated_at")
    op.drop_column("mentor_requests", "session_at")
