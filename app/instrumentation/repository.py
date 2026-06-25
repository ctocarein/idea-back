"""Lectures analytiques sur les événements (tableau de bord d'apprentissage)."""

from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.instrumentation.models import Event


class InstrumentationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def counts_by_name(self) -> dict[str, int]:
        result = await self.session.execute(select(Event.name, func.count()).group_by(Event.name))
        return {name: int(count) for name, count in result.all()}

    async def distinct_actors_for(self, name: str) -> int:
        result = await self.session.execute(select(func.count(distinct(Event.actor_id))).where(Event.name == name))
        return int(result.scalar_one())
