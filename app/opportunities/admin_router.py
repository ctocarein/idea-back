"""Routes back-office opportunités — CRUD catalogue (admin uniquement)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.opportunities.dependencies import get_opportunity_service
from app.opportunities.schemas import OpportunityAdminOut, OpportunityIn, SetActiveIn
from app.opportunities.service import OpportunityService

router = APIRouter(prefix="/admin/opportunities", tags=["admin-opportunities"])

_require_admin = require(Permission.OPPORTUNITY_MANAGE)


@router.get("", response_model=list[OpportunityAdminOut])
async def list_all_opportunities(
    ctx: AuthContext = Depends(_require_admin),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> list[OpportunityAdminOut]:
    return await svc.admin_list_all(ctx)


@router.post("", response_model=OpportunityAdminOut, status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    body: OpportunityIn,
    ctx: AuthContext = Depends(_require_admin),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> OpportunityAdminOut:
    return await svc.admin_create(ctx, body)


@router.put("/{opportunity_id}", response_model=OpportunityAdminOut)
async def update_opportunity(
    opportunity_id: UUID,
    body: OpportunityIn,
    ctx: AuthContext = Depends(_require_admin),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> OpportunityAdminOut:
    return await svc.admin_update(ctx, opportunity_id, body)


@router.patch("/{opportunity_id}/active", response_model=OpportunityAdminOut)
async def set_opportunity_active(
    opportunity_id: UUID,
    body: SetActiveIn,
    ctx: AuthContext = Depends(_require_admin),
    svc: OpportunityService = Depends(get_opportunity_service),
) -> OpportunityAdminOut:
    return await svc.admin_set_active(ctx, opportunity_id, active=body.active)
