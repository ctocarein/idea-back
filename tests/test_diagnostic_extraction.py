"""« Raconte, on structure » : le récit → 12 dimensions captées/manquantes, sans rien inventer."""

from __future__ import annotations

import pytest

from app.diagnostics.extraction import IdeaExtractionService


class _FakeProvider:
    model = "fake"

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def analyze_json(self, prompt: str, *, schema: dict | None = None, max_tokens: int | None = None) -> dict:
        return self._payload


@pytest.mark.asyncio
async def test_maps_captured_and_gaps_and_name():
    payload = {
        "project_name": "wedidy",
        "dimensions": {
            "d1": {"captured": True, "evidence": "Supports chers, besoin réel"},
            "d6": {"captured": False, "question": "Comment gagnes-tu de l'argent ?"},
        },
    }
    out = await IdeaExtractionService(_FakeProvider(payload)).extract("récit du porteur…", None)

    assert out.project_name == "wedidy"
    assert out.total == 12
    d1 = next(d for d in out.dimensions if d.key == "d1")
    assert d1.captured and d1.evidence.startswith("Supports") and d1.question == ""
    d6 = next(d for d in out.dimensions if d.key == "d6")
    assert not d6.captured and d6.question.startswith("Comment") and d6.evidence == ""
    # Une dimension absente du payload est un manque (on n'invente pas).
    assert any(d.key == "d2" and not d.captured for d in out.dimensions)
    assert out.captured_count == 1
    assert all(not g.captured for g in out.gaps) and len(out.gaps) == 11


@pytest.mark.asyncio
async def test_falls_back_to_provided_name():
    out = await IdeaExtractionService(_FakeProvider({"dimensions": {}})).extract("x" * 30, "MonProjet")
    assert out.project_name == "MonProjet"
    assert out.captured_count == 0


def test_scoring_prompt_is_honest_about_missing_data():
    from app.llm.prompt import build_scoring_prompt

    p = build_scoring_prompt(
        [{"key": "d1", "label": "Problème", "central_question": "?", "anchors": []}],
        category="edtech",
        archetype="field",
        description="x" * 30,
        answers=None,
    )
    assert "HONNÊTETÉ" in p
    assert "à compléter" in p
