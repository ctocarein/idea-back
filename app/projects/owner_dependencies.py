"""Assemblage de la façade propriétaire de l'espace projet."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.documents.repository import DocumentRepository
from app.project_memory.repository import ProjectMemoryRepository
from app.projects.owner_service import ProjectOwnerService
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository


def get_project_owner_service(session: AsyncSession = Depends(get_session)) -> ProjectOwnerService:
    return ProjectOwnerService(
        ProjectRepository(session),
        ProjectMemoryRepository(session),
        ReportRepository(session),
        DocumentRepository(session),
    )
