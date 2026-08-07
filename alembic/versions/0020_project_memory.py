"""Ajoute la mémoire projet sourcée et l'état explicable des dimensions.

Revision ID: 0020_project_memory
Revises: 0019_job_leases
Create Date: 2026-07-16
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0020_project_memory"
down_revision = "0019_job_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_memory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dimension", sa.String(length=3), nullable=False),
        sa.Column("item_type", sa.String(length=13), nullable=False),
        sa.Column("evidence_state", sa.String(length=9), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("provenance_type", sa.String(length=11), nullable=False),
        sa.Column("source_ref", sa.String(length=200), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("deduplication_key", sa.String(length=200), nullable=True),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "verified_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "supersedes_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_memory_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("dimension ~ '^d([1-9]|1[0-2])$'", name="ck_project_memory_dimension"),
        sa.UniqueConstraint("project_id", "deduplication_key", name="uq_project_memory_deduplication"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_project_memory_items_project_id",
        "project_memory_items",
        ["project_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_project_memory_items_created_by_id",
        "project_memory_items",
        ["created_by_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_project_memory_items_expires_at",
        "project_memory_items",
        ["expires_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_project_memory_items_is_active",
        "project_memory_items",
        ["is_active"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_project_memory_items_created_at",
        "project_memory_items",
        ["created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_project_memory_project_dimension",
        "project_memory_items",
        ["project_id", "dimension"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_project_memory_project_state",
        "project_memory_items",
        ["project_id", "evidence_state"],
        if_not_exists=True,
    )

    op.create_table(
        "project_dimension_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dimension", sa.String(length=3), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence_state", sa.String(length=9), nullable=False, server_default="unknown"),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("contradictions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("missing_information", sa.Text(), nullable=False, server_default=""),
        sa.Column("next_action", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "last_score_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("score_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("dimension ~ '^d([1-9]|1[0-2])$'", name="ck_project_dimension_state_dimension"),
        sa.CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 10",
            name="ck_project_dimension_state_score",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_project_dimension_state_confidence",
        ),
        sa.UniqueConstraint("project_id", "dimension", name="uq_project_dimension_state"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_project_dimension_states_project_id",
        "project_dimension_states",
        ["project_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_project_dimension_states_last_score_run_id",
        "project_dimension_states",
        ["last_score_run_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("project_dimension_states")
    op.drop_table("project_memory_items")
