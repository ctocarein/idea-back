"""Service de l'éditeur de pitch (V1.2).

L'IA amorce/améliore chaque section à partir du travail réel du porteur dans le
Workshop (synthèses `form_data` par dimension) et de ses fiches de besoin. Le
porteur reste maître : l'IA propose, il édite et enregistre.
"""

from __future__ import annotations

import json
import re
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
from app.llm.prompt import build_deck_prompt, build_pitch_section_prompt
from app.pitch.deck_export import render_deck_pdf, render_deck_pptx
from app.pitch.deck_render import TEMPLATES, render_deck_html
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
        # Le deck visuel est le vrai livrable dès qu'il existe ; sinon on retombe
        # sur l'export texte des sections (avant génération du deck).
        has_deck = bool(pitch.slides)
        if fmt == "pdf":
            if has_deck:
                deck_html = render_deck_html(pitch, project_title=title, export=True)
                data = await render_deck_pdf(deck_html)
            else:
                data = render_pitch_pdf(render_pitch_html(pitch, project_title=title))
            return data, "application/pdf", f"pitch-{short}.pdf"
        if has_deck:
            deck_html = render_deck_html(pitch, project_title=title, export=True)
            data = await render_deck_pptx(deck_html)
        else:
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
        return PitchOut(
            id=pitch.id,
            title=pitch.title,
            sections=sections,
            template_id=pitch.template_id or "base",
            slides=pitch.slides or [],
            updated_at=pitch.updated_at,
        )

    # --- Deck visuel (V1.3) ---

    async def set_template(self, ctx: AuthContext, pitch_id: UUID, template_id: str) -> PitchOut:
        if template_id not in TEMPLATES:
            raise BusinessRuleError(f"Template inconnu : {template_id}")
        pitch = await self._load_owned(ctx, pitch_id)
        pitch.template_id = template_id
        await self.session.commit()
        await self.session.refresh(pitch)
        return self._to_out(pitch)

    async def update_slide(
        self, ctx: AuthContext, pitch_id: UUID, index: int, fields: dict
    ) -> PitchOut:
        """Met à jour les champs d'UNE slide (édition structurée)."""
        pitch = await self._load_owned(ctx, pitch_id)
        slides = [dict(s) for s in (pitch.slides or [])]
        if not 0 <= index < len(slides):
            raise NotFoundError("slide")
        for k, v in fields.items():
            if v is not None:
                slides[index][k] = v
        pitch.slides = slides
        await self.session.commit()
        await self.session.refresh(pitch)
        return self._to_out(pitch)

    async def delete_slide(self, ctx: AuthContext, pitch_id: UUID, index: int) -> PitchOut:
        pitch = await self._load_owned(ctx, pitch_id)
        slides = [dict(s) for s in (pitch.slides or [])]
        if not 0 <= index < len(slides):
            raise NotFoundError("slide")
        del slides[index]
        pitch.slides = slides
        await self.session.commit()
        await self.session.refresh(pitch)
        return self._to_out(pitch)

    async def reorder_slides(
        self, ctx: AuthContext, pitch_id: UUID, order: list[int]
    ) -> PitchOut:
        pitch = await self._load_owned(ctx, pitch_id)
        slides = list(pitch.slides or [])
        if sorted(order) != list(range(len(slides))):
            raise BusinessRuleError("Ordre invalide (doit être une permutation des slides).")
        pitch.slides = [slides[i] for i in order]
        await self.session.commit()
        await self.session.refresh(pitch)
        return self._to_out(pitch)

    async def generate_deck(
        self, ctx: AuthContext, pitch_id: UUID, source: str | None = None
    ) -> PitchOut:
        """Génère les slides structurées depuis la source (texte fourni ou sections)."""
        pitch = await self._load_owned(ctx, pitch_id)
        material = (source or "").strip()
        if not material:
            material = "\n\n".join(
                f"{s.get('title','')} : {s.get('content','')}"
                for s in (pitch.sections or [])
                if str(s.get("content", "")).strip()
            )
        if not material:
            material = await self._workshop_material(ctx)
        if not material:
            raise BusinessRuleError(
                "Rien à générer : fais ton diagnostic / travaille un axe dans le Workshop, "
                "colle un texte, ou importe un pitch."
            )
        title, sector, _ = await self._project_context(ctx)
        prompt = build_deck_prompt(source=material, project_title=title, sector=sector)
        result = await self.provider.complete(prompt)
        try:
            parsed = json.loads(self._extract_json(result.text))
            slides = parsed.get("slides", []) if isinstance(parsed, dict) else []
        except (json.JSONDecodeError, ValueError):
            slides = []
        if not slides:
            raise BusinessRuleError("La génération du deck a échoué. Réessaie.")
        pitch.slides = [s for s in slides if isinstance(s, dict)]
        await self.session.commit()
        await self.session.refresh(pitch)
        return self._to_out(pitch)

    async def _workshop_material(self, ctx: AuthContext) -> str:
        """Matière issue du Workshop : synthèses des modules + fiches de besoin."""
        if self.academy is None:
            return ""
        parts: list[str] = []
        for dim, _phase, sid, _after in await self.academy.list_started_dimensions(ctx.user.id):
            module = await self.academy.get_module_session(ctx.user.id, dim)
            if module and module.form_data:
                vals = [str(v) for v in module.form_data.values() if str(v).strip()]
                if vals:
                    parts.append("\n".join(vals))
        fiches = await self.academy.list_fiches_for_owner(ctx.user.id)
        if fiches:
            parts.append("Besoins : " + "; ".join(f"{f.need_type} — {f.title}" for f in fiches[:8]))
        return "\n\n".join(parts)

    async def render_deck(self, ctx: AuthContext, pitch_id: UUID, *, standalone: bool = True) -> str:
        pitch = await self._load_owned(ctx, pitch_id)
        title, _sector, _ = await self._project_context(ctx)
        return render_deck_html(pitch, project_title=title, standalone=standalone)

    @staticmethod
    def _extract_json(text: str) -> str:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            return m.group(1).strip()
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        return m.group(1).strip() if m else text.strip()
