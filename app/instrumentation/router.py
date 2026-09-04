"""Route du tableau de bord d'apprentissage (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.instrumentation.repository import InstrumentationRepository
from app.instrumentation.schemas import (
    DraftFunnelOut,
    LearningDashboardOut,
    ReminderStatsOut,
)
from app.instrumentation.service import AnalyticsService

router = APIRouter(tags=["admin-analytics"])


@router.get("/admin/learning-dashboard", response_model=LearningDashboardOut)
async def learning_dashboard(
    ctx: AuthContext = Depends(require(Permission.AUDIT_READ)),
    session: AsyncSession = Depends(get_session),
) -> LearningDashboardOut:
    # Funnel de transformation (bilan_viewed → action_started → opportunity_interest) + compteurs.
    return await AnalyticsService(InstrumentationRepository(session)).learning_dashboard()


@router.get("/admin/draft-funnel", response_model=DraftFunnelOut)
async def draft_funnel(
    ctx: AuthContext = Depends(require(Permission.AUDIT_READ)),
    session: AsyncSession = Depends(get_session),
) -> DraftFunnelOut:
    # Taux de complétion, dimension de décrochage, délai de reprise — la sortie qui
    # justifie la persistance serveur des brouillons.
    return await AnalyticsService(InstrumentationRepository(session)).draft_funnel()


@router.get("/admin/reminder-stats", response_model=ReminderStatsOut)
async def reminder_stats(
    ctx: AuthContext = Depends(require(Permission.AUDIT_READ)),
    session: AsyncSession = Depends(get_session),
) -> ReminderStatsOut:
    # Sans mesure, le chantier « rappel » est invérifiable. Le taux de désabonnement est le
    # signal d'alerte : élevé, il invalide le principe directeur.
    return await AnalyticsService(InstrumentationRepository(session)).reminder_stats()
