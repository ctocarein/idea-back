"""Routes Academy — leçons, progression, construire guidé."""

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
)
from app.academy.service import AcademyService
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission

router = APIRouter(prefix="/academy", tags=["academy"])


@router.get("/lessons", response_model=list[LessonOut])
async def list_lessons(
    topic: str | None = None,
    ctx: AuthContext = Depends(require(Permission.ACADEMY_READ)),
    svc: AcademyService = Depends(get_academy_service),
) -> list[LessonOut]:
    # `?topic=modele_economique` : sert les leçons d'un levier (résolution des next_actions).
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


# --- Construire guidé ---


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
