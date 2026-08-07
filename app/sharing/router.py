"""Routes de partage — création/révocation (porteur) + fiche publique (B2B)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.projects.schemas import VisibilityIn
from app.sharing.dependencies import get_share_service
from app.sharing.schemas import ProjectVisibilityOut, ShareCreateIn, SharedFicheOut, ShareOut, ShareStatsOut
from app.sharing.service import ShareService

router = APIRouter(tags=["sharing"])


@router.post("/projects/{project_id}/share", response_model=ShareOut, status_code=201)
async def create_share(
    project_id: UUID,
    body: ShareCreateIn,
    ctx: AuthContext = Depends(require(Permission.REPORT_READ_OWN)),
    svc: ShareService = Depends(get_share_service),
) -> ShareOut:
    # Le porteur génère un lien de partage (consentement explicite requis).
    return await svc.create_share(ctx, project_id, body.consent)


@router.delete("/projects/{project_id}/share", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    project_id: UUID,
    ctx: AuthContext = Depends(require(Permission.REPORT_READ_OWN)),
    svc: ShareService = Depends(get_share_service),
) -> None:
    await svc.revoke(ctx, project_id)


@router.get("/me/shares", response_model=list[ShareStatsOut])
async def list_my_shares(
    ctx: AuthContext = Depends(require(Permission.REPORT_READ_OWN)),
    svc: ShareService = Depends(get_share_service),
) -> list[ShareStatsOut]:
    return await svc.list_my_shares(ctx)


@router.get("/me/project-visibility", response_model=ProjectVisibilityOut | None)
async def get_my_project_visibility(
    ctx: AuthContext = Depends(require(Permission.REPORT_READ_OWN)),
    svc: ShareService = Depends(get_share_service),
) -> ProjectVisibilityOut | None:
    return await svc.get_my_project_visibility(ctx)


@router.patch("/projects/{project_id}/visibility", status_code=status.HTTP_204_NO_CONTENT)
async def set_project_visibility(
    project_id: UUID,
    body: VisibilityIn,
    ctx: AuthContext = Depends(require(Permission.REPORT_READ_OWN)),
    svc: ShareService = Depends(get_share_service),
) -> None:
    await svc.set_visibility(ctx, project_id, body.is_public)


@router.get("/shared/{token}", response_model=SharedFicheOut)
async def get_shared_fiche(
    token: str,
    svc: ShareService = Depends(get_share_service),
) -> SharedFicheOut:
    # Fiche publique (jury/incubateur) — aucune authentification.
    return await svc.get_fiche(token)
