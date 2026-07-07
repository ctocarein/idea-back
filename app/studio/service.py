"""Service du Studio — logo (génération, sélection, édition)."""

from __future__ import annotations

from uuid import UUID

from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.diagnostics.repository import DiagnosticRepository
from app.iam.dependencies import AuthContext
from app.llm.base import LLMProvider
from app.projects.repository import ProjectRepository
from app.studio.brand import kit_view
from app.studio.logo_gen import build_logo_prompt, coerce_spec, default_variations, parse_variations
from app.studio.logo_render import render_logo_svg
from app.studio.models import Logo
from app.studio.repository import LogoRepository
from app.studio.schemas import LogoOut, LogoUpdateIn, VariationOut

logger = get_logger("studio")


class LogoService:
    def __init__(
        self,
        repo: LogoRepository,
        provider: LLMProvider,
        projects: ProjectRepository,
        diagnostics: DiagnosticRepository,
    ) -> None:
        self.repo = repo
        self.provider = provider
        self.projects = projects
        self.diagnostics = diagnostics
        self.session = repo.session

    # --- helpers ---------------------------------------------------------------
    def _to_out(self, logo: Logo) -> LogoOut:
        spec = logo.spec
        variations = [
            VariationOut(spec=v, svg=render_logo_svg(v, standalone=True))
            for v in (logo.variations or [])
        ]
        return LogoOut(
            id=logo.id,
            spec=spec,
            svg=render_logo_svg(spec, standalone=True) if spec else None,
            variations=variations,
            updated_at=logo.updated_at,
        )

    async def _project_context(self, ctx: AuthContext) -> tuple[str, str | None, str | None, UUID | None]:
        p = await self.projects.get_latest_for_owner(ctx.user.id)
        if p is None:
            return "Mon projet", None, None, None
        archetype = p.archetype.value if getattr(p, "archetype", None) is not None else None
        return p.title, p.sector, archetype, p.id

    async def _load_owned(self, ctx: AuthContext, logo_id: UUID) -> Logo:
        logo = await self.repo.get_by_id(logo_id)
        if logo is None:
            raise NotFoundError("logo")
        if logo.owner_id != ctx.user.id:
            raise ForbiddenError()
        return logo

    # --- cas d'usage -----------------------------------------------------------
    async def get_kit(self, ctx: AuthContext) -> dict:
        """Vue du kit de marque (dérivé du logo courant) pour l'UI."""
        logo = await self.repo.get_latest_for_owner(ctx.user.id)
        return kit_view(logo.spec if logo is not None else None)

    async def get_or_create(self, ctx: AuthContext) -> LogoOut:
        logo = await self.repo.get_latest_for_owner(ctx.user.id)
        if logo is None:
            _name, _sector, _arch, project_id = await self._project_context(ctx)
            logo = await self.repo.create(owner_id=ctx.user.id, project_id=project_id)
            await self.session.commit()
            await self.session.refresh(logo)
        return self._to_out(logo)

    async def generate(self, ctx: AuthContext, logo_id: UUID) -> LogoOut:
        logo = await self._load_owned(ctx, logo_id)
        name, sector, archetype, _pid = await self._project_context(ctx)

        # Matière thématique : le récit du projet → logo qui raconte CE projet précis.
        diagnostic = await self.diagnostics.get_latest_for_owner(ctx.user.id)
        description = diagnostic.description if diagnostic is not None else None

        variations: list[dict]
        try:
            prompt = build_logo_prompt(name=name, sector=sector, archetype=archetype, description=description, lang=ctx.user.language)
            # 4 briefs (un par angle) = sortie longue : on relève le plafond sinon JSON tronqué.
            raw = await self.provider.analyze_json(prompt, max_tokens=1800)
            variations = parse_variations(raw, name=name, sector=sector)
        except Exception as exc:  # noqa: BLE001 — l'IA ne doit jamais bloquer la génération
            logger.warning("logo_llm_failed", error=str(exc))
            variations = default_variations(name, sector)

        logo.variations = variations
        # Première génération → on sélectionne d'office le 1er concept.
        if not logo.spec and variations:
            logo.spec = variations[0]
        await self.session.commit()
        await self.session.refresh(logo)
        return self._to_out(logo)

    async def select(self, ctx: AuthContext, logo_id: UUID, index: int) -> LogoOut:
        logo = await self._load_owned(ctx, logo_id)
        variations = logo.variations or []
        if not 0 <= index < len(variations):
            raise NotFoundError("variation")
        logo.spec = variations[index]
        await self.session.commit()
        await self.session.refresh(logo)
        return self._to_out(logo)

    async def update_spec(self, ctx: AuthContext, logo_id: UUID, patch: LogoUpdateIn) -> LogoOut:
        logo = await self._load_owned(ctx, logo_id)
        base = dict(logo.spec or default_variations("Mon projet", None)[0])

        data = patch.model_dump(exclude_none=True)
        palette_patch = data.pop("palette", None)
        merged = {**base, **data}
        if isinstance(palette_patch, dict):
            merged["palette"] = {**(base.get("palette") or {}), **palette_patch}

        name = merged.get("name") or base.get("name") or "Mon projet"
        logo.spec = coerce_spec(merged, name=name, sector=None)
        await self.session.commit()
        await self.session.refresh(logo)
        return self._to_out(logo)
