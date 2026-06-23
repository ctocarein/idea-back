"""Routes scoring — exposition de la grille Radar active.

La grille est une donnée de référence non sensible (utilisée jusque sur le public) :
lecture ouverte, pas de permission requise.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.scoring.repository import ScoreRunRepository, ScoringRepository
from app.scoring.schemas import GridOut
from app.scoring.service import ScoringService

router = APIRouter(prefix="/scoring", tags=["scoring"])


def get_scoring_service(session: AsyncSession = Depends(get_session)) -> ScoringService:
    return ScoringService(ScoringRepository(session), ScoreRunRepository(session))


@router.get("/grid", response_model=GridOut)
async def get_grid(svc: ScoringService = Depends(get_scoring_service)) -> GridOut:
    return await svc.get_active_grid()
