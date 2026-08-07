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
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.core.storage import get_storage
from app.diagnostics.repository import DiagnosticRepository
from app.iam.repository import UserRepository
from app.inconsistencies.dedup import Finding
from app.inconsistencies.service import Dossier, InconsistencyService
from app.llm.factory import get_llm
from app.llm.prompt import PROMPT_VERSION, build_report_prompt, build_scoring_prompt
from app.notifications.repository import NotificationRepository
from app.project_memory.contradictions import persist_findings
from app.project_memory.evaluation import ProjectEvaluationProjector
from app.project_memory.repository import ProjectMemoryRepository
from app.projects.models import DiagnosticStatus, ReviewStatus
from app.projects.repository import ProjectRepository
from app.projects.state_service import ProjectStateService
from app.reports.models import ReportStatus
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
        runs = ScoreRunRepository(session)
        scoring = ScoringService(ScoringRepository(session), runs)
        auditor = AuditService(session)
        states = ProjectStateService(projects, auditor)

        diagnostic = await diagnostics.get_by_id(diagnostic_id)
        project = await projects.get_by_id(project_id)
        report = await reports.get_by_id(report_id)
        if diagnostic is None or project is None or report is None:
            raise RuntimeError("run_diagnostic : entités introuvables (déjà supprimées ?).")
        if report.status is ReportStatus.READY and project.diagnostic_status is DiagnosticStatus.BILAN_READY:
            logger.info("diagnostic_job_already_completed", report_id=str(report.id))
            return

        grid = await scoring.repo.get_active()
        if grid is None:
            raise RuntimeError("Aucune grille Radar active (seed manquant).")

        # Bilingue : le bilan (justifications + rapport) suit la langue du porteur.
        owner = await UserRepository(session).get_by_id(project.owner_id)
        lang = owner.language if owner is not None else "fr"

        # N passes : même rubrique, angle d'analyse variable → dispersion mesurable.
        # Indépendantes entre elles → lancées EN PARALLÈLE (latence ≈ 1 appel, pas N).
        async def _score_pass(perspective: int) -> dict:
            prompt = build_scoring_prompt(
                grid.axes,
                category=project.sector,
                archetype=project.archetype.value,
                description=diagnostic.description,
                answers=diagnostic.answers,
                perspective=perspective,
                lang=lang,
            )
            return await provider.analyze_json(prompt)

        # Détection des contradictions internes du récit. Elle tourne EN PARALLÈLE du scoring :
        # elle n'en dépend pas et ne doit pas retarder le Radar. Son produit alimente la chaîne
        # `contradiction_gap` déjà en place — c'est le seul signal du parcours qui soit vrai
        # indépendamment de la calibration du score.
        async def _detect_inconsistencies() -> list[Finding]:
            if not diagnostic.description:
                return []  # dossier issu d'un document : pas de récit à confronter
            try:
                detector = InconsistencyService(provider, concurrency=1)
                analysis = await detector.analyze(
                    Dossier(
                        reference=str(project.id),
                        narrative=diagnostic.description,
                        category=project.sector,
                        archetype=project.archetype.value,
                    )
                )
                return analysis.findings
            except Exception as exc:
                # IDX-MEM-04 : un diagnostic doit aboutir même sans détection. Le porteur
                # préfère un Radar sans contradictions à pas de Radar du tout.
                logger.warning("inconsistency_detection_failed", report_id=str(report.id), error=str(exc))
                return []

        # TOLÉRANT : une passe qui échoue (rate-limit, transitoire, JSON invalide) ne doit pas
        # faire tomber tout le scoring — l'ensemble sait produire un consensus avec moins de
        # 3 passes (confiance moindre, signalée). On ne lève QUE si TOUTES échouent.
        results, findings = await asyncio.gather(
            asyncio.gather(*(_score_pass(k) for k in range(N_PASSES)), return_exceptions=True),
            _detect_inconsistencies(),
        )
        raw_outputs: list[dict] = [r for r in results if isinstance(r, dict) and isinstance(r.get("axes"), dict)]
        if not raw_outputs:
            first_exc = next((r for r in results if isinstance(r, Exception)), None)
            raise first_exc or RuntimeError("scoring : toutes les passes LLM ont échoué")
        if len(raw_outputs) < N_PASSES:
            logger.warning(
                "scoring_partial_passes",
                report_id=str(report.id),
                kept=len(raw_outputs),
                total=N_PASSES,
            )
        passes: list[dict[str, int]] = [{key: int(v) for key, v in out["axes"].items()} for out in raw_outputs]
        justifications: dict[str, str] | None = next(
            (out.get("justifications") for out in raw_outputs if out.get("justifications")), None
        )

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

        # Routage déterministe : des axes faibles → prochaines actions (leviers typés).
        # Dépend du SCORE seul (pas du rapport) → appartient à la Phase 1 (Radar).
        next_actions = derive_next_actions(
            grid.axes,
            result.axes,
            grid.category_weights,
            project.sector,
            scale_max=grid.scale_max,
        )

        radar_score = {"gridVersion": result.grid_version, "axes": result.axes}
        comprehension = {"pillars": result.pillars, "overall": result.overall}
        score_run = await runs.get_by_id(result.run_id)
        if score_run is not None:
            memory = ProjectMemoryRepository(session)
            # AVANT la projection : le projecteur relit la mémoire pour bâtir l'état des
            # dimensions. Une contradiction écrite après lui resterait invisible jusqu'au run suivant.
            await persist_findings(memory, project_id=project.id, findings=findings)
            await ProjectEvaluationProjector(memory).persist_from_score_run(
                project_id=project.id,
                axes=grid.axes,
                score_run=score_run,
                next_actions=next_actions,
                scale_max=grid.scale_max,
            )

        # ── PHASE 1 : le Radar est prêt → on l'EXPOSE TOUT DE SUITE ────────────────────
        # score + compréhension + prochaines actions. Le porteur voit son score sans
        # attendre le rapport LLM ni le PDF (Phase 2). Statut : reste PENDING ; le front
        # affiche le Radar dès que `radar_score` est présent.
        await reports.mark_scored(
            report,
            grid_version=result.grid_version,
            radar_score=radar_score,
            comprehension=comprehension,
            next_actions=next_actions,
        )
        await states.transition_diagnostic(project, DiagnosticStatus.DIAGNOSTIC_COMPLETED, actor_id=None)
        # Routage AUTO vers la revue humaine si le score est incertain (dépend du score).
        if result.needs_review and project.review_status is ReviewStatus.NEW_DIAGNOSTIC:
            await states.transition_review(project, ReviewStatus.IN_REVIEW, actor_id=None)
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
        await session.commit()  # ← Radar disponible côté front (report PENDING + radar_score)

        # ── PHASE 2 : rapport (LLM) + PDF, en arrière-plan du point de vue porteur ─────
        # Best-effort : un échec n'empêche pas le bilan (le Radar scoré reste la colonne
        # vertébrale). L'analyste affine ensuite ce rapport.
        report_data: dict | None = None
        try:
            report_prompt = build_report_prompt(
                category=project.sector,
                archetype=project.archetype.value,
                description=diagnostic.description,
                answers=diagnostic.answers,
                scores=result.axes,
                lang=lang,
            )
            report_raw = await provider.analyze_json(report_prompt)
            report_data = DiagnosticReport.model_validate(report_raw).model_dump()
        except Exception as exc:  # noqa: BLE001 — dégradation gracieuse du rapport
            logger.warning("diagnostic_report_skipped", report_id=str(report.id), error=str(exc))

        # PDF du bilan — best-effort : toute défaillance (WeasyPrint/MinIO/réseau) est
        # loggée et n'empêche jamais le bilan d'être `ready`. Pas de panne dure.
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
                await storage.aput_bytes(key=key, data=pdf_bytes, content_type="application/pdf")
                # Le report.id sert de référence d'objet (clé = bilans/<id>.pdf) tant que
                # le module documents ne formalise pas une table dédiée.
                pdf_document_id = report.id
        except Exception as exc:  # noqa: BLE001 — dégradation gracieuse du PDF
            logger.warning("bilan_pdf_skipped", report_id=str(report.id), error=str(exc))

        # Bilan COMPLET : insights + PDF ajoutés, statut READY.
        await reports.mark_ready(
            report,
            grid_version=result.grid_version,
            radar_score=radar_score,
            comprehension=comprehension,
            insights=report_data,
            next_actions=next_actions,
            pdf_document_id=pdf_document_id,
        )
        await states.transition_diagnostic(project, DiagnosticStatus.BILAN_READY, actor_id=None)

        # Notifie le porteur : son bilan complet est prêt.
        try:
            notif_repo = NotificationRepository(session)
            await notif_repo.create(
                user_id=project.owner_id,
                type="report_ready",
                payload={"report_id": str(report.id), "title": "Ton bilan de compréhension est prêt."},
            )
        except Exception as exc:  # noqa: BLE001 — dégradation gracieuse
            logger.warning("notification_skipped", report_id=str(report.id), error=str(exc))

        await session.commit()  # ← bilan complet (rapport + PDF)

    logger.info(
        "diagnostic_scored",
        report_id=str(report_id),
        overall=result.overall,
        confidence=result.confidence,
        needs_review=result.needs_review,
    )


