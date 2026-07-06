"""Provider Gemini (optionnel) — API NON compatible OpenAI (à implémenter séparément).

Stub : l'API generateContent de Gemini diffère (endpoint, format de messages, JSON mode).
À câbler quand le besoin se présente ; DeepSeek/Mistral couvrent le MVP.
"""

from __future__ import annotations

from app.core.config import Settings
from app.llm.base import ConfigError


class GeminiProvider:
    model = "gemini"

    def __init__(self, settings: Settings) -> None:
        raise ConfigError("Provider Gemini pas encore implémenté (API non compatible OpenAI).")

    async def complete(self, prompt: str, *, max_tokens: int = 1024):  # pragma: no cover
        raise ConfigError("Gemini non implémenté.")

    async def analyze_json(
        self, prompt: str, *, schema: dict | None = None, max_tokens: int | None = None
    ):  # pragma: no cover
        raise ConfigError("Gemini non implémenté.")
