"""Événements d'instrumentation — la donnée brute du funnel de transformation.

Posé tôt (GUIDE §9 : « émettre les événements dès qu'ils existent ») : le tableau de bord
d'apprentissage (épic INSTRUM) n'aura qu'à agréger. Un event = un fait daté + des props libres.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80), index=True)  # ex. "bilan_viewed"
    actor_id: Mapped[UUID | None] = mapped_column(index=True, default=None)
    project_id: Mapped[UUID | None] = mapped_column(index=True, default=None)
    props: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
