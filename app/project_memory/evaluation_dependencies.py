"""Assemblage du service de lecture du Radar explicable."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.project_memory.evaluation_service import ProjectEvaluationService
from app.project_memory.repository import ProjectMemoryRepository
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository
from app.scoring.repository import ScoreRunRepository, ScoringRepository


def get_project_evaluation_service(session: AsyncSession = Depends(get_session)) -> ProjectEvaluationService:
    return ProjectEvaluationService(
        projects=ProjectRepository(session),
        memory=ProjectMemoryRepository(session),
        grids=ScoringRepository(session),
        runs=ScoreRunRepository(session),
        reports=ReportRepository(session),
    )
