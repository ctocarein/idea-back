"""Modèle `PitchRubric` — rubrique de pitch versionnée et ancrée.

Calque sur `ScoringGrid` : même logique de robustesse (versionnée, requêtable, validée
avant activation). Les `PitchSession`/`PitchRun`/`PitchDeck` arrivent aux stories suivantes.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PitchRubric(Base):
    __tablename__ = "pitch_rubrics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=False, index=True)
    scale_max: Mapped[int] = mapped_column(default=10)
    # axes Fond ancrés (notés par le LLM) : [{key,label,kind,source,weight,central_question,anchors}]
    axes: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
