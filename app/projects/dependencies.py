"""Assemblage du service back-office projets."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.core.database import get_session
from app.iam.repository import UserRepository
from app.projects.repository import ProjectRepository
from app.projects.service import ProjectAdminService
from app.reports.repository import ReportRepository


def get_project_admin_service(
    session: AsyncSession = Depends(get_session),
) -> ProjectAdminService:
    return ProjectAdminService(
        ProjectRepository(session),
        UserRepository(session),
        AuditService(session),
        ReportRepository(session),
    )
