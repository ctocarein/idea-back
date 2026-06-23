"""Tests du prompt de scoring + provider mock (purs, hors-ligne)."""

from __future__ import annotations

import asyncio

from app.llm.mock import MockProvider
from app.llm.prompt import build_scoring_prompt

_GRID_AXES = [
    {
        "key": "probleme",
        "label": "Problème",
        "lens": "essence",
        "anchors": [
            {"min": 0, "max": 50, "label": "faible"},
            {"min": 50, "max": 100, "label": "fort"},
        ],
        "guiding_questions": ["Quel problème ?"],
    },
    {
        "key": "marche",
        "label": "Marché",
        "lens": "viabilite",
        "anchors": [
            {"min": 0, "max": 50, "label": "étroit"},
            {"min": 50, "max": 100, "label": "large"},
        ],
        "guiding_questions": ["Qui paie ?"],
    },
]


def test_prompt_contains_anchors_and_axes() -> None:
    prompt = build_scoring_prompt(
        _GRID_AXES,
        category="fintech",
        archetype="digital",
        description="Une appli de paiement.",
        answers={"probleme": "frais élevés"},
        perspective=0,
    )
    assert "fintech" in prompt
    assert "probleme (Problème)" in prompt  # axe + ancres listés
    assert "Angle d'analyse #0" in prompt
    assert "JSON" in prompt


def test_mock_provider_is_deterministic_and_covers_axes() -> None:
    prompt = build_scoring_prompt(
        _GRID_AXES,
        category="fintech",
        archetype="digital",
        description="x" * 30,
        answers=None,
        perspective=1,
    )
    provider = MockProvider()
    out_a = asyncio.run(provider.analyze_json(prompt))
    out_b = asyncio.run(provider.analyze_json(prompt))
    assert out_a == out_b  # déterministe : même prompt → même sortie
    assert set(out_a["axes"]) == {"probleme", "marche"}
    assert all(0 <= v <= 100 for v in out_a["axes"].values())


def test_perspective_changes_scores() -> None:
    # Deux angles d'analyse → dispersion (matière à l'ensemble).
    provider = MockProvider()
    p0 = build_scoring_prompt(
        _GRID_AXES, category="fintech", archetype="digital", description="idem", answers=None, perspective=0
    )
    p1 = build_scoring_prompt(
        _GRID_AXES, category="fintech", archetype="digital", description="idem", answers=None, perspective=1
    )
    a0 = asyncio.run(provider.analyze_json(p0))["axes"]
    a1 = asyncio.run(provider.analyze_json(p1))["axes"]
    assert a0 != a1  # les passes diffèrent → l'ensemble peut mesurer l'incertitude
