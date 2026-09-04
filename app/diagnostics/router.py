"""Routes diagnostics — les 2 flows. Réponse 202 (analyse asynchrone)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.ratelimit import rate_limit
from app.diagnostics.dependencies import (
    get_diagnostic_service,
    get_draft_service,
    get_extraction_service,
)
from app.diagnostics.draft_service import DiagnosticDraftService
from app.diagnostics.extraction import IdeaExtractionService, extract_text_from_file
from app.diagnostics.schemas import (
    DiagnosticCreatedOut,
    DiagnosticDraftIn,
    DiagnosticDraftOut,
    IdeaExtractIn,
    IdeaExtractOut,
    ManualDiagnosticIn,
    UploadDiagnosticIn,
)
from app.diagnostics.service import DiagnosticService
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

_MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 Mo
_CHUNK = 1024 * 1024  # 1 Mo


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    """Lit un UploadFile par chunks — refuse dès que la limite est dépassée (SEC-04).

    Sans ce guard, `await file.read()` charge tout en mémoire avant le contrôle de taille,
    ouvrant la porte à un DoS mémoire sur l'endpoint public.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail="Fichier trop grand (max 20 Mo).")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/extract",
    response_model=IdeaExtractOut,
    # PUBLIC : le porteur raconte AVANT de s'inscrire. Rate-limité par IP (1 appel LLM/visiteur).
    dependencies=[Depends(rate_limit("diagnostic_extract", limit=8, window_seconds=60))],
)
async def extract_idea(
    body: IdeaExtractIn,
    svc: IdeaExtractionService = Depends(get_extraction_service),
) -> IdeaExtractOut:
    # « Raconte, on structure » : récit libre → 12 dimensions captées / manquantes (synchrone).
    return await svc.extract(body.idea, body.project_name, lang=body.lang, currency=body.currency)


@router.post(
    "/extract-file",
    response_model=IdeaExtractOut,
    # PUBLIC + rate-limité : même logique que /extract mais pour les fichiers.
    dependencies=[Depends(rate_limit("diagnostic_extract_file", limit=5, window_seconds=60))],
)
async def extract_file_idea(
    file: UploadFile = File(...),
    project_name: str | None = Form(default=None),
    lang: str = Form(default="fr"),
    currency: str = Form(default="XOF"),
    svc: IdeaExtractionService = Depends(get_extraction_service),
) -> IdeaExtractOut:
    """Upload d'un PDF ou DOCX → extraction de texte → même pipeline 'Raconte' que /extract."""
    data = await _read_limited(file, _MAX_FILE_BYTES)

    text = extract_text_from_file(
        data,
        content_type=file.content_type or "",
        filename=file.filename or "",
    )
    if len(text.strip()) < 20:
        raise HTTPException(
            status_code=422,
            detail="Le document semble vide ou dans un format non lisible. Essaie le flow 'Raconte'.",
        )

    name = project_name or (file.filename or "").rsplit(".", 1)[0] or None
    return await svc.extract(text.strip()[:5000], name, lang=lang if lang in ("fr", "en") else "fr", currency=currency)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DiagnosticCreatedOut,
    # Scoring = 3 passes LLM : anti-abus coût (fail-closed si Redis down).
    dependencies=[Depends(rate_limit("diagnostic_run", limit=6, window_seconds=60))],
)
async def start_guided_diagnostic(
    body: ManualDiagnosticIn,
    ctx: AuthContext = Depends(require(Permission.DIAGNOSTIC_RUN)),
    svc: DiagnosticService = Depends(get_diagnostic_service),
) -> DiagnosticCreatedOut:
    # Flow A — idée guidée. Crée projet + diagnostic + bilan en attente, enqueue l'analyse.
    return await svc.start_guided(owner_id=ctx.user.id, data=body)


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DiagnosticCreatedOut,
    dependencies=[Depends(rate_limit("diagnostic_run", limit=6, window_seconds=60))],
)
async def start_upload_diagnostic(
    body: UploadDiagnosticIn,
    ctx: AuthContext = Depends(require(Permission.DIAGNOSTIC_RUN)),
    svc: DiagnosticService = Depends(get_diagnostic_service),
) -> DiagnosticCreatedOut:
    # Flow B — document déjà uploadé (app/documents). L'extraction se fait côté worker.
    return await svc.start_from_document(owner_id=ctx.user.id, data=body)


# --- Brouillon de saisie (diagnostic en cours) --------------------------------
#
# Déclarées AVANT aucune route paramétrée du même préfixe : `/draft` est un segment
# littéral, il ne doit jamais être capté comme un identifiant.
#
# `PUT` et non `POST` : l'appel est répété à chaque sauvegarde (une fois par dimension),
# il doit donc être idempotent, et le corps porte l'état complet plutôt qu'un delta.


@router.put("/draft", response_model=DiagnosticDraftOut)
async def save_diagnostic_draft(
    body: DiagnosticDraftIn,
    ctx: AuthContext = Depends(require(Permission.DIAGNOSTIC_RUN)),
    svc: DiagnosticDraftService = Depends(get_draft_service),
) -> DiagnosticDraftOut:
    return await svc.save(ctx, body)


@router.get("/draft", response_model=DiagnosticDraftOut)
async def get_diagnostic_draft(
    ctx: AuthContext = Depends(require(Permission.DIAGNOSTIC_RUN)),
    svc: DiagnosticDraftService = Depends(get_draft_service),
) -> DiagnosticDraftOut:
    # 404 si aucun brouillon vivant : c'est le signal « rien à reprendre » du front.
    return await svc.get(ctx)


@router.delete("/draft", status_code=status.HTTP_204_NO_CONTENT)
async def discard_diagnostic_draft(
    ctx: AuthContext = Depends(require(Permission.DIAGNOSTIC_RUN)),
    svc: DiagnosticDraftService = Depends(get_draft_service),
) -> None:
    # « Recommencer » — abandon explicite. 204 même si aucun brouillon : l'appel est
    # idempotent, et le front n'a pas à distinguer les deux cas.
    await svc.discard(ctx)
