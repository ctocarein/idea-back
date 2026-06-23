"""Sélection du provider LLM selon la config (résidence + coût d'abord).

Le métier ne connaît jamais un provider concret : il appelle get_llm(settings) et reçoit
un objet conforme au protocole `LLMProvider`. Imports paresseux (un provider n'est chargé
que s'il est sélectionné — évite d'importer httpx pour le mock).

Si des `llm_fallbacks` sont configurés (et leurs clés présentes), on renvoie un
`FallbackProvider` qui bascule de l'un à l'autre en cas d'échec (pilier 6).
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.logging import get_logger
from app.llm.base import ConfigError, LLMProvider

logger = get_logger("llm")


def _build(name: str, settings: Settings) -> LLMProvider:
    # Construit un provider par nom. Lève ConfigError si non disponible (clé manquante…).
    provider = name.lower()
    if provider == "mock":
        from app.llm.mock import MockProvider

        return MockProvider(settings)
    if provider == "deepseek":
        from app.llm.deepseek import DeepSeekProvider

        return DeepSeekProvider(settings)
    if provider == "mistral":
        from app.llm.mistral import MistralProvider

        return MistralProvider(settings)
    if provider == "openai":
        from app.llm.openai import OpenAIProvider

        return OpenAIProvider(settings)
    if provider == "gemini":
        from app.llm.gemini import GeminiProvider

        return GeminiProvider(settings)
    raise ConfigError(f"LLM_PROVIDER inconnu : {name!r}")


def get_llm(settings: Settings) -> LLMProvider:
    primary = _build(settings.llm_provider, settings)  # le primaire DOIT être configuré

    # Replis : on n'active que ceux réellement constructibles (clé présente).
    fallbacks: list[LLMProvider] = []
    for name in settings.llm_fallbacks:
        if name.lower() == settings.llm_provider.lower():
            continue
        try:
            fallbacks.append(_build(name, settings))
        except ConfigError as exc:
            logger.warning("llm_fallback_skipped", provider=name, reason=str(exc))

    if not fallbacks:
        return primary

    from app.llm.fallback import FallbackProvider

    return FallbackProvider([primary, *fallbacks])
