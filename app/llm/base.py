"""Protocole LLM + types + exceptions — surface commune à tous les providers.

Le métier ne dépend QUE de ce protocole. Les implémentations concrètes (DeepSeek,
Mistral, OpenAI) sont compatibles OpenAI et enveloppées par app/core/resilience.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class LLMResult:
    # Résultat normalisé d'une complétion, indépendant du provider.
    text: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


class LLMProvider(Protocol):
    model: str

    async def complete(self, prompt: str, *, max_tokens: int = 1024) -> LLMResult:
        # Complétion texte libre.
        ...

    async def analyze_json(self, prompt: str, *, schema: dict | None = None) -> dict:
        # Complétion contrainte à un JSON validable (parsing strict).
        ...


# --- Exceptions ------------------------------------------------------------


class LLMError(Exception):
    """Erreur LLM générique (réponse 4xx, provider mal configuré, etc.)."""


class ConfigError(LLMError):
    """Configuration LLM invalide (clé manquante, provider inconnu)."""


class TransientLLMError(LLMError):
    """Erreur transitoire (5xx, indisponibilité) — éligible au retry."""


class LLMParseError(LLMError):
    """La sortie du modèle n'est pas un JSON exploitable — déclenche retry/revue."""
