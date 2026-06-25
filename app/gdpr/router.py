"""Routes RGPD — export & effacement des données du compte courant."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status

from app.gdpr.dependencies import get_gdpr_service
from app.gdpr.service import GdprService
from app.iam.dependencies import AuthContext, get_current_user

router = APIRouter(tags=["rgpd"])


@router.get("/me/export")
async def export_my_data(
    ctx: AuthContext = Depends(get_current_user),
    svc: GdprService = Depends(get_gdpr_service),
) -> dict[str, Any]:
    # Portabilité : toutes les données personnelles du porteur, en JSON.
    return await svc.export(ctx)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    ctx: AuthContext = Depends(get_current_user),
    svc: GdprService = Depends(get_gdpr_service),
) -> None:
    # Droit à l'oubli : suppression du compte + cascade (DB) + objets MinIO (best-effort).
    await svc.delete_me(ctx)
