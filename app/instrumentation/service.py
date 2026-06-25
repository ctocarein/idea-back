"""Service d'instrumentation — émission d'événements.

`emit` ajoute l'event à la session courante (flush) ; l'appelant commite (souvent un GET
analytique → commit dédié). Mince et sans métier : on capte, on n'interprète pas ici.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.instrumentation.models import Event
from app.instrumentation.repository import InstrumentationRepository
from app.instrumentation.schemas import FunnelStageOut, LearningDashboardOut

# Catalogue des noms d'événements (le funnel du maillon bilan → action).
BILAN_VIEWED = "bilan_viewed"
ACTION_STARTED = "action_started"
OPPORTUNITY_INTEREST = "opportunity_interest"  # le porteur exprime un intérêt → signal B2B

# Le funnel de transformation, dans l'ordre.
FUNNEL_STAGES = [BILAN_VIEWED, ACTION_STARTED, OPPORTUNITY_INTEREST]


class AnalyticsService:
    """Agrège les événements en tableau de bord d'apprentissage (le freemium apprenant)."""

    def __init__(self, repo: InstrumentationRepository) -> None:
        self.repo = repo

    async def learning_dashboard(self) -> LearningDashboardOut:
        counts = await self.repo.counts_by_name()
        actors = {s: await self.repo.distinct_actors_for(s) for s in FUNNEL_STAGES}
        base = actors[FUNNEL_STAGES[0]] or 0
        funnel = [
            FunnelStageOut(
                stage=s,
                actors=actors[s],
                conversion=round(actors[s] / base, 3) if base else 0.0,
            )
            for s in FUNNEL_STAGES
        ]
        return LearningDashboardOut(total_events=sum(counts.values()), event_counts=counts, funnel=funnel)


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
