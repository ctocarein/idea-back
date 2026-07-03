"""Assemblage du service Studio (logo)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.diagnostics.repository import DiagnosticRepository
from app.llm.factory import get_llm
from app.projects.repository import ProjectRepository
from app.studio.repository import LogoRepository
from app.studio.service import LogoService


def get_logo_service(session: AsyncSession = Depends(get_session)) -> LogoService:
    return LogoService(
        LogoRepository(session),
        get_llm(get_settings()),
        ProjectRepository(session),
        DiagnosticRepository(session),
    )
