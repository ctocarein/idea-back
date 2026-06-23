"""Projet + DEUX machines à états distinctes (réconciliation Sprint 2).

Décision : on sépare deux axes qui se confondaient :
  - `diagnostic_status` : pipeline AUTOMATIQUE du « comprendre » (génération du bilan).
  - `review_status`     : curation HUMAINE par l'analyste/admin (qualification, excellence).

Chacune a sa propre machine ; aucune transition implicite, tout saut illégal → 422.
Le segment v2 « transformer » (sprint/certification) sera un 3ᵉ axe ajouté plus tard.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Archetype(str, Enum):
    # Valeur canonique en anglais. Le front envoie parfois "terrain" → alias accepté
    # côté DTO (app/diagnostics/schemas.py), jamais stocké autrement que "field".
    DIGITAL = "digital"  # appli, plateforme, logiciel, service en ligne
    FIELD = "field"  # "terrain" : commerce, production, agro, service local, artisanat


class ProjectStage(str, Enum):
    IDEA = "idea"
    PROTOTYPE = "prototype"
    FIRST_CUSTOMERS = "first_customers"
    GROWING = "growing"


class DiagnosticStatus(str, Enum):
    # Pipeline automatique du segment MVP « comprendre ». Piloté par le worker.
    DRAFT = "draft"  # projet créé, diagnostic pas encore lancé
    DIAGNOSTIC_IN_PROGRESS = "diagnostic_in_progress"
    DIAGNOSTIC_COMPLETED = "diagnostic_completed"
    BILAN_READY = "bilan_ready"  # Radar + tableau de compréhension disponibles
    ARCHIVED = "archived"  # terminal


class ReviewStatus(str, Enum):
    # Curation humaine (analyste/admin). Vocabulaire aligné sur le front.
    NEW_DIAGNOSTIC = "new_diagnostic"
    IN_REVIEW = "in_review"
    NEEDS_WORK = "needs_work"
    QUALIFIED = "qualified"
    EXCELLENCE = "excellence"  # projet d'excellence → présentation concierge
    REJECTED = "rejected"  # hors cible


# Pipeline diagnostic (automatique). En MVP, seules ces transitions sont câblées.
DIAGNOSTIC_TRANSITIONS: dict[DiagnosticStatus, list[DiagnosticStatus]] = {
    DiagnosticStatus.DRAFT: [
        DiagnosticStatus.DIAGNOSTIC_IN_PROGRESS,
        DiagnosticStatus.ARCHIVED,
    ],
    DiagnosticStatus.DIAGNOSTIC_IN_PROGRESS: [
        DiagnosticStatus.DIAGNOSTIC_COMPLETED,
        DiagnosticStatus.ARCHIVED,
    ],
    DiagnosticStatus.DIAGNOSTIC_COMPLETED: [DiagnosticStatus.BILAN_READY],
    DiagnosticStatus.BILAN_READY: [DiagnosticStatus.ARCHIVED],
}

# Curation humaine (miroir de la machine front status-machine.ts).
REVIEW_TRANSITIONS: dict[ReviewStatus, list[ReviewStatus]] = {
    ReviewStatus.NEW_DIAGNOSTIC: [ReviewStatus.IN_REVIEW],
    ReviewStatus.IN_REVIEW: [
        ReviewStatus.QUALIFIED,
        ReviewStatus.NEEDS_WORK,
        ReviewStatus.REJECTED,
    ],
    ReviewStatus.NEEDS_WORK: [ReviewStatus.IN_REVIEW],
    ReviewStatus.QUALIFIED: [ReviewStatus.EXCELLENCE, ReviewStatus.NEEDS_WORK],
    ReviewStatus.EXCELLENCE: [ReviewStatus.QUALIFIED],
    ReviewStatus.REJECTED: [ReviewStatus.IN_REVIEW],
}


def can_transition_diagnostic(current: DiagnosticStatus, target: DiagnosticStatus) -> bool:
    return target in DIAGNOSTIC_TRANSITIONS.get(current, [])


def can_transition_review(current: ReviewStatus, target: ReviewStatus) -> bool:
    return target in REVIEW_TRANSITIONS.get(current, [])


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    # "sector" porte la clé de catégorie (agritech, fintech…) qui pilote le diagnostic.
    sector: Mapped[str] = mapped_column(String(120))
    archetype: Mapped[Archetype] = mapped_column(default=Archetype.FIELD)
    stage: Mapped[ProjectStage] = mapped_column(default=ProjectStage.IDEA)
    # Deux statuts indépendants (cf. en-tête de module).
    diagnostic_status: Mapped[DiagnosticStatus] = mapped_column(default=DiagnosticStatus.DRAFT, index=True)
    review_status: Mapped[ReviewStatus] = mapped_column(default=ReviewStatus.NEW_DIAGNOSTIC, index=True)
    # Analyste/mentor assigné (curation). Null tant que non assigné.
    assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
