"""Service diagnostics — orchestre la création du projet + diagnostic + bilan en attente.

Flux (GUIDE DIAG-01/02) : `POST /diagnostics` crée le projet (`new_diagnostic` /
`diagnostic_in_progress`) + le diagnostic + un bilan `pending`, puis enqueue le job
`run_diagnostic` et répond 202. L'analyse LLM + le scoring sont faits en asynchrone par
le worker (épic LLM/DIAG-03). Tout est commité atomiquement (un seul commit).
"""

from __future__ import annotations

from uuid import UUID

from app.audit.service import AuditService
from app.diagnostics.models import EntryMode
from app.diagnostics.repository import DiagnosticRepository
from app.diagnostics.schemas import (
    DiagnosticCreatedOut,
    ManualDiagnosticIn,
    UploadDiagnosticIn,
)
from app.documents.repository import DocumentRepository
from app.jobs.service import JobService
from app.projects.models import (
    Archetype,
    DiagnosticStatus,
    ProjectStage,
    ReviewStatus,
)
from app.projects.repository import ProjectRepository
from app.projects.state_service import ProjectStateService
from app.reports.repository import ReportRepository

# Type de job consommé par le worker (épic LLM/DIAG-03).
RUN_DIAGNOSTIC_JOB = "run_diagnostic"


class DiagnosticService:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        diagnostics: DiagnosticRepository,
        reports: ReportRepository,
        jobs: JobService,
        auditor: AuditService,
        documents: DocumentRepository | None = None,
    ) -> None:
        self.projects = projects
        self.diagnostics = diagnostics
        self.reports = reports
        self.jobs = jobs
        self.auditor = auditor
        self.documents = documents
        self.session = projects.session
        self.states = ProjectStateService(projects, auditor)

    async def start_guided(self, *, owner_id: UUID, data: ManualDiagnosticIn) -> DiagnosticCreatedOut:
        return await self._start(
            owner_id=owner_id,
            title=data.project_name,
            sector=data.sector,
            archetype=data.archetype,
            stage=data.stage,
            mode=EntryMode.GUIDED,
            description=data.description,
            answers=data.answers,
            funding_need=data.funding_need,
            document_id=None,
        )

    async def start_from_document(self, *, owner_id: UUID, data: UploadDiagnosticIn) -> DiagnosticCreatedOut:
        # SEC-07 : vérifier que le document appartient bien au porteur.
        if data.document_id is not None and self.documents is not None:
            from app.core.errors import ForbiddenError, NotFoundError

            doc = await self.documents.get_by_id(data.document_id)
            if doc is None:
                raise NotFoundError("document")
            if doc.owner_id != owner_id:
                raise ForbiddenError("Ce document ne vous appartient pas.")
        return await self._start(
            owner_id=owner_id,
            title=data.project_name,
            sector=data.sector,
            archetype=data.archetype,
            stage=data.stage,
            mode=EntryMode.DOCUMENT,
            description=None,  # extraite du document par le worker
            answers=None,
            funding_need=None,
            document_id=data.document_id,
        )

    async def _start(
        self,
        *,
        owner_id: UUID,
        title: str,
        sector: str,
        archetype: Archetype,
        stage: ProjectStage,
        mode: EntryMode,
        description: str | None,
        answers: dict[str, str] | None,
        funding_need: int | None,
        document_id: UUID | None,
    ) -> DiagnosticCreatedOut:
        # 1) Projet créé en brouillon, puis transition auditée vers le traitement.
        project = await self.projects.create(
            owner_id=owner_id,
            title=title,
            sector=sector,
            archetype=archetype,
            stage=stage,
            diagnostic_status=DiagnosticStatus.DRAFT,
            review_status=ReviewStatus.NEW_DIAGNOSTIC,
        )
        # 2) Diagnostic (l'entrée du porteur).
        diagnostic = await self.diagnostics.create(
            project_id=project.id,
            owner_id=owner_id,
            mode=mode,
            description=description,
            answers=answers,
            funding_need=funding_need,
            document_id=document_id,
        )
        await self.states.transition_diagnostic(
            project,
            DiagnosticStatus.DIAGNOSTIC_IN_PROGRESS,
            actor_id=owner_id,
        )
        # 3) Bilan en attente (rempli par le worker).
        report = await self.reports.create_pending(project_id=project.id, diagnostic_id=diagnostic.id)
        # 4) Audit + enqueue du job d'analyse (dans la même transaction).
        await self.auditor.record(
            actor_id=owner_id,
            action="diagnostic.started",
            entity="diagnostic",
            entity_id=diagnostic.id,
            new_value={"mode": mode.value, "sector": sector},
        )
        await self.jobs.enqueue(
            job_type=RUN_DIAGNOSTIC_JOB,
            payload={
                "diagnostic_id": str(diagnostic.id),
                "project_id": str(project.id),
                "report_id": str(report.id),
                "mode": mode.value,
            },
            idempotency_key=f"{RUN_DIAGNOSTIC_JOB}:{diagnostic.id}",
            correlation_id=diagnostic.id,
            project_id=project.id,
        )
        await self.session.commit()

        return DiagnosticCreatedOut(
            diagnostic_id=diagnostic.id,
            project_id=project.id,
            report_id=report.id,
            mode=mode,
            diagnostic_status=project.diagnostic_status,
            review_status=project.review_status,
        )
