"""DTO supervision des jobs (admin)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    idempotency_key: str | None
    correlation_id: UUID
    project_id: UUID | None
    status: str
    priority: int
    retry_count: int
    max_retries: int
    error_message: str | None
    scheduled_at: datetime
    started_at: datetime | None
    locked_at: datetime | None
    heartbeat_at: datetime | None
    created_at: datetime
