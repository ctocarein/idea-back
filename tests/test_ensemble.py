"""Tests de l'ensemble — consensus (médiane), incertitude (étendue), routage humain."""

from __future__ import annotations

import pytest

from app.scoring.ensemble import EnsembleThresholds, consensus

AXES = ["probleme", "valeur", "marche", "modele", "equipe", "croissance"]


def _axes(values: list[int]) -> dict[str, int]:
    return dict(zip(AXES, values))


def test_median_is_robust_to_one_outlier_pass() -> None:
    # 3 passes ; une passe aberrante sur "modele" ne doit pas tirer le consensus.
    passes = [
        _axes([80, 70, 60, 45, 55, 75]),
        _axes([80, 70, 62, 47, 55, 73]),
        _axes([80, 70, 61, 10, 55, 74]),  # outlier sur modele
    ]
    cons = consensus(passes, AXES)
    assert cons.axes["modele"] == 45  # médiane(45,47,10) = 45, pas la moyenne
    assert cons.axes["probleme"] == 80


def test_concordant_passes_are_confident_no_review() -> None:
    same = _axes([80, 70, 60, 50, 55, 75])
    cons = consensus([same, same, same], AXES)
    assert cons.confidence == 1.0
    assert cons.uncertain_axes == []
    assert cons.needs_human_review is False


def test_divergent_axis_flags_uncertainty_and_routes_to_human() -> None:
    passes = [
        _axes([80, 70, 60, 30, 55, 75]),
        _axes([80, 70, 62, 75, 55, 73]),  # "modele" passe de 30 à 75 → étendue 45
        _axes([80, 70, 61, 50, 55, 74]),
    ]
    cons = consensus(passes, AXES)
    assert "modele" in cons.uncertain_axes
    assert cons.per_axis_spread["modele"] == 45
    assert cons.needs_human_review is True


def test_too_few_passes_triggers_review() -> None:
    same = _axes([80, 70, 60, 50, 55, 75])
    cons = consensus([same, same], AXES)  # N=2 < 3 recommandé
    assert cons.needs_human_review is True
    assert any("passe" in r for r in cons.reasons)


def test_custom_thresholds_loosen_routing() -> None:
    passes = [
        _axes([80, 70, 60, 30, 55, 75]),
        _axes([80, 70, 62, 55, 55, 73]),  # modele étendue 25
        _axes([80, 70, 61, 50, 55, 74]),
    ]
    # On tolère jusqu'à 30 pts d'étendue → plus d'axe incertain.
    loose = EnsembleThresholds(axis_spread_tolerance=30, min_confidence=0.0)
    cons = consensus(passes, AXES, loose)
    assert cons.uncertain_axes == []
    assert cons.needs_human_review is False


def test_empty_passes_rejected() -> None:
    with pytest.raises(ValueError):
        consensus([], AXES)
