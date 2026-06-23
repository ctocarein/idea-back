"""Modèle du diagnostic — l'ENTRÉE du porteur (le score/bilan vit dans `reports`).

Deux modes :
  - GUIDED   : le porteur écrit son idée + répond aux questions par catégorie (flow A).
  - DOCUMENT : le porteur uploade un document, extrait par le worker (flow B).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EntryMode(str, Enum):
    GUIDED = "guided"  # "J'ai une idée à explorer"
    DOCUMENT = "document"  # "J'ai déjà un document"


class Diagnostic(Base):
    __tablename__ = "diagnostics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[EntryMode]
    description: Mapped[str | None] = mapped_column(Text, default=None)
    # Réponses aux questions guidées : { questionId: réponse } (flow A).
    answers: Mapped[dict | None] = mapped_column(JSONB, default=None)
    funding_need: Mapped[int | None] = mapped_column(default=None)  # FCFA
    # Document source (flow B) — l'extraction texte est faite par le worker.
    document_id: Mapped[UUID | None] = mapped_column(default=None)
    consent_at: Mapped[datetime] = mapped_column(server_default=func.now())  # RGPD
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
