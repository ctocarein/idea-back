"""Ajoute idempotence, corrélation et leases aux jobs.

Revision ID: 0019_job_leases
Revises: 0018_project_stage_canonical
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0019_job_leases"
down_revision = "0018_project_stage_canonical"
branch_labels = None
depends_on = None


def _columns() -> dict[str, dict]:
    return {column["name"]: column for column in sa.inspect(op.get_bind()).get_columns("jobs")}


def _indexes() -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("jobs")}


def _project_foreign_key() -> dict | None:
    return next(
        (
            fk
            for fk in sa.inspect(op.get_bind()).get_foreign_keys("jobs")
            if fk["constrained_columns"] == ["project_id"]
        ),
        None,
    )


def upgrade() -> None:
    columns = _columns()
    correlation_added = "correlation_id" not in columns
    if "idempotency_key" not in columns:
        op.add_column("jobs", sa.Column("idempotency_key", sa.String(length=200), nullable=True))
    if correlation_added:
        op.add_column("jobs", sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True))
    if "project_id" not in columns:
        op.add_column("jobs", sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True))
    if "locked_at" not in columns:
        op.add_column("jobs", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    if "heartbeat_at" not in columns:
        op.add_column("jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))

    # Chaque ligne historique reçoit une corrélation stable sans inventer de lien métier.
    op.execute("UPDATE jobs SET correlation_id = id WHERE correlation_id IS NULL")
    if correlation_added:
        op.alter_column("jobs", "correlation_id", nullable=False)
    op.execute(
        """
        UPDATE jobs
        SET locked_at = COALESCE(started_at, created_at)
        WHERE status::text = 'PROCESSING' AND locked_at IS NULL
        """
    )

    # Backfill prudent du projet depuis le JSON historique lorsque la valeur est un UUID.
    op.execute(
        """
        UPDATE jobs
        SET project_id = (payload->>'project_id')::uuid
        WHERE payload ? 'project_id'
          AND payload->>'project_id' ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        """
    )

    indexes = _indexes()
    if "ix_jobs_idempotency_key" not in indexes:
        op.create_index("ix_jobs_idempotency_key", "jobs", ["idempotency_key"], unique=True)
    if "ix_jobs_correlation_id" not in indexes:
        op.create_index("ix_jobs_correlation_id", "jobs", ["correlation_id"])
    if "ix_jobs_project_id" not in indexes:
        op.create_index("ix_jobs_project_id", "jobs", ["project_id"])
    if "ix_jobs_locked_at" not in indexes:
        op.create_index("ix_jobs_locked_at", "jobs", ["locked_at"])
    if _project_foreign_key() is None:
        op.create_foreign_key(
            "fk_jobs_project_id_projects",
            "jobs",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    project_fk = _project_foreign_key()
    if project_fk is not None and project_fk["name"]:
        op.drop_constraint(project_fk["name"], "jobs", type_="foreignkey")
    indexes = _indexes()
    for index in (
        "ix_jobs_locked_at",
        "ix_jobs_project_id",
        "ix_jobs_correlation_id",
        "ix_jobs_idempotency_key",
    ):
        if index in indexes:
            op.drop_index(index, table_name="jobs")
    columns = _columns()
    for column in ("heartbeat_at", "locked_at", "project_id", "correlation_id", "idempotency_key"):
        if column in columns:
            op.drop_column("jobs", column)
