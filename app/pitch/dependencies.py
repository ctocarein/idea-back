"""Assemblage du service Pitch."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.academy.repository import AcademyRepository
from app.core.config import get_settings
from app.core.database import get_session
from app.llm.factory import get_llm
from app.pitch.repository import PitchRepository
from app.pitch.service import PitchService
from app.projects.repository import ProjectRepository


def get_pitch_service(session: AsyncSession = Depends(get_session)) -> PitchService:
    return PitchService(
        PitchRepository(session),
        get_llm(get_settings()),
        ProjectRepository(session),
        AcademyRepository(session),
    )
