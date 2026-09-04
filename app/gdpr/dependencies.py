"""Assemblage du service RGPD."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.core.database import get_session
from app.core.storage import get_storage
from app.diagnostics.draft_repository import DiagnosticDraftRepository
from app.documents.repository import DocumentRepository
from app.gdpr.service import GdprService
from app.iam.repository import UserRepository
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository


def get_gdpr_service(session: AsyncSession = Depends(get_session)) -> GdprService:
    return GdprService(
        users=UserRepository(session),
        projects=ProjectRepository(session),
        reports=ReportRepository(session),
        documents=DocumentRepository(session),
        drafts=DiagnosticDraftRepository(session),
        auditor=AuditService(session),
        storage=get_storage(),
    )
