"""Fallback multi-provider — bascule ordonnée si un provider échoue.

Complète le pilier 6 : le circuit breaker dégrade PAR modèle ; ce wrapper bascule VERS UN
AUTRE provider (ex. DeepSeek down → Mistral) pour que le chemin critique (scoring) ne
s'arrête jamais sur l'indisponibilité d'un fournisseur. Si tous échouent, on lève la
dernière erreur (le job sera rejoué, le bilan reste `pending` — jamais de faux score).

Découplé de httpx : il ne manipule que des exceptions LLM (traduites par les providers)
et `CircuitOpenError` → testable hors-ligne avec des providers factices.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.resilience import CircuitOpenError
from app.llm.base import LLMError, LLMProvider, LLMResult

logger = get_logger("llm")

# Exceptions qui justifient un basculement vers le provider suivant.
_FAILOVER = (LLMError, CircuitOpenError)


class FallbackProvider:
    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("FallbackProvider requiert au moins un provider.")
        self._providers = providers
        # `model` = chaîne ordonnée des modèles (tracée dans le ScoreRun).
        self.model = "→".join(p.model for p in providers)

    @property
    def supports_vision(self) -> bool:
        # Le wrapper voit les images si AU MOINS un provider de la chaîne le sait.
        return any(getattr(p, "supports_vision", False) for p in self._providers)

    async def complete(self, prompt: str, *, max_tokens: int = 1024) -> LLMResult:
        return await self._with_failover("complete", lambda p: p.complete(prompt, max_tokens=max_tokens))

    async def analyze_json(
        self, prompt: str, *, schema: dict | None = None, max_tokens: int | None = None
    ) -> dict:
        return await self._with_failover(
            "analyze_json", lambda p: p.analyze_json(prompt, schema=schema, max_tokens=max_tokens)
        )

    async def analyze_json_with_images(
        self, prompt: str, *, images: list[str], schema: dict | None = None
    ) -> dict:
        # Bascule UNIQUEMENT sur les providers qui voient les images (Pixtral…).
        vision = [p for p in self._providers if getattr(p, "supports_vision", False)]
        last_exc: Exception | None = None
        for provider in vision:
            try:
                return await provider.analyze_json_with_images(  # type: ignore[attr-defined]
                    prompt, images=images, schema=schema
                )
            except _FAILOVER as exc:
                last_exc = exc
                continue
        if last_exc is not None:
            raise last_exc
        return await self.analyze_json(prompt, schema=schema)  # aucun vision → texte seul

    async def _with_failover(self, op: str, call):
        last_exc: Exception | None = None
        for index, provider in enumerate(self._providers):
            try:
                return await call(provider)
            except _FAILOVER as exc:
                last_exc = exc
                is_last = index == len(self._providers) - 1
                logger.warning(
                    "llm_failover",
                    op=op,
                    model=provider.model,
                    rank=index,
                    last=is_last,
                    error=str(exc),
                )
                continue
        # Tous les providers ont échoué : on remonte la dernière erreur.
        raise last_exc if last_exc is not None else LLMError("aucun provider LLM disponible")
