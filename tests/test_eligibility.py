"""Éligibilité opportunités — déterministe, sans DB ni LLM.

Deux échelles distinctes, et c'est le piège que ces tests verrouillent :
`min_overall` porte sur le score global /100, `min_advancement` sur la seule
dimension D11 /10 (SPEC_SCORING_INTEGRITY C3/C4).
"""

from __future__ import annotations

from app.opportunities.eligibility import evaluate_eligibility


def test_eligible_when_all_criteria_met():
    eligible, missing = evaluate_eligibility(
        min_overall=50,
        min_advancement=4,
        opp_sector="agro",
        overall=60.0,
        advancement=5,
        sector="agro",
    )
    assert eligible is True
    assert missing == []


def test_blocked_by_overall_score():
    eligible, missing = evaluate_eligibility(
        min_overall=60,
        min_advancement=None,
        opp_sector=None,
        overall=40.0,
        advancement=None,
        sector="finance",
    )
    assert eligible is False
    assert any("Score global" in m for m in missing)


def test_blocked_by_maturity_when_unknown():
    # Pas encore de bilan → maturité None → l'opportunité exigeant un avancement bloque.
    eligible, missing = evaluate_eligibility(
        min_overall=0,
        min_advancement=5,
        opp_sector=None,
        overall=0.0,
        advancement=None,
        sector=None,
    )
    assert eligible is False
    assert any("Avancement" in m for m in missing)


def test_blocked_by_sector_mismatch():
    eligible, missing = evaluate_eligibility(
        min_overall=0,
        min_advancement=None,
        opp_sector="agro",
        overall=90.0,
        advancement=10,
        sector="finance",
    )
    assert eligible is False
    assert any("secteur" in m for m in missing)


def test_open_opportunity_eligible_for_everyone():
    # Aucune contrainte → éligible même sans bilan.
    eligible, missing = evaluate_eligibility(
        min_overall=0,
        min_advancement=None,
        opp_sector=None,
        overall=0.0,
        advancement=None,
        sector=None,
    )
    assert eligible is True
    assert missing == []
