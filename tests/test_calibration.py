"""Tests du harnais de calibration — métriques d'accord + porte de non-régression."""

from __future__ import annotations

from app.scoring.calibration import CalibrationThresholds, evaluate

AXES = ["probleme", "valeur", "marche", "modele", "equipe", "croissance"]


def _axes(values: list[int]) -> dict[str, int]:
    return dict(zip(AXES, values))


def test_perfect_agreement_passes_with_zero_mae() -> None:
    expert = _axes([80, 70, 60, 50, 55, 75])
    report = evaluate([(expert, expert)], AXES)
    assert report.passed
    assert report.overall_mae == 0.0
    assert report.within_tolerance_rate == 1.0


def test_close_prediction_passes() -> None:
    expert = _axes([80, 68, 62, 38, 55, 72])
    model = _axes([80, 70, 65, 45, 55, 75])
    report = evaluate([(model, expert)], AXES)
    assert report.passed
    assert report.overall_mae < 10
    assert report.per_axis_mae["modele"] == 7  # l'axe le plus dur ressort


def test_large_divergence_fails_the_gate() -> None:
    expert = _axes([80, 70, 60, 50, 55, 75])
    model = _axes([20, 20, 20, 20, 20, 20])  # prédiction grossièrement fausse
    report = evaluate([(model, expert)], AXES)
    assert not report.passed
    assert report.failures  # au moins un seuil violé


def test_thresholds_are_enforced() -> None:
    expert = _axes([80, 70, 60, 50, 55, 75])
    model = _axes([60, 50, 40, 30, 35, 55])  # 20 pts d'écart partout
    strict = CalibrationThresholds(max_overall_mae=10, tolerance=15)
    report = evaluate([(model, expert)], AXES, strict)
    assert not report.passed
    assert report.within_tolerance_rate == 0.0  # aucun axe sous 15 pts d'écart
