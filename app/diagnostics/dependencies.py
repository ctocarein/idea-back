"""Assemblage du service diagnostics (injection de dépendances)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.core.config import get_settings
from app.core.database import get_session
from app.diagnostics.extraction import IdeaExtractionService
from app.diagnostics.repository import DiagnosticRepository
from app.diagnostics.service import DiagnosticService
from app.documents.repository import DocumentRepository
from app.jobs.repository import JobRepository
from app.jobs.service import JobService
from app.llm.factory import get_llm
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository


def get_diagnostic_service(
    session: AsyncSession = Depends(get_session),
) -> DiagnosticService:
    return DiagnosticService(
        projects=ProjectRepository(session),
        diagnostics=DiagnosticRepository(session),
        reports=ReportRepository(session),
        jobs=JobService(JobRepository(session)),
        auditor=AuditService(session),
        documents=DocumentRepository(session),
    )


def get_extraction_service() -> IdeaExtractionService:
    # Service synchrone « Raconte, on structure » — un appel LLM, pas de DB.
    return IdeaExtractionService(get_llm(get_settings()))
