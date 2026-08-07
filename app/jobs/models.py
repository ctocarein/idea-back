"""Modèle de la file de jobs (table `jobs`).

On conserve le pattern Postgres (table + FOR UPDATE SKIP LOCKED) plutôt qu'un broker
externe : moins de dépendances, traçabilité et résidence des données dans Postgres.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(String(80), index=True)  # ex. "run_diagnostic"
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Une commande métier ne doit produire qu'un seul job. Nullable pour les
    # anciennes lignes et les tâches volontairement non idempotentes.
    idempotency_key: Mapped[str | None] = mapped_column(String(200), unique=True, index=True, default=None)
    correlation_id: Mapped[UUID] = mapped_column(index=True, default=uuid4)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True, default=None
    )
    status: Mapped[JobStatus] = mapped_column(default=JobStatus.PENDING, index=True)
    priority: Mapped[int] = mapped_column(default=100)  # plus petit = plus prioritaire
    retry_count: Mapped[int] = mapped_column(default=0)
    max_retries: Mapped[int] = mapped_column(default=3)
    scheduled_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    # Lease renouvelé par le worker. Une lease expirée signale un worker mort
    # et permet de remettre le job en file sans intervention humaine.
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, default=None)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(String(2000), default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
