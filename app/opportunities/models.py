"""Modèle opportunité — catalogue curé (concours, hackathons, incubateurs, mentorat).

L'éligibilité est DÉTERMINISTE (cf. `eligibility.py`) : on compare le score/maturité/secteur
du projet aux critères de l'opportunité. Même esprit que le routage `next_actions` (zéro LLM).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OpportunityKind(str, Enum):
    CONCOURS = "concours"
    HACKATHON = "hackathon"
    INCUBATEUR = "incubateur"
    MENTORAT = "mentorat"
    FINANCEMENT = "financement"


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[OpportunityKind] = mapped_column(index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    # Critères d'éligibilité (tous optionnels = pas de contrainte sur ce critère).
    sector: Mapped[str | None] = mapped_column(String(120), default=None)  # None = tous secteurs
    min_overall: Mapped[float] = mapped_column(Numeric(4, 1), default=0)  # score global /10
    min_maturity: Mapped[int | None] = mapped_column(default=None)  # axe D11 avancement /10
    deadline: Mapped[datetime | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
