"""Modèle d'audit — journal des actions sensibles.

Toute action sensible (changement de statut, grant, invitation, approbation,
suppression RGPD) produit une ligne ici, DANS la même transaction que l'action.
Si l'audit échoue, la transaction échoue : pas d'action sensible sans trace.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(index=True)  # None = action système
    action: Mapped[str] = mapped_column(String(120), index=True)  # ex. "project.status_changed"
    entity: Mapped[str] = mapped_column(String(60), index=True)  # ex. "project"
    entity_id: Mapped[UUID | None] = mapped_column(index=True)
    # old/new value et métadonnées libres en JSONB (lisible et requêtable).
    old_value: Mapped[dict | None] = mapped_column(JSONB, default=None)
    new_value: Mapped[dict | None] = mapped_column(JSONB, default=None)
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(400), default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
