"""Accès données Academy — leçons, progression, sessions modules, fiches de besoin."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.academy.models import GuidedSession, LearningProgress, Lesson, NeedFiche


class AcademyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Leçons ---

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

    # --- Progression ---

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

    # --- Sessions guidées (legacy + modules) ---

    async def create_session(
        self,
        *,
        owner_id: UUID,
        project_id: UUID | None,
        section: str,
        dimension: str | None = None,
        phase: str = "context",
    ) -> GuidedSession:
        gs = GuidedSession(
            owner_id=owner_id,
            project_id=project_id,
            section=section,
            dimension=dimension,
            phase=phase,
            turns=[],
        )
        self.session.add(gs)
        await self.session.flush()
        return gs

    async def get_session(self, session_id: UUID) -> GuidedSession | None:
        return await self.session.get(GuidedSession, session_id)

    async def get_module_session(self, owner_id: UUID, dimension: str) -> GuidedSession | None:
        """Retourne la session de module la plus récente pour un porteur/dimension."""
        result = await self.session.execute(
            select(GuidedSession)
            .where(
                GuidedSession.owner_id == owner_id,
                GuidedSession.dimension == dimension,
            )
            .order_by(GuidedSession.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_started_dimensions(self, owner_id: UUID) -> list[tuple[str, str, UUID]]:
        """Retourne [(dimension, phase, session_id)] pour toutes les sessions de module."""
        result = await self.session.execute(
            select(GuidedSession.dimension, GuidedSession.phase, GuidedSession.id)
            .where(
                GuidedSession.owner_id == owner_id,
                GuidedSession.dimension.is_not(None),
            )
            .order_by(GuidedSession.created_at.desc())
        )
        seen: set[str] = set()
        rows = []
        for dim, phase, sid in result:
            if dim not in seen:
                seen.add(dim)
                rows.append((dim, phase, sid))
        return rows

    # --- Fiches de besoin ---

    async def create_fiche(
        self,
        *,
        owner_id: UUID,
        project_id: UUID | None,
        session_id: UUID | None,
        dimension: str,
        need_type: str,
        title: str,
        description: str,
        details: dict,
    ) -> NeedFiche:
        fiche = NeedFiche(
            owner_id=owner_id,
            project_id=project_id,
            session_id=session_id,
            dimension=dimension,
            need_type=need_type,
            title=title,
            description=description,
            details=details,
        )
        self.session.add(fiche)
        await self.session.flush()
        return fiche

    async def list_fiches_for_owner(self, owner_id: UUID) -> list[NeedFiche]:
        result = await self.session.execute(
            select(NeedFiche)
            .where(NeedFiche.owner_id == owner_id)
            .order_by(NeedFiche.created_at.desc())
        )
        return list(result.scalars())

    async def list_fiches_for_session(self, session_id: UUID) -> list[NeedFiche]:
        result = await self.session.execute(
            select(NeedFiche)
            .where(NeedFiche.session_id == session_id)
            .order_by(NeedFiche.created_at)
        )
        return list(result.scalars())

    async def get_fiche(self, fiche_id: UUID) -> NeedFiche | None:
        return await self.session.get(NeedFiche, fiche_id)
