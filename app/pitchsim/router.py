"""Routes pitchsim — comités (lecture) + decks (upload/parsing)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.pitchsim.constants import COMMITTEES
from app.pitchsim.dependencies import get_deck_service, get_session_service
from app.pitchsim.models import SlideKind
from app.pitchsim.schemas import (
    AnswerIn,
    CommitteeOut,
    DeckOut,
    PitchRunOut,
    SessionOut,
    SessionStartIn,
    SlideSubmitIn,
)
from app.pitchsim.service import PitchDeckService, PitchSessionService

router = APIRouter(prefix="/pitchsim", tags=["pitchsim"])


@router.get("/committees", response_model=list[CommitteeOut])
async def list_committees(
    ctx: AuthContext = Depends(require(Permission.PITCHSIM_RUN)),
) -> list[dict]:
    # Comités + personas (Écran 1). Constantes versionnées avec la rubrique.
    return COMMITTEES


@router.post("/decks", response_model=DeckOut)
async def create_deck(
    file: UploadFile = File(...),
    title: str = Form("Pitch deck"),
    project_id: UUID | None = Form(None),
    ctx: AuthContext = Depends(require(Permission.PITCHSIM_RUN)),
    svc: PitchDeckService = Depends(get_deck_service),
) -> DeckOut:
    # Upload direct du deck principal → parsing PDF/PPTX → slides MAIN.
    data = await file.read()
    return await svc.create_deck(
        ctx,
        title=title,
        project_id=project_id,
        content_type=file.content_type or "",
        data=data,
    )


@router.post("/decks/{deck_id}/slides", response_model=DeckOut)
async def add_slides(
    deck_id: UUID,
    file: UploadFile = File(...),
    kind: SlideKind = Form(SlideKind.BACKUP),
    ctx: AuthContext = Depends(require(Permission.PITCHSIM_RUN)),
    svc: PitchDeckService = Depends(get_deck_service),
) -> DeckOut:
    # Slides de backup / synthèse (réponses aux questions du comité).
    data = await file.read()
    return await svc.add_slides(ctx, deck_id, kind=kind, content_type=file.content_type or "", data=data)


@router.get("/decks/{deck_id}", response_model=DeckOut)
async def get_deck(
    deck_id: UUID,
    ctx: AuthContext = Depends(require(Permission.PITCHSIM_RUN)),
    svc: PitchDeckService = Depends(get_deck_service),
) -> DeckOut:
    return await svc.get_deck(ctx, deck_id)


# --- Session de pitch (le comité) ---


@router.post("/sessions", response_model=SessionOut)
async def start_session(
    body: SessionStartIn,
    ctx: AuthContext = Depends(require(Permission.PITCHSIM_RUN)),
    svc: PitchSessionService = Depends(get_session_service),
) -> SessionOut:
    return await svc.start_session(ctx, body)


@router.post("/sessions/{session_id}/slide", response_model=SessionOut)
async def submit_slide(
    session_id: UUID,
    body: SlideSubmitIn,
    ctx: AuthContext = Depends(require(Permission.PITCHSIM_RUN)),
    svc: PitchSessionService = Depends(get_session_service),
) -> SessionOut:
    # Narration d'une slide → réactions du comité (interruption si faiblesse détectée).
    return await svc.submit_slide(ctx, session_id, body.narration, body.slide_id)


@router.post("/sessions/{session_id}/answer", response_model=SessionOut)
async def answer(
    session_id: UUID,
    body: AnswerIn,
    ctx: AuthContext = Depends(require(Permission.PITCHSIM_RUN)),
    svc: PitchSessionService = Depends(get_session_service),
) -> SessionOut:
    return await svc.answer(ctx, session_id, body.answer, body.shown_slide_id)


@router.post("/sessions/{session_id}/imprevu", response_model=SessionOut)
async def force_imprevu(
    session_id: UUID,
    ctx: AuthContext = Depends(require(Permission.PITCHSIM_RUN)),
    svc: PitchSessionService = Depends(get_session_service),
) -> SessionOut:
    # « Imprévu forcé » (entraînement) — l'investisseur surprise.
    return await svc.force_imprevu(ctx, session_id)


@router.post("/sessions/{session_id}/finish", response_model=SessionOut)
async def finish_session(
    session_id: UUID,
    ctx: AuthContext = Depends(require(Permission.PITCHSIM_RUN)),
    svc: PitchSessionService = Depends(get_session_service),
) -> SessionOut:
    # Délibération du comité (le scoring Fond/Forme arrive en PITCH-04).
    return await svc.finish(ctx, session_id)


@router.post("/sessions/{session_id}/abandon", status_code=204)
async def abandon_session(
    session_id: UUID,
    ctx: AuthContext = Depends(require(Permission.PITCHSIM_RUN)),
    svc: PitchSessionService = Depends(get_session_service),
) -> None:
    await svc.abandon(ctx, session_id)


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: UUID,
    ctx: AuthContext = Depends(require(Permission.PITCHSIM_RUN)),
    svc: PitchSessionService = Depends(get_session_service),
) -> SessionOut:
    return await svc.get_session(ctx, session_id)


@router.get("/sessions/{session_id}/run", response_model=PitchRunOut)
async def get_run(
    session_id: UUID,
    ctx: AuthContext = Depends(require(Permission.PITCHSIM_RUN)),
    svc: PitchSessionService = Depends(get_session_service),
) -> PitchRunOut:
    # Score Fond (credential) + Forme (coaching) calculé à finish.
    return await svc.get_run(ctx, session_id)
