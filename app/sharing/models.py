"""Partage de fiche projet (B2B) — lien à token, gated par le consentement du porteur.

Le porteur contrôle la visibilité : il crée un lien (consentement explicite horodaté) et peut
le révoquer. Le token n'est jamais stocké en clair (hash). La fiche publique ne montre que la
*lecture jury/incubateur* (score + synthèse + forces), jamais les internes du bilan.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProjectShare(Base):
    __tablename__ = "project_shares"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    consent_at: Mapped[datetime] = mapped_column()  # consentement explicite du porteur (RGPD)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)  # révocable
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
