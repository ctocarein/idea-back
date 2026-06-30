"""Service Academy — leçons, modules guidés (3 phases), fiches de besoin.

Flux module :
  1. start_module() → phase "context" + message d'ouverture du coach
  2. module_turn() × N → conversation de contexte
  3. prefill_form() → l'IA pré-remplit le formulaire depuis la conversation
  4. save_module_form() → le porteur valide/complète le formulaire → phase "form"
  5. generate_fiches() → l'IA génère les fiches de besoin → phase "fiches"
"""

from __future__ import annotations

import json
import re
from uuid import UUID

from app.academy.dimensions import DIMENSION_MODULES
from app.academy.models import GuidedSession, NeedFiche
from app.academy.repository import AcademyRepository
from app.academy.schemas import (
    AcademyProgressOut,
    GuidedSessionOut,
    GuidedStartIn,
    LessonDetailOut,
    LessonOut,
    ModuleSessionOut,
    NeedFicheOut,
    WeaknessListOut,
    WeaknessOut,
)
from app.core.errors import BusinessRuleError, ForbiddenError, NotFoundError
from app.iam.dependencies import AuthContext, guard_owner_access
from app.llm.base import LLMProvider
from app.llm.prompt import (
    build_coach_prompt,
    build_module_fiches_prompt,
    build_module_form_prefill_prompt,
    build_module_opener_prompt,
    build_module_turn_prompt,
)
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository
from app.reports.models import ReportStatus
from app.scoring.constants import AXES


_AXES_BY_KEY: dict[str, dict] = {a["key"]: a for a in AXES}


def _extract_json(text: str) -> str:
    """Extrait le JSON d'une réponse LLM qui peut contenir des code fences."""
    # Cherche un bloc ```json ... ``` ou ``` ... ```
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        return m.group(1).strip()
    # Sinon cherche le premier { ... } ou [ ... ]
    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if m:
        return m.group(1).strip()
    return text.strip()


