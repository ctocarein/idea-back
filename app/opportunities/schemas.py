"""DTO opportunités."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


# --- Admin -------------------------------------------------------------------


class OpportunityIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: str
    description: str = ""
    sector: str | None = None
    min_overall: float = Field(0.0, ge=0, le=10)
    min_maturity: int | None = Field(None, ge=0, le=10)
    deadline: datetime | None = None
    is_active: bool = True


class OpportunityAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    kind: str
    description: str
    sector: str | None
    min_overall: float
    min_maturity: int | None
    deadline: datetime | None
    is_active: bool
    created_at: datetime


class SetActiveIn(BaseModel):
    active: bool
