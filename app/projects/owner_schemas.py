"""Contrat de l'espace projet unifié destiné au porteur."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.project_memory.schemas import ProjectMemoryItemOut


class OwnerProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    sector: str
    archetype: str
    stage: str
    diagnostic_status: str
    review_status: str
    is_public: bool
    created_at: datetime
    updated_at: datetime


class WorkspaceReportOut(BaseModel):
    id: UUID
    status: str
    grid_version: str | None
    radar_score: dict | None
    next_actions: list = Field(default_factory=list)
    created_at: datetime


class WorkspaceDocumentsOut(BaseModel):
    total: int
    confirmed: int


class WorkspaceMemoryOut(BaseModel):
    total_active: int
    by_state: dict[str, int]
    by_dimension: dict[str, int]
    recent: list[ProjectMemoryItemOut]


class ProjectWorkspaceOut(BaseModel):
    project: OwnerProjectOut
    latest_report: WorkspaceReportOut | None
    next_actions: list = Field(default_factory=list)
    documents: WorkspaceDocumentsOut
    memory: WorkspaceMemoryOut
