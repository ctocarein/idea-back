"""Routes opportunités — l'orientation/visibilité du porteur (face amont du pont B2B)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.iam.dependencies import AuthContext, get_current_user
from app.opportunities.dependencies import get_opportunity_service
from app.opportunities.schemas import InterestIn, OpportunityOut
from app.opportunities.service import OpportunityService

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.get("", response_model=list[OpportunityOut])
async def list_opportunities(
    project_id: UUID,
    eligible_only: bool = False,
    ctx: AuthContext = Depends(get_current_user),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> list[OpportunityOut]:
    # Pour le projet ciblé : éligibilité déterministe + « ce qu'il te manque pour viser plus haut ».
    return await svc.list_for_project(ctx, project_id, eligible_only=eligible_only)


@router.post("/{opportunity_id}/interest", status_code=status.HTTP_204_NO_CONTENT)
async def express_interest(
    opportunity_id: UUID,
    body: InterestIn,
    ctx: AuthContext = Depends(get_current_user),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> None:
    await svc.express_interest(ctx, opportunity_id, body.project_id)
