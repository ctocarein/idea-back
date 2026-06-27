"""Assemblage des services pitchsim."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.storage import get_storage
from app.llm.factory import get_llm
from app.pitchsim.repository import (
    PitchDeckRepository,
    PitchRubricRepository,
    PitchRunRepository,
    PitchSessionRepository,
)
from app.pitchsim.service import PitchDeckService, PitchSessionService
from app.projects.repository import ProjectRepository


def get_deck_service(session: AsyncSession = Depends(get_session)) -> PitchDeckService:
    return PitchDeckService(PitchDeckRepository(session), get_storage())


def get_session_service(session: AsyncSession = Depends(get_session)) -> PitchSessionService:
    return PitchSessionService(
        PitchSessionRepository(session),
        PitchRubricRepository(session),
        PitchRunRepository(session),
        PitchDeckRepository(session),
        ProjectRepository(session),
        get_llm(get_settings()),
        get_storage(),
    )
