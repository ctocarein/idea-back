"""Routes reports — le bilan in-app (porteur). Le PDF (download presigned) suivra."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.iam.dependencies import AuthContext, get_current_user, require
from app.iam.permissions import Permission
from app.reports.dependencies import get_report_edit_service, get_report_service
from app.reports.edit_service import ReportEditService
from app.reports.schemas import (
    DiagnosticReport,
    PdfLink,
    ReportDetailOut,
    ReportOut,
    ScoreAdjustIn,
)
from app.reports.service import ReportService
from app.scoring.schemas import ScoreResult

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportOut])
async def list_my_reports(
    ctx: AuthContext = Depends(require(Permission.REPORT_READ_OWN)),
    svc: ReportService = Depends(get_report_service),
) -> list[ReportOut]:
    return await svc.list_mine(ctx)


@router.get("/{report_id}", response_model=ReportDetailOut)
async def get_report(
    report_id: UUID,
    ctx: AuthContext = Depends(get_current_user),
    svc: ReportService = Depends(get_report_service),
) -> ReportDetailOut:
    # Détail = tableau de compréhension + score Radar. Garde de propriété dans le service.
    return await svc.get_detail(report_id, ctx)


@router.post("/{report_id}/actions/{action_key}/start", status_code=204)
async def start_next_action(
    report_id: UUID,
    action_key: str,
    ctx: AuthContext = Depends(require(Permission.REPORT_READ_OWN)),
    svc: ReportService = Depends(get_report_service),
) -> None:
    # Le porteur démarre une prochaine action → event `action_started` (sortie du funnel).
    await svc.start_action(report_id, ctx, action_key)


@router.get("/{report_id}/html", response_class=HTMLResponse)
async def download_report_html(
    report_id: UUID,
    ctx: AuthContext = Depends(get_current_user),
    svc: ReportService = Depends(get_report_service),
) -> HTMLResponse:
    html = await svc.get_html(report_id, ctx)
    short = str(report_id)[:8]
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'attachment; filename="bilan-{short}.html"'},
    )


@router.get("/{report_id}/pdf", response_model=PdfLink)
async def get_report_pdf(
    report_id: UUID,
    ctx: AuthContext = Depends(get_current_user),
    svc: ReportService = Depends(get_report_service),
) -> PdfLink:
    # Renvoie une URL presigned MinIO (409 si le PDF est encore en préparation).
    return PdfLink(url=await svc.get_pdf_url(report_id, ctx))


# --- Affinage analyste/mentor (« l'humain dispose ») ---
# Permission + assignation vérifiées dans le service (guard_assigned_or_admin) : admin
# partout, mentor/analyste sur projet assigné, porteur exclu.


@router.patch("/{report_id}/scores", response_model=ScoreResult)
async def adjust_report_scores(
    report_id: UUID,
    body: ScoreAdjustIn,
    ctx: AuthContext = Depends(get_current_user),
    svc: ReportEditService = Depends(get_report_edit_service),
) -> ScoreResult:
    # Ajuste les 12 dimensions → ScoreRun source=human → met à jour le bilan.
    return await svc.adjust_scores(report_id, ctx, body)


@router.patch("/{report_id}/report", response_model=ReportDetailOut)
async def edit_report_content(
    report_id: UUID,
    body: DiagnosticReport,
    ctx: AuthContext = Depends(get_current_user),
    svc: ReportEditService = Depends(get_report_edit_service),
) -> ReportDetailOut:
    # Édition partielle de la couche structurée (verdict, risques, concurrence, recos…).
    return await svc.edit_report(report_id, ctx, body)
