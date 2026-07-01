"""Routes de l'éditeur de pitch (V1.2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.pitch.dependencies import get_pitch_service
from app.pitch.schemas import PitchOut, SectionGenerateOut, SectionUpdateIn
from app.pitch.service import PitchService

router = APIRouter(prefix="/pitch", tags=["pitch"])


@router.get("", response_model=PitchOut)
async def get_pitch(
    ctx: AuthContext = Depends(require(Permission.PITCH_EDIT)),
    svc: PitchService = Depends(get_pitch_service),
) -> PitchOut:
    return await svc.get_or_create(ctx)


@router.patch("/{pitch_id}/sections/{key}", response_model=PitchOut)
async def update_section(
    pitch_id: UUID,
    key: str,
    body: SectionUpdateIn,
    ctx: AuthContext = Depends(require(Permission.PITCH_EDIT)),
    svc: PitchService = Depends(get_pitch_service),
) -> PitchOut:
    return await svc.update_section(ctx, pitch_id, key, body.content)


@router.post("/{pitch_id}/sections/{key}/generate", response_model=SectionGenerateOut)
async def generate_section(
    pitch_id: UUID,
    key: str,
    ctx: AuthContext = Depends(require(Permission.PITCH_EDIT)),
    svc: PitchService = Depends(get_pitch_service),
) -> SectionGenerateOut:
    return await svc.generate_section(ctx, pitch_id, key)
