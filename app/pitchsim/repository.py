"""Accès données rubrique de pitch."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pitchsim.models import PitchDeck, PitchRubric, PitchSlide, SlideKind


class PitchDeckRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_deck(self, *, owner_id: UUID, project_id: UUID | None, title: str) -> PitchDeck:
        deck = PitchDeck(owner_id=owner_id, project_id=project_id, title=title)
        self.session.add(deck)
        await self.session.flush()
        return deck

    async def add_slides(self, deck_id: UUID, kind: SlideKind, slides: list[dict]) -> None:
        for i, s in enumerate(slides):
            self.session.add(
                PitchSlide(
                    deck_id=deck_id,
                    kind=kind,
                    position=i,
                    title=s.get("title", ""),
                    extracted_text=s.get("text", ""),
                )
            )
        await self.session.flush()

    async def get_deck(self, deck_id: UUID) -> PitchDeck | None:
        return await self.session.get(PitchDeck, deck_id)

    async def slides_for_deck(self, deck_id: UUID) -> list[PitchSlide]:
        result = await self.session.execute(
            select(PitchSlide).where(PitchSlide.deck_id == deck_id).order_by(PitchSlide.kind, PitchSlide.position)
        )
        return list(result.scalars())


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
