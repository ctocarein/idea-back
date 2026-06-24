"""Accès données opportunités."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.opportunities.models import Opportunity


class OpportunityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> list[Opportunity]:
        result = await self.session.execute(
            select(Opportunity)
            .where(Opportunity.is_active.is_(True))
            .order_by(Opportunity.deadline.asc().nullslast(), Opportunity.title)
        )
        return list(result.scalars())

    async def get_by_id(self, opportunity_id: UUID) -> Opportunity | None:
        return await self.session.get(Opportunity, opportunity_id)
