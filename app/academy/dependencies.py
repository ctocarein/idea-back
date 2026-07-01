"""Assemblage du service Academy."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.academy.repository import AcademyRepository
from app.academy.service import AcademyService
from app.core.config import get_settings
from app.core.database import get_session
from app.llm.factory import get_llm
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository
from app.scoring.repository import ScoringRepository


def get_academy_service(session: AsyncSession = Depends(get_session)) -> AcademyService:
    return AcademyService(
        AcademyRepository(session),
        get_llm(get_settings()),
        ProjectRepository(session),
        ReportRepository(session),
        ScoringRepository(session),
    )
