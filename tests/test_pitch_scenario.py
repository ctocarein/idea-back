"""Moteur de scénario — pur, déterministe, sans DB ni LLM."""

from __future__ import annotations

from app.pitchsim import scenario
from app.pitchsim.constants import committee

INCUB = committee("incubateur")["personas"]


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


def test_interruption_targets_the_judge_whose_obsession_is_weak():
    # M. Morel obsède le marché → il interrompt sur une faiblesse de marché.
    res = scenario.choose_interruption(INCUB, ["marche"], imprevus_enabled=True, hard_questions=True, seed_key="s1")
    assert res is not None
    assert res["actor"] == "M. Morel"
    assert res["axis"] == "marche"


def test_no_interruption_when_disabled():
    assert (
        scenario.choose_interruption(INCUB, ["marche"], imprevus_enabled=False, hard_questions=True, seed_key="s1")
        is None
    )


def test_no_interruption_when_no_judge_cares():
    # Aucun juge du comité n'obsède la "resilience" → personne n'intervient.
    assert (
        scenario.choose_interruption(INCUB, ["resilience"], imprevus_enabled=True, hard_questions=True, seed_key="s1")
        is None
    )


def test_interruption_is_deterministic():
    a = scenario.choose_interruption(INCUB, ["marche"], imprevus_enabled=True, hard_questions=True, seed_key="same")
    b = scenario.choose_interruption(INCUB, ["marche"], imprevus_enabled=True, hard_questions=True, seed_key="same")
    assert a == b


def test_deliberation_one_verdict_per_judge():
    verdicts = scenario.deliberation(INCUB, ["marche"])
    assert len(verdicts) == len(INCUB)
    # Le juge dont l'obsession est faible n'est « pas convaincu ».
    morel = next(v for v in verdicts if v["actor"] == "M. Morel")
    assert "Pas convaincu" in morel["content"]


def test_count_fillers():
    assert scenario.count_fillers("euh, du coup, en fait voilà") >= 3
