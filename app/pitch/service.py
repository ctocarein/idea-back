"""Service de l'éditeur de pitch (V1.2).

L'IA amorce/améliore chaque section à partir du travail réel du porteur dans le
Workshop (synthèses `form_data` par dimension) et de ses fiches de besoin. Le
porteur reste maître : l'IA propose, il édite et enregistre.
"""

from __future__ import annotations

from uuid import UUID

from app.academy.repository import AcademyRepository
from app.core.config import get_settings
from app.core.errors import (
    BusinessRuleError,
    ForbiddenError,
    NotFoundError,
    PaymentRequiredError,
)
from app.iam.dependencies import AuthContext
from app.llm.base import LLMProvider
from app.llm.prompt import build_pitch_section_prompt
from app.pitch.export import (
    render_pitch_html,
    render_pitch_pdf,
    render_pitch_pptx,
)
from app.pitch.models import Pitch
from app.pitch.repository import PitchRepository
from app.pitch.schemas import PitchOut, PitchSectionOut, SectionGenerateOut
from app.pitch.sections import PITCH_SECTIONS, default_sections
from app.projects.repository import ProjectRepository

_SECTION_BY_KEY = {s["key"]: s for s in PITCH_SECTIONS}


class PitchService:
    def __init__(
        self,
        repo: PitchRepository,
        provider: LLMProvider,
        projects: ProjectRepository | None = None,
        academy: AcademyRepository | None = None,
    ) -> None:
        self.repo = repo
        self.provider = provider
        self.projects = projects
        self.academy = academy
        self.session = repo.session

    async def _project_context(self, ctx: AuthContext) -> tuple[str | None, str | None, UUID | None]:
        if self.projects is None:
            return None, None, None
        p = await self.projects.get_latest_for_owner(ctx.user.id)
        if p is None:
            return None, None, None
        return p.title, p.sector, p.id

    async def get_or_create(self, ctx: AuthContext) -> PitchOut:
        pitch = await self.repo.get_latest_for_owner(ctx.user.id)
        if pitch is None:
            _title, _sector, project_id = await self._project_context(ctx)
            pitch = await self.repo.create(
                owner_id=ctx.user.id,
                project_id=project_id,
                title="Mon pitch",
                sections=default_sections(),
            )
            await self.session.commit()
            await self.session.refresh(pitch)  # recharge created_at/updated_at (server-side)
        return self._to_out(pitch)

    async def _load_owned(self, ctx: AuthContext, pitch_id: UUID) -> Pitch:
        pitch = await self.repo.get_by_id(pitch_id)
        if pitch is None:
            raise NotFoundError("pitch")
        if pitch.owner_id != ctx.user.id:
            raise ForbiddenError()
        return pitch

    async def update_section(
        self, ctx: AuthContext, pitch_id: UUID, key: str, content: str
    ) -> PitchOut:
        pitch = await self._load_owned(ctx, pitch_id)
        if key not in _SECTION_BY_KEY:
            raise BusinessRuleError(f"Section inconnue : {key}")
        sections = [dict(s) for s in (pitch.sections or [])]
        found = False
        for s in sections:
            if s.get("key") == key:
                s["content"] = content
                found = True
                break
        if not found:
            meta = _SECTION_BY_KEY[key]
            sections.append({"key": key, "title": meta["title"], "content": content})
        pitch.sections = sections
        await self.session.commit()
        await self.session.refresh(pitch)  # recharge updated_at (server-side onupdate)
        return self._to_out(pitch)

    async def _evidence_for(self, ctx: AuthContext, key: str) -> str | None:
        """Matière brute pour amorcer une section : synthèse Workshop ou fiches."""
        meta = _SECTION_BY_KEY.get(key, {})
        if self.academy is None:
            return None
        if key == "ask":
            fiches = await self.academy.list_fiches_for_owner(ctx.user.id)
            if not fiches:
                return None
            return "\n".join(f"- {f.need_type} : {f.title}" for f in fiches[:8])
        dimension = meta.get("dimension")
        if dimension:
            module = await self.academy.get_module_session(ctx.user.id, dimension)
            if module and module.form_data:
                parts = [str(v) for v in module.form_data.values() if str(v).strip()]
                if parts:
                    return "\n".join(parts)
        return None

    async def generate_section(
        self, ctx: AuthContext, pitch_id: UUID, key: str
    ) -> SectionGenerateOut:
        pitch = await self._load_owned(ctx, pitch_id)
        meta = _SECTION_BY_KEY.get(key)
        if meta is None:
            raise BusinessRuleError(f"Section inconnue : {key}")
        existing = next((s.get("content", "") for s in (pitch.sections or []) if s.get("key") == key), "")
        evidence = await self._evidence_for(ctx, key)
        title, sector, _ = await self._project_context(ctx)
        prompt = build_pitch_section_prompt(
            section_title=meta["title"],
            section_hint=meta["hint"],
            existing_content=existing,
            evidence=evidence,
            project_title=title,
            sector=sector,
        )
        result = await self.provider.complete(prompt)
        return SectionGenerateOut(key=key, content=result.text.strip())

    async def export_pitch(
        self, ctx: AuthContext, pitch_id: UUID, fmt: str
    ) -> tuple[bytes, str, str]:
        """Exporte le pitch en PDF ou PPTX. Retourne (bytes, media_type, filename).

        Paywall « prêt mais off » : si `pitch_export_paid` est activé et que le
        porteur n'a pas de droit, on lève 402. Par défaut le flag est off → gratuit.
        """
        if fmt not in {"pdf", "pptx"}:
            raise BusinessRuleError("Format d'export invalide (pdf ou pptx).")
        pitch = await self._load_owned(ctx, pitch_id)

        if get_settings().pitch_export_paid and not self._is_entitled(ctx):
            raise PaymentRequiredError("L'export du pitch nécessite un accès payant.")

        title, _sector, _ = await self._project_context(ctx)
        short = str(pitch_id)[:8]
        if fmt == "pdf":
            data = render_pitch_pdf(render_pitch_html(pitch, project_title=title))
            return data, "application/pdf", f"pitch-{short}.pdf"
        data = render_pitch_pptx(pitch, project_title=title)
        return (
            data,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            f"pitch-{short}.pptx",
        )

    def _is_entitled(self, ctx: AuthContext) -> bool:
        # Aucun système de paiement en V1 → personne n'est débloqué quand le
        # paywall est activé. À brancher sur les droits/abonnements plus tard.
        return False

    def _to_out(self, pitch: Pitch) -> PitchOut:
        # On renvoie les sections dans l'ordre canonique, en injectant le hint.
        by_key = {s.get("key"): s for s in (pitch.sections or [])}
        sections = [
            PitchSectionOut(
                key=meta["key"],
                title=meta["title"],
                hint=meta["hint"],
                content=by_key.get(meta["key"], {}).get("content", ""),
            )
            for meta in PITCH_SECTIONS
        ]
        return PitchOut(id=pitch.id, title=pitch.title, sections=sections, updated_at=pitch.updated_at)
