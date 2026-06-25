"""DTO du tableau de bord d'apprentissage."""

from __future__ import annotations

from pydantic import BaseModel


class FunnelStageOut(BaseModel):
    stage: str
    actors: int  # porteurs distincts ayant atteint l'étape
    conversion: float  # part depuis la 1re étape (0..1)


class LearningDashboardOut(BaseModel):
    total_events: int
    event_counts: dict[str, int]
    funnel: list[FunnelStageOut]  # bilan_viewed → action_started → opportunity_interest
