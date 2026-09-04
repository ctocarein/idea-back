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


class DraftFunnelOut(BaseModel):
    """Diagnostic en cours — mesure du décrochage pendant la saisie."""

    created: int
    submitted: int
    completion_rate: float  # soumis / créés (0..1)
    dropoff_by_dimension: dict[str, int]
    median_resume_delay_seconds: float | None = None


class ReminderStatsOut(BaseModel):
    """Rappels J+7 — envoyés, annulés (par motif), désabonnements.

    Le taux de désabonnement est le SIGNAL D'ALERTE : élevé, il signifie que le mail est
    perçu comme du marketing, ce qui invaliderait le principe même du rappel.
    """

    sent: int
    cancelled: int
    cancelled_by_reason: dict[str, int]
    opted_out_users: int
