"""Modèle `PitchRubric` — rubrique de pitch versionnée et ancrée.

Calque sur `ScoringGrid` : même logique de robustesse (versionnée, requêtable, validée
avant activation). Les `PitchSession`/`PitchRun`/`PitchDeck` arrivent aux stories suivantes.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SlideKind(str, Enum):
    MAIN = "main"  # pitch deck linéaire (≤ 10)
    BACKUP = "backup"  # slides de réponse aux questions
    SYNTHESIS = "synthesis"  # slide unique « 30 secondes » (urgences)


class PitchDeck(Base):
    __tablename__ = "pitch_decks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), default=None, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="Pitch deck")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PitchSlide(Base):
    __tablename__ = "pitch_slides"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    deck_id: Mapped[UUID] = mapped_column(ForeignKey("pitch_decks.id", ondelete="CASCADE"), index=True)
    kind: Mapped[SlideKind] = mapped_column(default=SlideKind.MAIN, index=True)
    position: Mapped[int] = mapped_column(default=0)
    title: Mapped[str] = mapped_column(String(200), default="")
    extracted_text: Mapped[str] = mapped_column(Text, default="")  # texte vu par les juges
    image_key: Mapped[str | None] = mapped_column(String(300), default=None)  # vignette (V2)


class PitchRubric(Base):
    __tablename__ = "pitch_rubrics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=False, index=True)
    scale_max: Mapped[int] = mapped_column(default=10)
    # axes Fond ancrés (notés par le LLM) : [{key,label,kind,source,weight,central_question,anchors}]
    axes: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
