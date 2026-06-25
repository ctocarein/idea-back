"""DTO supervision des jobs (admin)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    status: str
    priority: int
    retry_count: int
    max_retries: int
    error_message: str | None
    scheduled_at: datetime
    created_at: datetime
