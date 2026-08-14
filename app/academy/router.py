"""Routes Academy — modules guidés (Workshop) et fiches de besoin."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.academy.dependencies import get_academy_service
from app.academy.schemas import (
    FicheShareOut,
    ModuleFormIn,
    ModuleSessionOut,
    ModuleStartIn,
    ModuleTurnIn,
    NeedFicheOut,
    SharedFicheOut,
    WeaknessListOut,
)
from app.academy.service import AcademyService
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission

router = APIRouter(prefix="/academy", tags=["academy"])


# --- Modules Academy (nouveaux) ---


@router.get("/my-weaknesses", response_model=WeaknessListOut)
async def get_my_weaknesses(
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> WeaknessListOut:
    return await svc.get_my_weaknesses(ctx)


@router.post("/modules/start", response_model=ModuleSessionOut, status_code=201)
async def start_module(
    body: ModuleStartIn,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> ModuleSessionOut:
    return await svc.start_module(ctx, dimension=body.dimension, project_id=body.project_id)


@router.post("/modules/{session_id}/turn", response_model=ModuleSessionOut)
async def module_turn(
    session_id: UUID,
    body: ModuleTurnIn,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> ModuleSessionOut:
    return await svc.module_turn(ctx, session_id, body.message)


@router.post("/modules/{session_id}/prefill-form", response_model=ModuleSessionOut)
async def prefill_form(
    session_id: UUID,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> ModuleSessionOut:
    return await svc.prefill_form(ctx, session_id)


@router.patch("/modules/{session_id}/form", response_model=ModuleSessionOut)
async def save_module_form(
    session_id: UUID,
    body: ModuleFormIn,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> ModuleSessionOut:
    return await svc.save_module_form(ctx, session_id, body.form_data)


@router.post("/modules/{session_id}/generate-fiches", response_model=ModuleSessionOut)
async def generate_fiches(
    session_id: UUID,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> ModuleSessionOut:
    return await svc.generate_fiches(ctx, session_id)


@router.post("/modules/{session_id}/rescore", response_model=ModuleSessionOut)
async def rescore_axis(
    session_id: UUID,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> ModuleSessionOut:
    return await svc.rescore_axis(ctx, session_id)


@router.get("/modules/{session_id}", response_model=ModuleSessionOut)
async def get_module(
    session_id: UUID,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> ModuleSessionOut:
    return await svc.get_module(ctx, session_id)


@router.get("/my-fiches", response_model=list[NeedFicheOut])
async def list_my_fiches(
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> list[NeedFicheOut]:
    return await svc.list_my_fiches(ctx)


@router.post("/fiches/{fiche_id}/validate", response_model=NeedFicheOut)
async def validate_fiche(
    fiche_id: UUID,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> NeedFicheOut:
    return await svc.validate_fiche(ctx, fiche_id)


@router.get("/fiches/{fiche_id}/pdf")
async def export_fiche_pdf(
    fiche_id: UUID,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> Response:
    try:
        pdf = await svc.get_fiche_pdf(ctx, fiche_id)
    except ImportError as exc:  # WeasyPrint absent → dégradation propre.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Génération PDF indisponible (extra pdf non installé).",
        ) from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="besoin-{str(fiche_id)[:8]}.pdf"'},
    )


@router.post("/fiches/{fiche_id}/share", response_model=FicheShareOut, status_code=201)
async def share_fiche(
    fiche_id: UUID,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> FicheShareOut:
    return await svc.share_fiche(ctx, fiche_id)


@router.delete("/fiches/{fiche_id}/share", status_code=status.HTTP_204_NO_CONTENT)
async def unshare_fiche(
    fiche_id: UUID,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> None:
    await svc.unshare_fiche(ctx, fiche_id)


@router.get("/shared-fiche/{token}", response_model=SharedFicheOut)
async def get_shared_fiche(
    token: str,
    svc: AcademyService = Depends(get_academy_service),
) -> SharedFicheOut:
    # Public : aucune auth (lecture seule, données non personnelles).
    return await svc.get_shared_fiche(token)
