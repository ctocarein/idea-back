"""Accès données du logo (Studio)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.studio.models import Logo


class LogoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, logo_id: UUID) -> Logo | None:
        return await self.session.get(Logo, logo_id)

    async def get_latest_for_owner(self, owner_id: UUID) -> Logo | None:
        result = await self.session.execute(
            select(Logo).where(Logo.owner_id == owner_id).order_by(Logo.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def create(self, *, owner_id: UUID, project_id: UUID | None) -> Logo:
        logo = Logo(owner_id=owner_id, project_id=project_id)
        self.session.add(logo)
        await self.session.flush()
        return logo
