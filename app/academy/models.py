"""Modèles Academy — leçons, progression, sessions modules, fiches de besoin.

`topic` relie une leçon à un levier de la grille (cf. `app/scoring/constants.py::_LEVERS`) :
un axe faible (next_actions) pointe un `topic` → on sert la leçon correspondante.

Les modules Academy suivent un flux en 3 phases :
  context → form → fiches
où le porteur répond à des questions ciblées, remplit un formulaire pré-rempli par l'IA,
puis reçoit des fiches de besoin générées.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Lesson(Base):
    __tablename__ = "academy_lessons"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    topic: Mapped[str] = mapped_column(String(60), index=True)  # ex. "modele_economique"
    summary: Mapped[str] = mapped_column(String(400))
    body: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_progress_user_lesson"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[UUID] = mapped_column(ForeignKey("academy_lessons.id", ondelete="CASCADE"), index=True)
    completed_at: Mapped[datetime] = mapped_column(server_default=func.now())


class GuidedSession(Base):
    """Session de travail sur une dimension du Radar.

    `dimension` : clé de dimension (d1..d12) — None si session "libre" (legacy).
    `phase`     : étape courante du module (context | form | fiches).
    `form_data` : formulaire structuré pré-rempli puis validé par le porteur.
    `section`   : conservé pour compatibilité ascendante (= label de la dimension).
    """

    __tablename__ = "guided_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), default=None, index=True
    )
    section: Mapped[str] = mapped_column(String(80), default="")
    dimension: Mapped[str | None] = mapped_column(String(10), default=None, index=True)  # d1..d12
    phase: Mapped[str] = mapped_column(String(20), default="context")  # context | form | fiches
    draft: Mapped[str] = mapped_column(Text, default="")
    turns: Mapped[list] = mapped_column(JSONB, default=list)
    form_data: Mapped[dict | None] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class NeedFiche(Base):
    """Fiche de besoin générée à la fin d'un module Academy.

    Représente un besoin concret du porteur (développeur, expert, cofondateur…)
    identifié après l'analyse de sa dimension faible. En V2, ces fiches peuvent
    être publiées sur la marketplace.
    """

    __tablename__ = "need_fiches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), default=None, index=True
    )
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("guided_sessions.id", ondelete="SET NULL"), default=None, index=True
    )
    dimension: Mapped[str] = mapped_column(String(10))  # d1..d12
    need_type: Mapped[str] = mapped_column(String(40))  # dev | expert | cofondateur | partenaire | outil | financement | formation | autre
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSONB, default=dict)  # profile, skills, budget, timeline, deliverables, priority, ...
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)  # porteur a confirmé la fiche
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
