"""Modèle du logo (Studio, tranche 2).

Un logo appartient à un porteur et (optionnellement) à un projet. `spec` est le logo
courant (source de vérité du rendu, éditable) ; `variations` garde le dernier lot généré
pour permettre de re-choisir. Le spec est un dict curé (cf `app.studio.vocab`).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Logo(Base):
    __tablename__ = "logos"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), default=None, index=True
    )
    # Logo courant (dict curé : name, mark_type, palette, font, layout…). None = pas encore généré.
    spec: Mapped[dict | None] = mapped_column(JSONB, default=None)
    # Dernier lot de variations proposé (liste de specs) — pour re-choisir sans régénérer.
    variations: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
