"""Lecture propriétaire du Radar explicable, sans exposer les traces internes brutes."""

from __future__ import annotations

from uuid import UUID

from app.core.errors import NotFoundError
from app.iam.dependencies import AuthContext, guard_owner_access
from app.project_memory.evaluation import build_dimension_projections, select_adaptive_questions
from app.project_memory.evaluation_schemas import (
    AdaptiveQuestionOut,
    DimensionEvaluationOut,
    ProjectEvaluationOut,
)
from app.project_memory.repository import ProjectMemoryRepository
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository
from app.scoring.repository import ScoreRunRepository, ScoringRepository


class ProjectEvaluationService:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        memory: ProjectMemoryRepository,
        grids: ScoringRepository,
        runs: ScoreRunRepository,
        reports: ReportRepository,
    ) -> None:
        self.projects = projects
        self.memory = memory
        self.grids = grids
        self.runs = runs
        self.reports = reports

    async def get_for_owner(self, ctx: AuthContext, project_id: UUID) -> ProjectEvaluationOut:
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("project")
        guard_owner_access(owner_id=project.owner_id, ctx=ctx)

        score_run = await self.runs.get_latest_for_project(project_id)
        grid = await self.grids.get_by_version(score_run.grid_version) if score_run is not None else None
        if grid is None:
            grid = await self.grids.get_active()
        if grid is None:
            raise NotFoundError("Aucune grille Radar active.")

        report = await self.reports.get_latest_for_project(project_id)
        memory_items = await self.memory.list_for_project(project_id, active_only=True, limit=1000)
        projections = build_dimension_projections(
            axes=grid.axes,
            score_run=score_run,
            memory_items=memory_items,
            next_actions=report.next_actions if report is not None else [],
            scale_max=grid.scale_max,
        )
        questions = select_adaptive_questions(projections)
        return ProjectEvaluationOut(
            project_id=project_id,
            grid_version=score_run.grid_version if score_run is not None else grid.version,
            dimensions=[DimensionEvaluationOut(**projection.__dict__) for projection in projections],
            questions=[AdaptiveQuestionOut(**question.__dict__) for question in questions],
            needs_review=bool(score_run.needs_review) if score_run is not None else False,
            confidence=score_run.confidence if score_run is not None else None,
        )