async def handle_run_diagnostic_failed(payload: dict[str, Any]) -> None:
    """Nettoyage sur échec DÉFINITIF du scoring (retries épuisés).

    Sans ça, le bilan resterait `pending` pour toujours et le porteur verrait un
    spinner infini. On le fait basculer en `failed` (état terminal côté front) et on
    prévient le porteur. Best-effort : ne doit jamais lever (sinon on masque l'échec).
    """
    report_id = UUID(payload["report_id"])
    factory = get_session_factory()

    # 1) Bascule du statut, commit ISOLÉ : c'est le correctif essentiel (sortir de l'attente).
    #    Rien ne doit l'empêcher de persister — surtout pas une notif défaillante.
    owner_id = None
    notif_type = "report_failed"
    notif_title = "On n'a pas pu terminer ton analyse. Notre équipe est prévenue."
    async with factory() as session:
        reports = ReportRepository(session)
        report = await reports.get_by_id(report_id)
        if report is None or report.status is not ReportStatus.PENDING:
            # Déjà prêt (course avec un retry qui a réussi) ou supprimé : rien à faire.
            return
        projects = ProjectRepository(session)
        states = ProjectStateService(projects, AuditService(session))
        project = await projects.get_by_id(report.project_id)
        owner_id = project.owner_id if project is not None else None

        if report.radar_score is not None:
            # Phase 1 a réussi (le Radar existe) mais la Phase 2 (rapport/PDF) a échoué
            # définitivement → bilan Radar-only VALIDE plutôt qu'un échec dur qui masquerait
            # le score déjà calculé. Le porteur voit son Radar ; l'analyste complètera.
            report.status = ReportStatus.READY
            if project is not None:
                await states.transition_diagnostic(project, DiagnosticStatus.BILAN_READY, actor_id=None)
            await session.commit()
            logger.warning("diagnostic_radar_only_ready", report_id=str(report_id))
            notif_type = "report_ready"
            notif_title = "Ton bilan de compréhension est prêt."
        else:
            await reports.mark_failed(report)
            await session.commit()
            logger.error("diagnostic_failed_terminal", report_id=str(report_id))

    # 2) Notification du porteur, best-effort dans une transaction séparée.
    if owner_id is None:
        return
    try:
        async with factory() as session:
            await NotificationRepository(session).create(
                user_id=owner_id,
                type=notif_type,
                payload={"report_id": str(report_id), "title": notif_title},
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001 — dégradation gracieuse de la notif
        logger.warning("report_terminal_notification_skipped", report_id=str(report_id), error=str(exc))
