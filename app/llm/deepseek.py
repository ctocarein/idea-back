"""Provider DeepSeek (compatible OpenAI). Défaut : coût + résidence (cf. archi §10)."""

from __future__ import annotations

from app.core.config import Settings
from app.llm.base import ConfigError
from app.llm.openai_compatible import OpenAICompatibleProvider

_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings) -> None:
        if settings.deepseek_api_key is None:
            raise ConfigError("DEEPSEEK_API_KEY manquante.")
        super().__init__(
            api_key=settings.deepseek_api_key.get_secret_value(),
            base_url=_BASE_URL,
            model=settings.deepseek_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        )
