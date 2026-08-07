"""Contrat API du Radar explicable."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.project_memory.models import EvidenceState


class DimensionEvaluationOut(BaseModel):
    dimension: str
    code: str
    label: str
    pillar: str
    score: int | None
    confidence: float
    evidence_state: EvidenceState
    rationale: str
    contradictions: list[dict[str, str]] = Field(default_factory=list)
    missing_information: str = ""
    next_action: dict = Field(default_factory=dict)
    score_run_id: UUID | None = None
    evaluated_at: datetime | None = None


class AdaptiveQuestionOut(BaseModel):
    dimension: str
    code: str
    label: str
    question: str
    reason: str
    priority: float


class ProjectEvaluationOut(BaseModel):
    project_id: UUID
    grid_version: str | None
    dimensions: list[DimensionEvaluationOut]
    questions: list[AdaptiveQuestionOut] = Field(default_factory=list)
