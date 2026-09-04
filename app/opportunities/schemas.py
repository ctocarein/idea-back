"""DTO opportunités."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(min_length=1, max_length=200)
    kind: str
    description: str = ""
    sector: str | None = None
    # Seuil sur le score GLOBAL, /100 (SPEC_SCORING_INTEGRITY C3).
    min_overall: float = Field(0.0, ge=0, le=100)
    # Seuil sur la seule dimension D11 « Niveau d'avancement », /10. Ex-`min_maturity` :
    # le nom laissait lire un palier de maturité globale, qui est une autre notion sur une
    # autre échelle (C4). L'ancien nom reste ACCEPTÉ en entrée le temps que les clients suivent.
    min_advancement: int | None = Field(
        None,
        ge=0,
        le=10,
        validation_alias=AliasChoices("min_advancement", "min_maturity"),
    )
    deadline: datetime | None = None
    is_active: bool = True


class OpportunityAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    kind: str
    description: str
    sector: str | None
    min_overall: float  # /100
    min_advancement: int | None  # dimension D11, /10
    deadline: datetime | None
    is_active: bool
    created_at: datetime


class SetActiveIn(BaseModel):
    active: bool
