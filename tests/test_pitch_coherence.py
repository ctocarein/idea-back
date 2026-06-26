"""Critique réelle : le verdict ET le score voient le deck + jugent la cohérence dit/montré."""

from __future__ import annotations

from app.llm.prompt import build_pitch_prompt, build_verdict_prompt


def test_verdict_sees_the_deck_and_judges_coherence():
    p = build_verdict_prompt(
        persona={"name": "M. Morel", "role": "Serial entrepreneur", "obsession": "scalabilite"},
        transcript="On vise 1M d'utilisateurs en 6 mois.",
        slide_text="Slide 3 : 1200 utilisateurs aujourd'hui.",
        conviction=-1,
    )
    # Le deck est présent dans le prompt…
    assert "1200 utilisateurs" in p
    # …et la consigne de cohérence dit/montré aussi.
    assert "COHÉRENCE" in p
    assert "MONTRÉ" in p


def test_verdict_without_deck_is_explicit():
    p = build_verdict_prompt(
        persona={"name": "Mme Diallo"},
        transcript="Notre équipe est complémentaire.",
        slide_text="",
        conviction=0,
    )
    assert "aucun deck partagé" in p


def test_fond_scoring_penalizes_incoherence():
    p = build_pitch_prompt(
        rubric_axes=[{"key": "traction", "label": "Traction", "anchors": []}],
        committee_label="Comité",
        transcript="Forte traction.",
        slide_text="Aucun chiffre de traction.",
    )
    assert "COHÉRENCE" in p
    assert "PÉNALISE" in p
