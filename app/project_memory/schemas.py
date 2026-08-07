"""DTO de lecture et d'écriture de la mémoire projet."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.project_memory.models import EvidenceState, MemoryItemType, ProvenanceType


class FounderMemoryCreateIn(BaseModel):
    dimension: str = Field(pattern=r"^d([1-9]|1[0-2])$")
    item_type: Literal["fact", "declaration", "hypothesis"] = "declaration"
    statement: str = Field(min_length=3, max_length=4000)
    deduplication_key: str | None = Field(default=None, min_length=1, max_length=160)
    supersedes_id: UUID | None = None
    occurred_at: datetime | None = None
    expires_at: datetime | None = None


class ProjectMemoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    dimension: str
    item_type: MemoryItemType
    evidence_state: EvidenceState
    statement: str
    provenance_type: ProvenanceType
    source_ref: str | None
    source_excerpt: str | None
    attributes: dict
    supersedes_id: UUID | None
    is_active: bool
    occurred_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
