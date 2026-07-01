"""Routes de l'éditeur de pitch (V1.2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

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


@router.get("/{pitch_id}/export")
async def export_pitch(
    pitch_id: UUID,
    format: str = Query("pdf", pattern="^(pdf|pptx)$"),
    ctx: AuthContext = Depends(require(Permission.PITCH_EDIT)),
    svc: PitchService = Depends(get_pitch_service),
) -> Response:
    try:
        data, media_type, filename = await svc.export_pitch(ctx, pitch_id, format)
    except ImportError as exc:  # WeasyPrint / python-pptx absent → dégradation propre.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Génération {format.upper()} indisponible (dépendance non installée).",
        ) from exc
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
