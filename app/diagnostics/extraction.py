"""« Raconte, on structure » — extraction synchrone du récit libre en 12 dimensions.

Le porteur raconte son idée ; on repère, pour chaque dimension de la grille, si l'info est déjà
là (preuve) ou s'il faut la demander (question courte). On n'invente rien : pas d'info = manque.
Service isolé (un seul appel LLM, request-time) — ne touche pas au pipeline de scoring asynchrone.
"""

from __future__ import annotations

from app.diagnostics.schemas import ExtractedDimension, IdeaExtractOut
from app.llm.base import LLMProvider
from app.llm.prompt import build_extraction_prompt
from app.scoring.constants import AXES


class IdeaExtractionService:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def extract(self, idea: str, project_name: str | None) -> IdeaExtractOut:
        prompt = build_extraction_prompt(idea=idea, axes=AXES, project_name=project_name)
        raw = await self.provider.analyze_json(prompt)
        by_key = raw.get("dimensions")
        by_key = by_key if isinstance(by_key, dict) else {}

        dims: list[ExtractedDimension] = []
        for axis in AXES:
            d = by_key.get(axis["key"]) or {}
            captured = bool(d.get("captured"))
            dims.append(
                ExtractedDimension(
                    key=axis["key"],
                    label=axis["label"],
                    captured=captured,
                    evidence=(str(d.get("evidence") or "") if captured else ""),
                    question=("" if captured else str(d.get("question") or "")),
                )
            )

        name = raw.get("project_name") or project_name
        if isinstance(name, str):
            name = name.strip() or None
        else:
            name = None

        return IdeaExtractOut(
            project_name=name,
            captured_count=sum(1 for d in dims if d.captured),
            total=len(dims),
            dimensions=dims,
            gaps=[d for d in dims if not d.captured],
        )
