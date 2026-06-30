"""Routes Academy — leçons, progression, modules guidés, fiches de besoin."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.academy.dependencies import get_academy_service
from app.academy.schemas import (
    AcademyProgressOut,
    GuidedDraftIn,
    GuidedSessionOut,
    GuidedStartIn,
    GuidedTurnIn,
    LessonDetailOut,
    LessonOut,
    ModuleFormIn,
    ModuleSessionOut,
    ModuleTurnIn,
    NeedFicheOut,
    WeaknessListOut,
)
from app.academy.service import AcademyService
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission

router = APIRouter(prefix="/academy", tags=["academy"])


# --- Leçons ---


@router.get("/lessons", response_model=list[LessonOut])
async def list_lessons(
    topic: str | None = None,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_READ)),
    svc: AcademyService = Depends(get_academy_service),
) -> list[LessonOut]:
    return await svc.list_lessons(topic=topic)


@router.get("/progress", response_model=AcademyProgressOut)
async def get_progress(
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> AcademyProgressOut:
    return await svc.get_progress(ctx)


@router.get("/lessons/{slug}", response_model=LessonDetailOut)
async def get_lesson(
    slug: str,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_READ)),
    svc: AcademyService = Depends(get_academy_service),
) -> LessonDetailOut:
    return await svc.get_lesson(slug)


@router.post("/lessons/{slug}/complete", response_model=AcademyProgressOut)
async def complete_lesson(
    slug: str,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> AcademyProgressOut:
    return await svc.complete_lesson(ctx, slug)


# --- Legacy Construire guidé ---


@router.post("/build/start", response_model=GuidedSessionOut)
async def start_guided(
    body: GuidedStartIn,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> GuidedSessionOut:
    return await svc.start_guided(ctx, body)


@router.post("/build/{session_id}/turn", response_model=GuidedSessionOut)
async def guided_turn(
    session_id: UUID,
    body: GuidedTurnIn,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> GuidedSessionOut:
    return await svc.guided_turn(ctx, session_id, body.message)


@router.patch("/build/{session_id}/draft", response_model=GuidedSessionOut)
async def save_draft(
    session_id: UUID,
    body: GuidedDraftIn,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> GuidedSessionOut:
    return await svc.save_draft(ctx, session_id, body.draft)


@router.get("/build/{session_id}", response_model=GuidedSessionOut)
async def get_guided(
    session_id: UUID,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_PROGRESS)),
    svc: AcademyService = Depends(get_academy_service),
) -> GuidedSessionOut:
    return await svc.get_guided(ctx, session_id)


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
