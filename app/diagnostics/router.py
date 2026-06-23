"""Routes diagnostics — les 2 flows. Réponse 202 (analyse asynchrone)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.diagnostics.dependencies import get_diagnostic_service
from app.diagnostics.schemas import (
    DiagnosticCreatedOut,
    ManualDiagnosticIn,
    UploadDiagnosticIn,
)
from app.diagnostics.service import DiagnosticService
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DiagnosticCreatedOut)
async def start_guided_diagnostic(
    body: ManualDiagnosticIn,
    ctx: AuthContext = Depends(require(Permission.DIAGNOSTIC_RUN)),
    svc: DiagnosticService = Depends(get_diagnostic_service),
) -> DiagnosticCreatedOut:
    # Flow A — idée guidée. Crée projet + diagnostic + bilan en attente, enqueue l'analyse.
    return await svc.start_guided(owner_id=ctx.user.id, data=body)


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, response_model=DiagnosticCreatedOut)
async def start_upload_diagnostic(
    body: UploadDiagnosticIn,
    ctx: AuthContext = Depends(require(Permission.DIAGNOSTIC_RUN)),
    svc: DiagnosticService = Depends(get_diagnostic_service),
) -> DiagnosticCreatedOut:
    # Flow B — document déjà uploadé (app/documents). L'extraction se fait côté worker.
    return await svc.start_from_document(owner_id=ctx.user.id, data=body)
