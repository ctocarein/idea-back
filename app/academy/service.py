"""Service Academy — leçons, progression, et « construire guidé ».

Construire guidé : l'IA explique et questionne, **le porteur reste l'auteur** (frontière
gratuit/payant). Le routage LLM passe par le provider configuré (bon marché en freemium).
"""

from __future__ import annotations

from uuid import UUID

from app.academy.models import GuidedSession
from app.academy.repository import AcademyRepository
from app.academy.schemas import (
    AcademyProgressOut,
    GuidedSessionOut,
    GuidedStartIn,
    LessonDetailOut,
    LessonOut,
)
from app.core.errors import ForbiddenError, NotFoundError
from app.iam.dependencies import AuthContext, guard_owner_access
from app.llm.base import LLMProvider
from app.llm.prompt import build_coach_prompt
from app.projects.repository import ProjectRepository


class AcademyService:
    def __init__(self, repo: AcademyRepository, provider: LLMProvider, projects: ProjectRepository | None = None) -> None:  # noqa: E501
        self.repo = repo
        self.provider = provider
        self.projects = projects
        self.session = repo.session

    async def list_lessons(self, *, topic: str | None = None) -> list[LessonOut]:
        rows = await self.repo.list_lessons(topic=topic)
        return [LessonOut.model_validate(r) for r in rows]

    async def get_lesson(self, slug: str) -> LessonDetailOut:
        lesson = await self.repo.get_by_slug(slug)
        if lesson is None:
            raise NotFoundError("lesson")
        return LessonDetailOut.model_validate(lesson)

    async def complete_lesson(self, ctx: AuthContext, slug: str) -> AcademyProgressOut:
        lesson = await self.repo.get_by_slug(slug)
        if lesson is None:
            raise NotFoundError("lesson")
        # Idempotent : marquer une leçon déjà complétée ne crée pas de doublon.
        if not await self.repo.progress_exists(ctx.user.id, lesson.id):
            await self.repo.add_progress(ctx.user.id, lesson.id)
            await self.session.commit()
        return await self.get_progress(ctx)

    async def get_progress(self, ctx: AuthContext) -> AcademyProgressOut:
        total = await self.repo.count_lessons()
        done = await self.repo.completed_lesson_ids(ctx.user.id)
        return AcademyProgressOut(total_lessons=total, completed_count=len(done), completed_lesson_ids=done)

    # --- Construire guidé ---

    async def start_guided(self, ctx: AuthContext, data: GuidedStartIn) -> GuidedSessionOut:
        # SEC-07 : vérifier que le project_id fourni appartient bien à l'utilisateur.
        if data.project_id is not None and self.projects is not None:
            project = await self.projects.get_by_id(data.project_id)
            if project is None or project.owner_id != ctx.user.id:
                raise ForbiddenError("Ce projet ne vous appartient pas.")
        gs = await self.repo.create_session(owner_id=ctx.user.id, project_id=data.project_id, section=data.section)
        await self.session.commit()
        return GuidedSessionOut.model_validate(gs)

    async def _load_owned_session(self, ctx: AuthContext, session_id: UUID) -> GuidedSession:
        gs = await self.repo.get_session(session_id)
        if gs is None:
            raise NotFoundError("guided_session")
        guard_owner_access(owner_id=gs.owner_id, ctx=ctx)
        return gs

    async def guided_turn(self, ctx: AuthContext, session_id: UUID, message: str) -> GuidedSessionOut:
        gs = await self._load_owned_session(ctx, session_id)
        prompt = build_coach_prompt(section=gs.section, draft=gs.draft, message=message)
        result = await self.provider.complete(prompt)
        # Réassignation (pas mutation in-place) pour que SQLAlchemy détecte le changement JSONB.
        gs.turns = [
            *gs.turns,
            {"role": "porteur", "text": message},
            {"role": "coach", "text": result.text},
        ]
        await self.session.commit()
        return GuidedSessionOut.model_validate(gs)

    async def save_draft(self, ctx: AuthContext, session_id: UUID, draft: str) -> GuidedSessionOut:
        gs = await self._load_owned_session(ctx, session_id)
        gs.draft = draft  # le texte écrit PAR le porteur
        await self.session.commit()
        return GuidedSessionOut.model_validate(gs)

    async def get_guided(self, ctx: AuthContext, session_id: UUID) -> GuidedSessionOut:
        gs = await self._load_owned_session(ctx, session_id)
        return GuidedSessionOut.model_validate(gs)
