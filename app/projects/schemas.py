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
    is_public: bool
    created_at: datetime


class ProjectAdminDetailOut(ProjectAdminOut):
    """Fiche projet côté back-office : la liste, plus le dernier bilan du projet.

    Sans `latest_report_id`, l'analyste assigné n'a AUCUN chemin vers
    `PATCH /reports/{id}/scores|report` : la garde de ces routes le désigne
    explicitement (`guard_assigned_or_admin`), mais `GET /reports` est owner-scoped —
    il ne pouvait donc pas découvrir l'identifiant du bilan qu'il est censé reprendre.

    Volontairement absent de la liste : le résoudre pour chaque ligne coûterait une
    requête par projet, pour une information dont seule la fiche a besoin.
    """

    latest_report_id: UUID | None = None


class ReviewTransitionIn(BaseModel):
    target: ReviewStatus  # validé contre la machine REVIEW_TRANSITIONS dans le service


class AssigneeIn(BaseModel):
    assignee_id: UUID | None  # None = désassigner


class VisibilityIn(BaseModel):
    is_public: bool
