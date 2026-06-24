"""Éligibilité opportunités — déterministe, sans DB ni LLM."""

from __future__ import annotations

from app.opportunities.eligibility import evaluate_eligibility


def test_eligible_when_all_criteria_met():
    eligible, missing = evaluate_eligibility(
        min_overall=5,
        min_maturity=4,
        opp_sector="agritech",
        overall=6.0,
        maturity=5,
        sector="agritech",
    )
    assert eligible is True
    assert missing == []


def test_blocked_by_overall_score():
    eligible, missing = evaluate_eligibility(
        min_overall=6,
        min_maturity=None,
        opp_sector=None,
        overall=4.0,
        maturity=None,
        sector="fintech",
    )
    assert eligible is False
    assert any("Score global" in m for m in missing)


def test_blocked_by_maturity_when_unknown():
    # Pas encore de bilan → maturité None → l'opportunité exigeant un avancement bloque.
    eligible, missing = evaluate_eligibility(
        min_overall=0,
        min_maturity=5,
        opp_sector=None,
        overall=0.0,
        maturity=None,
        sector=None,
    )
    assert eligible is False
    assert any("Avancement" in m for m in missing)


def test_blocked_by_sector_mismatch():
    eligible, missing = evaluate_eligibility(
        min_overall=0,
        min_maturity=None,
        opp_sector="agritech",
        overall=9.0,
        maturity=10,
        sector="fintech",
    )
    assert eligible is False
    assert any("secteur" in m for m in missing)


def test_open_opportunity_eligible_for_everyone():
    # Aucune contrainte → éligible même sans bilan.
    eligible, missing = evaluate_eligibility(
        min_overall=0,
        min_maturity=None,
        opp_sector=None,
        overall=0.0,
        maturity=None,
        sector=None,
    )
    assert eligible is True
    assert missing == []
