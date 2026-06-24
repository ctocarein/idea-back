"""Accès données rubrique de pitch."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pitchsim.models import (
    PitchDeck,
    PitchRubric,
    PitchRun,
    PitchSession,
    PitchSlide,
    PitchStatus,
    PitchTurn,
    SlideKind,
)


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


class PitchSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(
        self,
        *,
        owner_id: UUID,
        project_id: UUID | None,
        deck_id: UUID | None,
        committee_key: str,
        mode: str,
        rubric_version: str,
        config: dict,
    ) -> PitchSession:
        ps = PitchSession(
            owner_id=owner_id,
            project_id=project_id,
            deck_id=deck_id,
            committee_key=committee_key,
            mode=mode,
            rubric_version=rubric_version,
            config=config,
        )
        self.session.add(ps)
        await self.session.flush()
        return ps

    async def get_session(self, session_id: UUID) -> PitchSession | None:
        return await self.session.get(PitchSession, session_id)

    async def list_for_project(self, project_id: UUID) -> list[PitchSession]:
        result = await self.session.execute(
            select(PitchSession).where(PitchSession.project_id == project_id).order_by(PitchSession.created_at.desc())
        )
        return list(result.scalars())

    async def set_status(self, ps: PitchSession, status: PitchStatus) -> None:
        ps.status = status
        await self.session.flush()

    async def add_turn(
        self,
        session_id: UUID,
        *,
        seq: int,
        actor: str,
        kind: str,
        content: str,
        slide_id: UUID | None = None,
        meta: dict | None = None,
    ) -> PitchTurn:
        turn = PitchTurn(
            session_id=session_id,
            seq=seq,
            actor=actor,
            kind=kind,
            content=content,
            slide_id=slide_id,
            meta=meta or {},
        )
        self.session.add(turn)
        await self.session.flush()
        return turn

    async def turns_for_session(self, session_id: UUID) -> list[PitchTurn]:
        result = await self.session.execute(
            select(PitchTurn).where(PitchTurn.session_id == session_id).order_by(PitchTurn.seq)
        )
        return list(result.scalars())

    async def turn_count(self, session_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(PitchTurn).where(PitchTurn.session_id == session_id)
        )
        return int(result.scalar_one())

    async def project_question_angles(self, project_id: UUID) -> dict[str, list[str]]:
        # Angles déjà posés aux sessions PRÉCÉDENTES du projet (mémoire inter-sessions).
        result = await self.session.execute(
            select(PitchTurn.meta)
            .join(PitchSession, PitchTurn.session_id == PitchSession.id)
            .where(PitchSession.project_id == project_id, PitchTurn.kind == "question")
        )
        out: dict[str, list[str]] = {}
        for meta in result.scalars():
            axis, angle = (meta or {}).get("axis"), (meta or {}).get("angle")
            if axis and angle:
                out.setdefault(axis, []).append(angle)
        return out


class PitchRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **kw: object) -> PitchRun:
        run = PitchRun(**kw)
        self.session.add(run)
        await self.session.flush()
        return run

    async def latest_for_session(self, session_id: UUID) -> PitchRun | None:
        result = await self.session.execute(
            select(PitchRun).where(PitchRun.session_id == session_id).order_by(PitchRun.created_at.desc())
        )
        return result.scalars().first()

    async def list_for_project(self, project_id: UUID) -> list[PitchRun]:
        result = await self.session.execute(
            select(PitchRun).where(PitchRun.project_id == project_id).order_by(PitchRun.created_at)
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
