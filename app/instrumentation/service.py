"""Service d'instrumentation — émission d'événements.

`emit` ajoute l'event à la session courante (flush) ; l'appelant commite (souvent un GET
analytique → commit dédié). Mince et sans métier : on capte, on n'interprète pas ici.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.instrumentation.models import Event

# Catalogue des noms d'événements (le funnel du maillon bilan → action).
BILAN_VIEWED = "bilan_viewed"
ACTION_STARTED = "action_started"


class InstrumentationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def emit(
        self,
        name: str,
        *,
        actor_id: UUID | None = None,
        project_id: UUID | None = None,
        props: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(Event(name=name, actor_id=actor_id, project_id=project_id, props=props or {}))
        await self.session.flush()
