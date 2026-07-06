"""Provider LLM MOCK — déterministe, sans réseau (dev, tests, démo, baseline calibration).

Produit des scores d'axes reproductibles à partir d'un hash du prompt : même prompt →
même sortie. Comme le prompt varie d'une passe à l'autre (perspective), l'ensemble obtient
une légère dispersion → on peut exercer tout le pipeline (consensus, confiance, routage)
SANS provider réel. Les vrais providers (DeepSeek/Mistral) arrivent à LLM-01.
"""

from __future__ import annotations

import hashlib
import re

from app.llm.base import LLMResult


def _stable_int(*parts: str) -> int:
    # Entier stable (0..9999) dérivé d'un hash SHA-256 — déterministe, sans Math.random.
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 10000


class MockProvider:
    model = "mock-deterministic"

    def __init__(self, settings: object | None = None) -> None:
        self._settings = settings

    async def complete(self, prompt: str, *, max_tokens: int = 1024) -> LLMResult:
        if "FORMAT=coach" in prompt:
            text = (
                "(mock) Bonne base. Souviens-toi : c'est TOI qui écris, je t'aide à clarifier. "
                "Qui paie concrètement, et pourquoi maintenant ? Quelle est la plus petite preuve "
                "que tu pourrais obtenir cette semaine ?"
            )
            return LLMResult(text=text, model=self.model)
        return LLMResult(text="(mock)", model=self.model)

    async def analyze_json(
        self, prompt: str, *, schema: dict | None = None, max_tokens: int | None = None
    ) -> dict:
        # Plusieurs formats selon le marqueur du prompt. (`max_tokens` ignoré : sortie déterministe.)
        if "FORMAT=verdict" in prompt:
            return {
                "verdict": "(mock) Du potentiel, mais des points à confirmer avant de m'engager.",
                "vote": "conditional",
            }
        if "FORMAT=report" in prompt:
            return self._mock_report()
        # Extrait les clés d'axes ("- <key> (Label) — …") → score stable 30-90.
        axis_keys = re.findall(r"^- (\w+) \(", prompt, flags=re.MULTILINE)
        axes: dict[str, int] = {}
        justifications: dict[str, str] = {}
        for key in axis_keys:
            score = 2 + _stable_int(prompt, key) % 9  # 2..10 (échelle /10)
            axes[key] = score
            justifications[key] = f"(mock) score dérivé pour {key}"
        return {"axes": axes, "justifications": justifications}

    @staticmethod
    def _mock_report() -> dict:
        # Rapport factice mais plausible et structuré (dev/démo offline).
        return {
            "summary": "(mock) Projet au positionnement clair, dont la solidité dépend "
            "surtout de la robustesse du modèle économique à confirmer.",
            "maturity": "Prototype",
            "maturity_rationale": "(mock) preuve d'usage amorcée, monétisation non validée.",
            "description": {
                "problem": "(mock) douleur réelle et fréquente du segment.",
                "solution": "(mock) solution crédible et différenciée.",
                "target_client": "(mock) client idéal du segment.",
                "business_model": "(mock) commission / abonnement à valider.",
            },
            "benchmark": ["(mock) 2-3 acteurs comparables sur le segment"],
            "strengths": [
                {"text": "(mock) problème réel et fréquent", "dimension": "d1"},
                {"text": "(mock) différenciation lisible", "dimension": "d3"},
            ],
            "risks": [
                {"text": "(mock) unit economics à prouver", "probability": "high", "severity": "critical"},
                {"text": "(mock) dépendance à un canal", "probability": "medium", "severity": "high"},
            ],
            "competition": [
                {
                    "name": "(mock) Acteur A",
                    "type": "direct",
                    "description": "(mock) leader segment",
                    "threat": "high",
                },
                {
                    "name": "(mock) Acteur B",
                    "type": "indirect",
                    "description": "(mock) substitut",
                    "threat": "medium",
                },
            ],
            "progress": {"stage": "Prototype", "team_size": 3, "customers": 12, "revenue": 0, "funding": 0},
            "verdict": {
                "status": "conditional",
                "label": "Projet à potentiel sous conditions",
                "analysis": "(mock) Atouts réels côté problème et valeur ; la viabilité dépend "
                "de la preuve du modèle économique et d'une première traction mesurable.",
            },
            "recommendations": [
                {
                    "priority": 1,
                    "title": "(mock) Chiffrer le modèle",
                    "description": "(mock) prix, marge, CAC.",
                },
                {
                    "priority": 2,
                    "title": "(mock) Cadrer le go-to-market",
                    "description": "(mock) canaux initiaux.",
                },
            ],
            "next_steps": [
                {"deadline": "1 semaine", "action": "(mock) interviewer 20 clients cibles."},
                {"deadline": "4 semaines", "action": "(mock) MVP léger pour tester le marché."},
            ],
        }
