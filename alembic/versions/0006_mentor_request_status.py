"""Mentor request — updated_at + session_at + status index.

Revision ID: 0006_mentor_request_status
Revises: 0005_notifications
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_mentor_request_status"
down_revision = "0005_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("mentor_requests")}
    if "session_at" not in columns:
        op.add_column(
            "mentor_requests",
            sa.Column("session_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "updated_at" not in columns:
        op.add_column(
            "mentor_requests",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
        )

    indexes = {index["name"] for index in inspector.get_indexes("mentor_requests")}
    if "ix_mentor_requests_status" not in indexes:
        op.create_index("ix_mentor_requests_status", "mentor_requests", ["status"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("mentor_requests")}
    if "ix_mentor_requests_status" in indexes:
        op.drop_index("ix_mentor_requests_status", table_name="mentor_requests")

    columns = {column["name"] for column in inspector.get_columns("mentor_requests")}
    if "updated_at" in columns:
        op.drop_column("mentor_requests", "updated_at")
    if "session_at" in columns:
        op.drop_column("mentor_requests", "session_at")
