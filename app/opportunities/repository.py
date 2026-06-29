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

    # --- Admin CRUD ----------------------------------------------------------

    async def list_all(self) -> list[Opportunity]:
        # Actives d'abord, puis archivées ; par deadline ASC nulls last.
        result = await self.session.execute(
            select(Opportunity).order_by(
                Opportunity.is_active.desc(),
                Opportunity.deadline.asc().nullslast(),
                Opportunity.title,
            )
        )
        return list(result.scalars())

    async def create_opportunity(
        self,
        *,
        title: str,
        kind: str,
        description: str,
        sector: str | None,
        min_overall: float,
        min_maturity: int | None,
        deadline,
        is_active: bool,
    ) -> Opportunity:
        opp = Opportunity(
            title=title,
            kind=kind,
            description=description,
            sector=sector or None,
            min_overall=min_overall,
            min_maturity=min_maturity,
            deadline=deadline,
            is_active=is_active,
        )
        self.session.add(opp)
        await self.session.flush()
        return opp

    async def update_opportunity(self, opp: Opportunity, *, data: dict) -> None:
        for field, value in data.items():
            setattr(opp, field, value)
        await self.session.flush()

    async def set_active(self, opp: Opportunity, *, active: bool) -> None:
        opp.is_active = active
        await self.session.flush()
