"""DTO audit (lecture)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID | None
    action: str
    entity: str
    entity_id: UUID | None
    old_value: dict | None
    new_value: dict | None
    created_at: datetime
