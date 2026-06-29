"""Handler worker `run_diagnostic` — ferme la boucle diagnostic → bilan.

Enchaîne (en une transaction) : grille ancrée → N passes LLM → consensus + confiance →
validation + agrégation déterministe → bilan `ready` → transitions de statut → routage
auto vers la revue analyste si le score s'auto-déclare incertain.

Reproductibilité : chaque passe est stockée (raw_output du ScoreRun), `prompt_version` et
`model` figés. La dispersion entre passes vient de l'angle d'analyse (perspective), pas du
hasard — l'agrégation reste rejouable.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.audit.service import AuditService
from app.notifications.repository import NotificationRepository
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.core.storage import get_storage
from app.diagnostics.repository import DiagnosticRepository
from app.llm.factory import get_llm
from app.llm.prompt import PROMPT_VERSION, build_report_prompt, build_scoring_prompt
from app.projects.models import DiagnosticStatus, ReviewStatus
from app.projects.repository import ProjectRepository
from app.reports.pdf import render_bilan_html, render_bilan_pdf
from app.reports.repository import ReportRepository
from app.reports.schemas import DiagnosticReport
from app.scoring.actions import derive_next_actions
from app.scoring.repository import ScoreRunRepository, ScoringRepository
from app.scoring.service import ScoringService

logger = get_logger("run_diagnostic")

N_PASSES = 3  # nombre de passes d'ensemble (N≥3 pour un signal d'incertitude fiable)


async def handle_run_diagnostic(payload: dict[str, Any]) -> None:
    diagnostic_id = UUID(payload["diagnostic_id"])
    project_id = UUID(payload["project_id"])
    report_id = UUID(payload["report_id"])

    settings = get_settings()
    provider = get_llm(settings)  # lève si provider non configuré → job rejoué
    model = getattr(provider, "model", settings.llm_provider)

    factory = get_session_factory()
    async with factory() as session:
        diagnostics = DiagnosticRepository(session)
        projects = ProjectRepository(session)
        reports = ReportRepository(session)
        scoring = ScoringService(ScoringRepository(session), ScoreRunRepository(session))
        auditor = AuditService(session)

        diagnostic = await diagnostics.get_by_id(diagnostic_id)
        project = await projects.get_by_id(project_id)
        report = await reports.get_by_id(report_id)
        if diagnostic is None or project is None or report is None:
            raise RuntimeError("run_diagnostic : entités introuvables (déjà supprimées ?).")

        grid = await scoring.repo.get_active()
        if grid is None:
            raise RuntimeError("Aucune grille Radar active (seed manquant).")

        # N passes : même rubrique, angle d'analyse variable → dispersion mesurable.
        passes: list[dict[str, int]] = []
        justifications: dict[str, str] | None = None
        raw_outputs: list[dict] = []
        for k in range(N_PASSES):
            prompt = build_scoring_prompt(
                grid.axes,
                category=project.sector,
                archetype=project.archetype.value,
                description=diagnostic.description,
                answers=diagnostic.answers,
                perspective=k,
            )
            out = await provider.analyze_json(prompt)
            raw_outputs.append(out)
            passes.append({key: int(v) for key, v in out["axes"].items()})
            if justifications is None:
                justifications = out.get("justifications")

        # Consensus + confiance + enregistrement du ScoreRun (rejouable/auditable).
        result = await scoring.build_consensus_score(
            project_id=project.id,
            diagnostic_id=diagnostic.id,
            report_id=report.id,
            category=project.sector,
            passes=passes,
            justifications=justifications,
            prompt_version=PROMPT_VERSION,
            model=model,
            raw_outputs=raw_outputs,
        )

        # Rapport structuré (résumé, description, verdict, risques, concurrence, avancement,
        # recos, next steps) — GARDÉ : best-effort, un échec n'empêche pas le bilan (le Radar
        # scoré reste la colonne vertébrale). L'analyste affine ensuite ce rapport.
        report_data: dict | None = None
        try:
            report_prompt = build_report_prompt(
                category=project.sector,
                archetype=project.archetype.value,
                description=diagnostic.description,
                answers=diagnostic.answers,
                scores=result.axes,
            )
            report_raw = await provider.analyze_json(report_prompt)
            report_data = DiagnosticReport.model_validate(report_raw).model_dump()
        except Exception as exc:  # noqa: BLE001 — dégradation gracieuse du rapport
            logger.warning("diagnostic_report_skipped", report_id=str(report.id), error=str(exc))

        # Routage déterministe : des axes faibles → prochaines actions (leviers typés).
        next_actions = derive_next_actions(
            grid.axes,
            result.axes,
            grid.category_weights,
            project.sector,
            scale_max=grid.scale_max,
        )

        # Génération du PDF du bilan — GARDÉE : toute défaillance (WeasyPrint/MinIO absents,
        # réseau) est loggée et n'empêche jamais le bilan d'être `ready`. Pas de panne dure.
        pdf_document_id = None
        try:
            storage = get_storage()
            if storage is not None:
                html = render_bilan_html(
                    project_title=project.title,
                    category=project.sector,
                    grid_pillars=grid.pillars,
                    grid_axes=grid.axes,
                    scores=result.axes,
                    pillar_scores=result.pillars,
                    overall=result.overall,
                    scale_max=grid.scale_max,
                    grid_version=result.grid_version,
                    generated_at=datetime.now(UTC).strftime("%d/%m/%Y"),
                    n_passes=N_PASSES,
                    confidence=result.confidence,
                    report=report_data,
                    next_actions=next_actions,
                )
                pdf_bytes = await asyncio.to_thread(render_bilan_pdf, html)
                key = f"bilans/{report.id}.pdf"
                await asyncio.to_thread(storage.put_bytes, key=key, data=pdf_bytes, content_type="application/pdf")
                # Le report.id sert de référence d'objet (clé = bilans/<id>.pdf) tant que
                # le module documents ne formalise pas une table dédiée.
                pdf_document_id = report.id
        except Exception as exc:  # noqa: BLE001 — dégradation gracieuse du PDF
            logger.warning("bilan_pdf_skipped", report_id=str(report.id), error=str(exc))

        # Bilan prêt (tableau de compréhension + score ; PDF si disponible).
        await reports.mark_ready(
            report,
            grid_version=result.grid_version,
            radar_score={"gridVersion": result.grid_version, "axes": result.axes},
            comprehension={"pillars": result.pillars, "overall": result.overall},
            insights=report_data,
            next_actions=next_actions,
            pdf_document_id=pdf_document_id,
        )

        # Notifie le porteur : son bilan est prêt.
        try:
            notif_repo = NotificationRepository(session)
            await notif_repo.create(
                user_id=project.owner_id,
                type="report_ready",
                payload={"report_id": str(report.id), "title": "Ton bilan de compréhension est prêt."},
            )
        except Exception as exc:  # noqa: BLE001 — dégradation gracieuse
            logger.warning("notification_skipped", report_id=str(report.id), error=str(exc))

        # Avance le pipeline diagnostic.
        await projects.set_diagnostic_status(project, DiagnosticStatus.DIAGNOSTIC_COMPLETED)
        await projects.set_diagnostic_status(project, DiagnosticStatus.BILAN_READY)

        # Routage AUTO vers la revue humaine si le score est incertain.
        if result.needs_review and project.review_status is ReviewStatus.NEW_DIAGNOSTIC:
            await projects.set_review_status(project, ReviewStatus.IN_REVIEW)

        await auditor.record(
            actor_id=project.owner_id,
            action="diagnostic.scored",
            entity="report",
            entity_id=report.id,
            new_value={
                "overall": result.overall,
                "confidence": result.confidence,
                "needs_review": result.needs_review,
            },
        )
        await session.commit()

    logger.info(
        "diagnostic_scored",
        report_id=str(report_id),
        overall=result.overall,
        confidence=result.confidence,
        needs_review=result.needs_review,
    )