class AcademyService:
    def __init__(
        self,
        repo: AcademyRepository,
        provider: LLMProvider,
        projects: ProjectRepository | None = None,
        reports: ReportRepository | None = None,
    ) -> None:
        self.repo = repo
        self.provider = provider
        self.projects = projects
        self.reports = reports
        self.session = repo.session

    # --- Leçons ---

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
        if not await self.repo.progress_exists(ctx.user.id, lesson.id):
            await self.repo.add_progress(ctx.user.id, lesson.id)
            await self.session.commit()
        return await self.get_progress(ctx)

    async def get_progress(self, ctx: AuthContext) -> AcademyProgressOut:
        total = await self.repo.count_lessons()
        done = await self.repo.completed_lesson_ids(ctx.user.id)
        return AcademyProgressOut(total_lessons=total, completed_count=len(done), completed_lesson_ids=done)

    # --- Legacy Construire guidé ---

    async def start_guided(self, ctx: AuthContext, data: GuidedStartIn) -> GuidedSessionOut:
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
        gs.turns = [
            *gs.turns,
            {"role": "porteur", "text": message},
            {"role": "coach", "text": result.text},
        ]
        await self.session.commit()
        return GuidedSessionOut.model_validate(gs)

    async def save_draft(self, ctx: AuthContext, session_id: UUID, draft: str) -> GuidedSessionOut:
        gs = await self._load_owned_session(ctx, session_id)
        gs.draft = draft
        await self.session.commit()
        return GuidedSessionOut.model_validate(gs)

    async def get_guided(self, ctx: AuthContext, session_id: UUID) -> GuidedSessionOut:
        gs = await self._load_owned_session(ctx, session_id)
        return GuidedSessionOut.model_validate(gs)

    # --- Modules Academy ---

    async def _get_latest_radar(self, ctx: AuthContext) -> dict | None:
        """Retourne le radar_score du dernier bilan READY du porteur."""
        if self.reports is None:
            return None
        reports = await self.reports.list_for_owner(ctx.user.id)
        for r in reports:
            if r.status == ReportStatus.READY and r.radar_score:
                return r.radar_score
        return None

    async def _get_project_context(self, ctx: AuthContext) -> tuple[str | None, str | None, UUID | None]:
        """Retourne (project_title, sector, project_id) du projet principal du porteur."""
        if self.projects is None:
            return None, None, None
        project = await self.projects.get_latest_for_owner(ctx.user.id)
        if project is None:
            return None, None, None
        return project.title, project.sector, project.id

    async def get_my_weaknesses(self, ctx: AuthContext) -> WeaknessListOut:
        radar = await self._get_latest_radar(ctx)
        if radar is None:
            return WeaknessListOut(weaknesses=[], dimensions_worked=0, has_radar=False)

        axes_scores: dict[str, int] = radar.get("axes") or {}
        # Trier les dimensions par score croissant → les plus faibles en premier
        scored = [
            (key, int(score))
            for key, score in axes_scores.items()
            if key in _AXES_BY_KEY
        ]
        scored.sort(key=lambda x: x[1])
        top3 = scored[:3]

        # Charger les sessions existantes pour savoir lesquelles sont démarrées
        started = {
            dim: (phase, sid)
            for dim, phase, sid in await self.repo.list_started_dimensions(ctx.user.id)
        }

        weaknesses = []
        for dim_key, score in top3:
            axis = _AXES_BY_KEY[dim_key]
            existing = started.get(dim_key)
            weaknesses.append(
                WeaknessOut(
                    dimension=dim_key,
                    label=axis["label"],
                    score=score,
                    central_question=axis["central_question"],
                    pillar=axis["pillar"],
                    module_session_id=existing[1] if existing else None,
                    module_phase=existing[0] if existing else None,
                )
            )

        return WeaknessListOut(
            weaknesses=weaknesses,
            dimensions_worked=len(started),
            has_radar=True,
        )

    async def start_module(
        self,
        ctx: AuthContext,
        dimension: str,
        project_id: UUID | None = None,
    ) -> ModuleSessionOut:
        if dimension not in DIMENSION_MODULES:
            raise BusinessRuleError(f"Dimension inconnue : {dimension}")

        # Si une session de module existe déjà pour cette dimension, la retourner
        existing = await self.repo.get_module_session(ctx.user.id, dimension)
        if existing is not None:
            return await self._build_module_out(existing)

        mod = DIMENSION_MODULES[dimension]

        # Résoudre le project_id si non fourni
        if project_id is None and self.projects is not None:
            project = await self.projects.get_latest_for_owner(ctx.user.id)
            project_id = project.id if project else None

        # Obtenir le contexte projet
        project_title, sector, _ = await self._get_project_context(ctx)
        if project_id is not None and self.projects is not None:
            p = await self.projects.get_by_id(project_id)
            if p and p.owner_id == ctx.user.id:
                project_title = p.title
                sector = p.sector

        # Message d'ouverture du coach
        opener_prompt = build_module_opener_prompt(
            dimension=dimension,
            label=mod["label"],
            context_questions=mod["context_questions"],
            project_title=project_title,
            sector=sector,
        )
        result = await self.provider.complete(opener_prompt)

        gs = await self.repo.create_session(
            owner_id=ctx.user.id,
            project_id=project_id,
            section=mod["label"],
            dimension=dimension,
            phase="context",
        )
        gs.turns = [{"role": "coach", "text": result.text}]
        await self.session.commit()
        return await self._build_module_out(gs)

    async def module_turn(self, ctx: AuthContext, session_id: UUID, message: str) -> ModuleSessionOut:
        gs = await self._load_owned_session(ctx, session_id)
        if gs.dimension is None:
            raise BusinessRuleError("Cette session n'est pas un module Academy.")
        if gs.phase != "context":
            raise BusinessRuleError("La phase de conversation est terminée.")

        mod = DIMENSION_MODULES.get(gs.dimension, {})
        prompt = build_module_turn_prompt(
            dimension=gs.dimension,
            label=mod.get("label", gs.section),
            history=gs.turns,
            message=message,
        )
        result = await self.provider.complete(prompt)
        gs.turns = [
            *gs.turns,
            {"role": "porteur", "text": message},
            {"role": "coach", "text": result.text},
        ]
        await self.session.commit()
        return await self._build_module_out(gs)

    async def prefill_form(self, ctx: AuthContext, session_id: UUID) -> ModuleSessionOut:
        """L'IA pré-remplit le formulaire depuis la conversation de contexte."""
        gs = await self._load_owned_session(ctx, session_id)
        if gs.dimension is None:
            raise BusinessRuleError("Cette session n'est pas un module Academy.")

        mod = DIMENSION_MODULES.get(gs.dimension, {})
        project_title, sector, _ = await self._get_project_context(ctx)

        prompt = build_module_form_prefill_prompt(
            dimension=gs.dimension,
            label=mod.get("label", gs.section),
            form_sections=mod.get("form_sections", []),
            history=gs.turns,
            project_title=project_title,
            sector=sector,
        )
        result = await self.provider.complete(prompt)

        # Parser le JSON retourné par l'IA (peut contenir des code fences)
        try:
            prefilled = json.loads(_extract_json(result.text))
        except (json.JSONDecodeError, ValueError):
            prefilled = {}

        gs.form_data = prefilled
        gs.phase = "form"
        await self.session.commit()
        return await self._build_module_out(gs)

    async def save_module_form(
        self, ctx: AuthContext, session_id: UUID, form_data: dict
    ) -> ModuleSessionOut:
        """Le porteur enregistre le formulaire complété/corrigé."""
        gs = await self._load_owned_session(ctx, session_id)
        if gs.dimension is None:
            raise BusinessRuleError("Cette session n'est pas un module Academy.")
        gs.form_data = form_data
        if gs.phase == "context":
            gs.phase = "form"
        await self.session.commit()
        return await self._build_module_out(gs)

    async def generate_fiches(self, ctx: AuthContext, session_id: UUID) -> ModuleSessionOut:
        """L'IA génère les fiches de besoin à partir du formulaire rempli."""
        gs = await self._load_owned_session(ctx, session_id)
        if gs.dimension is None:
            raise BusinessRuleError("Cette session n'est pas un module Academy.")
        if not gs.form_data:
            raise BusinessRuleError("Le formulaire doit être rempli avant de générer les fiches.")

        mod = DIMENSION_MODULES.get(gs.dimension, {})
        project_title, sector, _ = await self._get_project_context(ctx)

        prompt = build_module_fiches_prompt(
            dimension=gs.dimension,
            label=mod.get("label", gs.section),
            form_data=gs.form_data,
            project_title=project_title,
            sector=sector,
        )
        result = await self.provider.complete(prompt)

        try:
            parsed = json.loads(_extract_json(result.text))
            fiches_data = parsed.get("fiches", []) if isinstance(parsed, dict) else []
        except (json.JSONDecodeError, ValueError):
            fiches_data = []

        for f in fiches_data:
            if not isinstance(f, dict):
                continue
            await self.repo.create_fiche(
                owner_id=ctx.user.id,
                project_id=gs.project_id,
                session_id=gs.id,
                dimension=gs.dimension,
                need_type=f.get("need_type", "autre"),
                title=f.get("title", "Besoin identifié"),
                description=f.get("description", ""),
                details=f.get("details", {}),
            )

        gs.phase = "fiches"
        await self.session.commit()
        return await self._build_module_out(gs)

    async def get_module(self, ctx: AuthContext, session_id: UUID) -> ModuleSessionOut:
        gs = await self._load_owned_session(ctx, session_id)
        return await self._build_module_out(gs)

    async def list_my_fiches(self, ctx: AuthContext) -> list[NeedFicheOut]:
        fiches = await self.repo.list_fiches_for_owner(ctx.user.id)
        return [NeedFicheOut.model_validate(f) for f in fiches]

    async def validate_fiche(self, ctx: AuthContext, fiche_id: UUID) -> NeedFicheOut:
        fiche = await self.repo.get_fiche(fiche_id)
        if fiche is None:
            raise NotFoundError("fiche")
        if fiche.owner_id != ctx.user.id:
            raise ForbiddenError()
        fiche.is_validated = True
        await self.session.commit()
        return NeedFicheOut.model_validate(fiche)

    async def _build_module_out(self, gs: GuidedSession) -> ModuleSessionOut:
        form_sections = []
        if gs.dimension and gs.dimension in DIMENSION_MODULES:
            form_sections = DIMENSION_MODULES[gs.dimension].get("form_sections", [])

        fiches = []
        if gs.phase == "fiches":
            raw = await self.repo.list_fiches_for_session(gs.id)
            fiches = [NeedFicheOut.model_validate(f) for f in raw]

        return ModuleSessionOut(
            id=gs.id,
            dimension=gs.dimension,
            phase=gs.phase,
            turns=gs.turns,
            form_data=gs.form_data,
            form_sections=form_sections,
            fiches=fiches,
        )
