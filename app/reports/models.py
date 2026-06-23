"""Modèle du bilan (`reports`) — tableau de compréhension + score Radar + PDF.

Le bilan est produit par le worker (job generate_bilan) à partir de l'analyse LLM et de
la grille Radar. Il est consultable au dashboard (jamais envoyé par email — BESOINS_PORTEUR
cas 8). Le PDF est stocké dans MinIO et servi en presigned download.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReportStatus(str, Enum):
    PENDING = "pending"  # en cours de génération (job en file/retry)
    READY = "ready"  # disponible (score + PDF)
    FAILED = "failed"  # échec définitif (alerte admin)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    diagnostic_id: Mapped[UUID | None] = mapped_column(default=None, index=True)
    title: Mapped[str] = mapped_column(String(200), default="Bilan de compréhension")
    status: Mapped[ReportStatus] = mapped_column(default=ReportStatus.PENDING, index=True)
    # Score Radar produit : { "gridVersion": "...", "axes": { "probleme": 72, ... } }.
    grid_version: Mapped[str | None] = mapped_column(String(40), default=None)
    radar_score: Mapped[dict | None] = mapped_column(JSONB, default=None)
    # Tableau de compréhension agrégé (3 lentilles) pour la vue porteur.
    comprehension: Mapped[dict | None] = mapped_column(JSONB, default=None)
    # Couche qualitative : résumé, benchmark, concurrence, maturité, forces, risques…
    insights: Mapped[dict | None] = mapped_column(JSONB, default=None)
    # Prochaines actions dérivées des axes faibles (routage déterministe vers les leviers).
    next_actions: Mapped[list | None] = mapped_column(JSONB, default=None)
    pdf_document_id: Mapped[UUID | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
