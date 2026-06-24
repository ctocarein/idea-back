"""DTO opportunités."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    kind: str
    description: str
    sector: str | None
    deadline: datetime | None
    # Calculés pour le projet ciblé :
    eligible: bool = False
    missing: list[str] = []


class InterestIn(BaseModel):
    project_id: UUID
