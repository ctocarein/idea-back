"""Assemblage du service de partage."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository
from app.sharing.repository import ShareRepository
from app.sharing.service import ShareService


def get_share_service(session: AsyncSession = Depends(get_session)) -> ShareService:
    return ShareService(ShareRepository(session), ProjectRepository(session), ReportRepository(session))
