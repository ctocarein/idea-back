"""Provider Mistral (compatible OpenAI). Défaut/fallback : résidence UE (cf. archi §10)."""

from __future__ import annotations

from app.core.config import Settings
from app.llm.base import ConfigError
from app.llm.openai_compatible import OpenAICompatibleProvider

_BASE_URL = "https://api.mistral.ai/v1"


class MistralProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings) -> None:
        if settings.mistral_api_key is None:
            raise ConfigError("MISTRAL_API_KEY manquante.")
        super().__init__(
            api_key=settings.mistral_api_key.get_secret_value(),
            base_url=_BASE_URL,
            model=settings.mistral_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        )
