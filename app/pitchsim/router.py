"""Routes pitchsim — comités (lecture) + decks (upload/parsing)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.pitchsim.constants import COMMITTEES
from app.pitchsim.dependencies import get_deck_service
from app.pitchsim.models import SlideKind
from app.pitchsim.schemas import CommitteeOut, DeckOut
from app.pitchsim.service import PitchDeckService

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
