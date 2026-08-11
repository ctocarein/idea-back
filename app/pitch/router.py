"""Routes de l'éditeur de pitch (V1.2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from app.core.ratelimit import rate_limit
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.pitch.dependencies import get_pitch_service
from app.pitch.schemas import (
    DeckGenerateIn,
    PitchOut,
    SectionGenerateOut,
    SectionUpdateIn,
    SlidesReorderIn,
    SlideUpdateIn,
    TemplateIn,
)
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


@router.post(
    "/{pitch_id}/sections/{key}/generate",
    response_model=SectionGenerateOut,
    dependencies=[Depends(rate_limit("pitch_generate", limit=15, window_seconds=60))],
)
async def generate_section(
    pitch_id: UUID,
    key: str,
    ctx: AuthContext = Depends(require(Permission.PITCH_EDIT)),
    svc: PitchService = Depends(get_pitch_service),
) -> SectionGenerateOut:
    return await svc.generate_section(ctx, pitch_id, key)


@router.post(
    "/{pitch_id}/deck/generate",
    response_model=PitchOut,
    # Génération du deck = appel LLM : anti-abus coût (fail-closed si Redis down).
    dependencies=[Depends(rate_limit("deck_generate", limit=10, window_seconds=60))],
)
async def generate_deck(
    pitch_id: UUID,
    body: DeckGenerateIn,
    ctx: AuthContext = Depends(require(Permission.PITCH_EDIT)),
    svc: PitchService = Depends(get_pitch_service),
) -> PitchOut:
    return await svc.generate_deck(ctx, pitch_id, body.source)


@router.post("/{pitch_id}/deck/import", response_model=PitchOut)
async def import_deck(
    pitch_id: UUID,
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(require(Permission.PITCH_EDIT)),
    svc: PitchService = Depends(get_pitch_service),
) -> PitchOut:
    from app.pitch.import_extract import extract_text

    data = await file.read()
    try:
        text = extract_text(file.filename or "", data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return await svc.generate_deck(ctx, pitch_id, text)


@router.patch("/{pitch_id}/template", response_model=PitchOut)
async def set_template(
    pitch_id: UUID,
    body: TemplateIn,
    ctx: AuthContext = Depends(require(Permission.PITCH_EDIT)),
    svc: PitchService = Depends(get_pitch_service),
) -> PitchOut:
    return await svc.set_template(ctx, pitch_id, body.template_id)


@router.patch("/{pitch_id}/slides/{index}", response_model=PitchOut)
async def update_slide(
    pitch_id: UUID,
    index: int,
    body: SlideUpdateIn,
    ctx: AuthContext = Depends(require(Permission.PITCH_EDIT)),
    svc: PitchService = Depends(get_pitch_service),
) -> PitchOut:
    return await svc.update_slide(ctx, pitch_id, index, body.model_dump(exclude_none=True))


@router.delete("/{pitch_id}/slides/{index}", response_model=PitchOut)
async def delete_slide(
    pitch_id: UUID,
    index: int,
    ctx: AuthContext = Depends(require(Permission.PITCH_EDIT)),
    svc: PitchService = Depends(get_pitch_service),
) -> PitchOut:
    return await svc.delete_slide(ctx, pitch_id, index)


@router.post("/{pitch_id}/slides/reorder", response_model=PitchOut)
async def reorder_slides(
    pitch_id: UUID,
    body: SlidesReorderIn,
    ctx: AuthContext = Depends(require(Permission.PITCH_EDIT)),
    svc: PitchService = Depends(get_pitch_service),
) -> PitchOut:
    return await svc.reorder_slides(ctx, pitch_id, body.order)


@router.get("/{pitch_id}/deck/html")
async def deck_html(
    pitch_id: UUID,
    ctx: AuthContext = Depends(require(Permission.PITCH_EDIT)),
    svc: PitchService = Depends(get_pitch_service),
) -> Response:
    html = await svc.render_deck(ctx, pitch_id, standalone=True)
    return Response(content=html, media_type="text/html; charset=utf-8")


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
