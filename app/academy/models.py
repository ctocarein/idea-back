"""Modèles Academy — leçons, progression, sessions « construire guidé ».

`topic` relie une leçon à un levier de la grille (cf. `app/scoring/constants.py::_LEVERS`) :
un axe faible (next_actions) pointe un `topic` → on sert la leçon correspondante. C'est ce
qui ferme la boucle bilan → action.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
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
    position: Mapped[int] = mapped_column(default=0)  # ordre d'affichage
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class LearningProgress(Base):
    # Une ligne = une leçon complétée par un porteur.
    __tablename__ = "learning_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_progress_user_lesson"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[UUID] = mapped_column(ForeignKey("academy_lessons.id", ondelete="CASCADE"), index=True)
    completed_at: Mapped[datetime] = mapped_column(server_default=func.now())


class GuidedSession(Base):
    # « Construire guidé » : le porteur écrit, l'IA explique/questionne (jamais à sa place).
    __tablename__ = "guided_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), default=None, index=True
    )
    section: Mapped[str] = mapped_column(String(80))  # ex. "probleme", "modele_economique"
    draft: Mapped[str] = mapped_column(Text, default="")  # le texte ÉCRIT par le porteur
    # Historique de l'accompagnement : [{role: porteur|coach, text: ...}].
    turns: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
