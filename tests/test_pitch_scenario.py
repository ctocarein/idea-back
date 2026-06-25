"""Heuristiques de pré-notation — pures, déterministes, sans DB ni LLM."""

from __future__ import annotations

from app.pitchsim import scenario


def test_assess_weakness_flags_empty_narration():
    weak = scenario.assess_weakness("Bonjour.")
    # Court, sans chiffre, sans logique de revenu, sans preuve → plusieurs axes faibles.
    assert "clarte_probleme" in weak
    assert "marche" in weak
    assert "business_model" in weak
    assert "traction" in weak


def test_assess_weakness_strong_narration_is_clean():
    text = (
        "Notre marché vaut 500 millions d'euros, avec 3 pilotes clients et 20% de croissance ; "
        "le modèle repose sur une commission de 2% et une marge de 40%."
    )
    assert scenario.assess_weakness(text) == []


def test_count_fillers():
    assert scenario.count_fillers("euh, du coup, en fait voilà") >= 3
