"""Accès données de l'éditeur de pitch."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pitch.models import Pitch


class PitchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, pitch_id: UUID) -> Pitch | None:
        return await self.session.get(Pitch, pitch_id)

    async def get_latest_for_owner(self, owner_id: UUID) -> Pitch | None:
        result = await self.session.execute(
            select(Pitch).where(Pitch.owner_id == owner_id).order_by(Pitch.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def create(self, *, owner_id: UUID, project_id: UUID | None, title: str, sections: list[dict]) -> Pitch:
        pitch = Pitch(owner_id=owner_id, project_id=project_id, title=title, sections=sections)
        self.session.add(pitch)
        await self.session.flush()
        return pitch
