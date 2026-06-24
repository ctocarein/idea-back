"""Expert métier + timing par comité — purs, sans DB."""

from __future__ import annotations

from app.pitchsim.constants import (
    committee,
    committee_timing,
    expert_for,
    resolve_personas,
)


def test_expert_for_known_sector():
    e = expert_for("fintech")
    assert "Fintech" in e["name"]
    assert e["obsession"] == "business_model"
    assert e["concerns"]


def test_expert_for_unknown_sector_falls_back():
    e = expert_for("secteur-inconnu")
    assert e["name"] == "Expert Secteur"
    # Repli aussi quand le secteur est None.
    assert expert_for(None)["name"] == "Expert Secteur"


def test_resolve_personas_injects_expert_as_extra_judge():
    base = committee("incubateur")["personas"]
    resolved = resolve_personas("incubateur", "fintech")
    assert len(resolved) == len(base) + 1
    assert resolved[-1]["name"] == expert_for("fintech")["name"]
    # L'obsession de l'expert pointe un axe Fond réel (utilisable par l'orchestrateur).
    assert resolved[-1]["obsession"] == "business_model"


def test_committee_timing_defaults_and_bounds():
    incub = committee_timing("incubateur")
    assert incub["qa_questions_per_agent"] == 2
    assert "long" in incub["allowed_formats"]
    # Comité inconnu → repli sûr.
    fallback = committee_timing("inexistant")
    assert fallback["allowed_formats"] == ["standard"]
