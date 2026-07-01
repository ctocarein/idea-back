"""Modèle du pitch (éditeur V1.2).

Un pitch appartient à un porteur et (optionnellement) à un projet. Les sections
sont stockées en JSONB : liste de {key, title, content}. Le contenu est amorcé
par l'IA depuis les synthèses du Workshop puis édité librement par le porteur.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Pitch(Base):
    __tablename__ = "pitches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), default=None, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="Mon pitch")
    # Sections : [{ "key": "problem", "title": "Problème", "content": "…" }, ...].
    sections: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
