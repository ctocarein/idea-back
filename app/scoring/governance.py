"""Gouvernance de la grille Radar (admin) — lister les versions, activer une version.

La grille est versionnée (`ScoringGrid`) ; une seule est active. L'activation est auditée.
L'AUTHORING complet d'une grille (rédaction des ancres) se fait en atelier puis seed/migration.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.core.database import get_session
from app.core.errors import NotFoundError
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.scoring.repository import ScoringRepository

router = APIRouter(tags=["admin-scoring"])


class GridSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: str
    is_active: bool
    scale_max: int
    created_at: datetime


@router.get("/admin/scoring/grids", response_model=list[GridSummaryOut])
async def list_grids(
    ctx: AuthContext = Depends(require(Permission.USER_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> list[GridSummaryOut]:
    grids = await ScoringRepository(session).list_grids()
    return [GridSummaryOut.model_validate(g) for g in grids]


@router.post("/admin/scoring/grids/{version}/activate", response_model=GridSummaryOut)
async def activate_grid(
    version: str,
    ctx: AuthContext = Depends(require(Permission.USER_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> GridSummaryOut:
    repo = ScoringRepository(session)
    grid = await repo.get_by_version(version)
    if grid is None:
        raise NotFoundError("scoring_grid")
    await repo.activate(grid)
    await AuditService(session).record(
        actor_id=ctx.user.id,
        action="scoring_grid.activated",
        entity="scoring_grid",
        entity_id=grid.id,
        new_value={"version": version},
    )
    await session.commit()
    return GridSummaryOut.model_validate(grid)
