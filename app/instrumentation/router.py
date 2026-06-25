"""Route du tableau de bord d'apprentissage (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.instrumentation.repository import InstrumentationRepository
from app.instrumentation.schemas import LearningDashboardOut
from app.instrumentation.service import AnalyticsService

router = APIRouter(tags=["admin-analytics"])


@router.get("/admin/learning-dashboard", response_model=LearningDashboardOut)
async def learning_dashboard(
    ctx: AuthContext = Depends(require(Permission.AUDIT_READ)),
    session: AsyncSession = Depends(get_session),
) -> LearningDashboardOut:
    # Funnel de transformation (bilan_viewed → action_started → opportunity_interest) + compteurs.
    return await AnalyticsService(InstrumentationRepository(session)).learning_dashboard()
