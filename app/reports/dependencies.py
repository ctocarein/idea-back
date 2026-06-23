"""Assemblage du service reports."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.core.database import get_session
from app.instrumentation.service import InstrumentationService
from app.projects.repository import ProjectRepository
from app.reports.edit_service import ReportEditService
from app.reports.repository import ReportRepository
from app.reports.service import ReportService
from app.scoring.repository import ScoreRunRepository, ScoringRepository
from app.scoring.service import ScoringService


def get_report_service(session: AsyncSession = Depends(get_session)) -> ReportService:
    return ReportService(
        ReportRepository(session),
        ProjectRepository(session),
        InstrumentationService(session),
    )


def get_report_edit_service(
    session: AsyncSession = Depends(get_session),
) -> ReportEditService:
    return ReportEditService(
        reports=ReportRepository(session),
        projects=ProjectRepository(session),
        scoring=ScoringService(ScoringRepository(session), ScoreRunRepository(session)),
        auditor=AuditService(session),
    )
