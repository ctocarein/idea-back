"""Assemblage des services pitchsim."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.storage import get_storage
from app.pitchsim.repository import PitchDeckRepository
from app.pitchsim.service import PitchDeckService


def get_deck_service(session: AsyncSession = Depends(get_session)) -> PitchDeckService:
    return PitchDeckService(PitchDeckRepository(session), get_storage())
