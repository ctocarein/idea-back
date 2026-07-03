"""Routes du Studio — logo (tranche 2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.ratelimit import rate_limit
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.studio.dependencies import get_logo_service
from app.studio.schemas import LogoOut, LogoSelectIn, LogoUpdateIn
from app.studio.service import LogoService

router = APIRouter(prefix="/studio", tags=["studio"])


@router.get("/logo", response_model=LogoOut)
async def get_logo(
    ctx: AuthContext = Depends(require(Permission.STUDIO_EDIT)),
    svc: LogoService = Depends(get_logo_service),
) -> LogoOut:
    return await svc.get_or_create(ctx)


@router.get("/kit")
async def get_kit(
    ctx: AuthContext = Depends(require(Permission.STUDIO_EDIT)),
    svc: LogoService = Depends(get_logo_service),
) -> dict:
    return await svc.get_kit(ctx)


@router.post(
    "/logo/{logo_id}/generate",
    response_model=LogoOut,
    # Génération = appel LLM : anti-abus coût (fail-closed si Redis down).
    dependencies=[Depends(rate_limit("logo_generate", limit=12, window_seconds=60, fail_open=False))],
)
async def generate_logo(
    logo_id: UUID,
    ctx: AuthContext = Depends(require(Permission.STUDIO_EDIT)),
    svc: LogoService = Depends(get_logo_service),
) -> LogoOut:
    return await svc.generate(ctx, logo_id)


@router.post("/logo/{logo_id}/select", response_model=LogoOut)
async def select_variation(
    logo_id: UUID,
    body: LogoSelectIn,
    ctx: AuthContext = Depends(require(Permission.STUDIO_EDIT)),
    svc: LogoService = Depends(get_logo_service),
) -> LogoOut:
    return await svc.select(ctx, logo_id, body.index)


@router.patch("/logo/{logo_id}", response_model=LogoOut)
async def update_logo(
    logo_id: UUID,
    body: LogoUpdateIn,
    ctx: AuthContext = Depends(require(Permission.STUDIO_EDIT)),
    svc: LogoService = Depends(get_logo_service),
) -> LogoOut:
    return await svc.update_spec(ctx, logo_id, body)
