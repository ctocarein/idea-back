"""Accès données Academy — leçons, progression, sessions guidées."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.academy.models import GuidedSession, LearningProgress, Lesson


class AcademyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_lessons(self, *, topic: str | None = None) -> list[Lesson]:
        stmt = select(Lesson).order_by(Lesson.position, Lesson.title)
        if topic:
            stmt = stmt.where(Lesson.topic == topic)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def get_by_slug(self, slug: str) -> Lesson | None:
        result = await self.session.execute(select(Lesson).where(Lesson.slug == slug))
        return result.scalar_one_or_none()

    async def count_lessons(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Lesson))
        return int(result.scalar_one())

    async def progress_exists(self, user_id: UUID, lesson_id: UUID) -> bool:
        result = await self.session.execute(
            select(LearningProgress.id).where(
                LearningProgress.user_id == user_id,
                LearningProgress.lesson_id == lesson_id,
            )
        )
        return result.first() is not None

    async def add_progress(self, user_id: UUID, lesson_id: UUID) -> None:
        self.session.add(LearningProgress(user_id=user_id, lesson_id=lesson_id))
        await self.session.flush()

    async def completed_lesson_ids(self, user_id: UUID) -> list[UUID]:
        result = await self.session.execute(
            select(LearningProgress.lesson_id).where(LearningProgress.user_id == user_id)
        )
        return list(result.scalars())

    # --- Sessions guidées ---

    async def create_session(self, *, owner_id: UUID, project_id: UUID | None, section: str) -> GuidedSession:
        gs = GuidedSession(owner_id=owner_id, project_id=project_id, section=section, turns=[])
        self.session.add(gs)
        await self.session.flush()
        return gs

    async def get_session(self, session_id: UUID) -> GuidedSession | None:
        return await self.session.get(GuidedSession, session_id)
