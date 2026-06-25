"""DTO back-office projets (admin / analyste)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.projects.models import ReviewStatus


class ProjectAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    title: str
    sector: str
    archetype: str
    stage: str
    diagnostic_status: str
    review_status: str
    assignee_id: UUID | None
    created_at: datetime


class ReviewTransitionIn(BaseModel):
    target: ReviewStatus  # validé contre la machine REVIEW_TRANSITIONS dans le service


class AssigneeIn(BaseModel):
    assignee_id: UUID | None  # None = désassigner
