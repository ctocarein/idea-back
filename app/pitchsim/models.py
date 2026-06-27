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
    # Fichier source persisté (présentation dans le salon, façon partage d'écran).
    source_key: Mapped[str | None] = mapped_column(String(300), default=None)
    source_content_type: Mapped[str | None] = mapped_column(String(100), default=None)
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


class PitchStatus(str, Enum):
    IN_PROGRESS = "in_progress"  # pitch ↔ questions/imprévus (le front pilote les tours)
    DELIBERATING = "deliberating"  # finish déclenché, scoring en cours (PITCH-04)
    COMPLETED = "completed"  # post-mortem disponible
    ABANDONED = "abandoned"  # terminal


class PitchSession(Base):
    __tablename__ = "pitch_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), default=None, index=True
    )
    deck_id: Mapped[UUID | None] = mapped_column(ForeignKey("pitch_decks.id", ondelete="SET NULL"), default=None)
    committee_key: Mapped[str] = mapped_column(String(40))
    mode: Mapped[str] = mapped_column(String(20), default="slides")  # slides | camera
    rubric_version: Mapped[str] = mapped_column(String(40))
    config: Mapped[dict] = mapped_column(JSONB, default=dict)  # imprevus, hard_questions, silence, duration_min
    status: Mapped[PitchStatus] = mapped_column(default=PitchStatus.IN_PROGRESS, index=True)
    # PITCH-06 « comité silencieux » (additif) : sous-phase fine + état d'orchestration.
    phase: Mapped[str] = mapped_column(String(20), default="briefing", index=True)
    # orch = { convictions:{agent:int}, qa_order:[noms], qa_index:int, asked:{axis:[angle]} }
    orch: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(default=None)


class PitchTurn(Base):
    # Un tour = une prise de parole. La SUITE des tours EST la timeline du post-mortem.
    __tablename__ = "pitch_turns"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("pitch_sessions.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(default=0)  # ordre dans la session
    actor: Mapped[str] = mapped_column(String(60))  # porteur | <nom juge> | systeme
    # narration | question | interruption | imprevu | answer | slide_shown | deliberation
    kind: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    slide_id: Mapped[UUID | None] = mapped_column(default=None)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)  # axis, imprevu_type…
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PitchRun(Base):
    # Évaluation d'une session : score Fond (credential, LLM ancré) + Forme (coaching, texte).
    # Rejouable/auditable comme `ScoreRun` (rubric_version + modèle + sortie brute figés).
    __tablename__ = "pitch_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("pitch_sessions.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID | None] = mapped_column(default=None, index=True)  # progression
    rubric_version: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(20), default="llm")  # llm | human | replay
    model: Mapped[str] = mapped_column(String(80), default="")
    raw_output: Mapped[dict | None] = mapped_column(JSONB, default=None)  # audit

    # Fond = le credential (axes ancrés notés par le LLM).
    fond_scores: Mapped[dict] = mapped_column(JSONB, default=dict)  # {axis: 0-10}
    overall_fond: Mapped[float] = mapped_column(default=0.0)
    # Forme = coaching (proxies déterministes, « indicatif »).
    forme_scores: Mapped[dict] = mapped_column(JSONB, default=dict)  # {proxy: 0-10}
    overall_forme: Mapped[float] = mapped_column(default=0.0)
    overall_global: Mapped[float] = mapped_column(default=0.0)

    strengths: Mapped[list] = mapped_column(JSONB, default=list)
    weaknesses: Mapped[list] = mapped_column(JSONB, default=list)
    # Les mots EXACTS de chaque agent en délibération (Règle d'or n°5) : [{agent, text, vote}].
    verdicts: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
