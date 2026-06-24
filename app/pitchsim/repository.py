"""Accès données rubrique de pitch."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pitchsim.models import PitchRubric


class PitchRubricRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, version: str, axes: list[dict], is_active: bool, scale_max: int) -> PitchRubric:
        rubric = PitchRubric(version=version, axes=axes, is_active=is_active, scale_max=scale_max)
        self.session.add(rubric)
        await self.session.flush()
        return rubric

    async def get_by_version(self, version: str) -> PitchRubric | None:
        result = await self.session.execute(select(PitchRubric).where(PitchRubric.version == version))
        return result.scalar_one_or_none()

    async def get_active(self) -> PitchRubric | None:
        result = await self.session.execute(select(PitchRubric).where(PitchRubric.is_active.is_(True)))
        return result.scalars().first()
