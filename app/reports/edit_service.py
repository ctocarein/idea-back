"""Affinage humain du pré-diagnostic — l'analyste/mentor dispose.

Deux gestes, audités, dans la transaction de la requête (autobegin + commit) :
  - `adjust_scores` : ré-évalue les 12 dimensions → `build_score(source=HUMAN)` → nouveau
    `ScoreRun` (traçable, alimente la calibration IA↔expert) → met à jour le bilan.
  - `edit_report`  : fusionne une édition partielle de la couche structurée du rapport.

Garde : admin partout ; mentor/analyste uniquement sur le projet qui lui est assigné.
"""

from __future__ import annotations

from uuid import UUID

from app.audit.service import AuditService
from app.core.errors import NotFoundError
from app.iam.dependencies import AuthContext, guard_assigned_or_admin
from app.project_memory.evaluation import ProjectEvaluationProjector
from app.project_memory.repository import ProjectMemoryRepository
from app.projects.models import Project
from app.projects.repository import ProjectRepository
from app.reports.models import Report
from app.reports.repository import ReportRepository
from app.reports.schemas import DiagnosticReport, ReportDetailOut, ScoreAdjustIn
from app.scoring.actions import derive_next_actions
from app.scoring.models import ScoreSource
from app.scoring.repository import ScoreRunRepository
from app.scoring.schemas import ScoreResult
from app.scoring.service import ScoringService


class ReportEditService:
    def __init__(
        self,
        *,
        reports: ReportRepository,
        projects: ProjectRepository,
        scoring: ScoringService,
        auditor: AuditService,
    ) -> None:
        self.reports = reports
        self.projects = projects
        self.scoring = scoring
        self.auditor = auditor
        self.session = reports.session

    async def _load(self, report_id: UUID, ctx: AuthContext) -> tuple[Report, Project]:
        report = await self.reports.get_by_id(report_id)
        if report is None:
            raise NotFoundError("report")
        project = await self.projects.get_by_id(report.project_id)
        if project is None:
            raise NotFoundError("project")
        # Permission + assignation (admin passe via PROJECT_READ_ANY).
        guard_assigned_or_admin(assignee_id=project.assignee_id, ctx=ctx)
        return report, project

    async def adjust_scores(self, report_id: UUID, ctx: AuthContext, data: ScoreAdjustIn) -> ScoreResult:
        report, project = await self._load(report_id, ctx)
        # Validation stricte (bornes + ancres) + nouveau ScoreRun source=human.
        result = await self.scoring.build_score(
            project_id=project.id,
            diagnostic_id=report.diagnostic_id,
            report_id=report.id,
            category=project.sector,
            axes=data.axes,
            justifications=data.justifications,
            grid_version=data.grid_version,
            source=ScoreSource.HUMAN,
            model="human",
        )
        report.radar_score = {"gridVersion": result.grid_version, "axes": result.axes}
        report.comprehension = {"pillars": result.pillars, "overall": result.overall}
        # Recalcule le routage (les axes faibles ont pu changer).
        grid = await self.scoring.repo.get_by_version(result.grid_version)
        if grid is not None:
            report.next_actions = derive_next_actions(
                grid.axes,
                result.axes,
                grid.category_weights,
                project.sector,
                scale_max=grid.scale_max,
            )
            score_run = await ScoreRunRepository(self.session).get_by_id(result.run_id)
            if score_run is not None:
                await ProjectEvaluationProjector(ProjectMemoryRepository(self.session)).persist_from_score_run(
                    project_id=project.id,
                    axes=grid.axes,
                    score_run=score_run,
                    next_actions=report.next_actions,
                    scale_max=grid.scale_max,
                )
        await self.auditor.record(
            actor_id=ctx.user.id,
            action="report.rescored",
            entity="report",
            entity_id=report.id,
            new_value={"overall": result.overall, "axes": result.axes},
        )
        await self.session.commit()
        return result

    async def edit_report(self, report_id: UUID, ctx: AuthContext, patch: DiagnosticReport) -> ReportDetailOut:
        report, _ = await self._load(report_id, ctx)
        # Fusion superficielle : seuls les champs fournis écrasent l'existant.
        merged = {**(report.insights or {}), **patch.model_dump(exclude_unset=True)}
        report.insights = DiagnosticReport.model_validate(merged).model_dump()
        await self.auditor.record(
            actor_id=ctx.user.id,
            action="report.edited",
            entity="report",
            entity_id=report.id,
        )
        await self.session.commit()
        return ReportDetailOut.model_validate(report)
