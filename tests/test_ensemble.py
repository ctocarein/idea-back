"""Tests du consensus, de l'incertitude et du routage humain."""

from __future__ import annotations

import pytest

from app.scoring.ensemble import EnsembleThresholds, consensus

AXES = [f"d{index}" for index in range(1, 13)]


def _axes(values: list[int]) -> dict[str, int]:
    return dict(zip(AXES, values))


def test_median_is_robust_to_one_outlier_pass() -> None:
    # Trois passes /10 ; une passe aberrante sur d4 ne tire pas le consensus.
    passes = [
        _axes([8, 7, 6, 5, 6, 7, 5, 6, 7, 8, 6, 5]),
        _axes([8, 7, 6, 6, 6, 7, 5, 6, 7, 8, 6, 5]),
        _axes([8, 7, 6, 1, 6, 7, 5, 6, 7, 8, 6, 5]),
    ]
    result = consensus(passes, AXES)
    assert result.axes["d4"] == 5
    assert result.axes["d1"] == 8


def test_concordant_passes_are_confident_no_review() -> None:
    same = _axes([8, 7, 6, 5, 6, 7, 5, 6, 7, 8, 6, 5])
    result = consensus([same, same, same], AXES)
    assert result.confidence == 1.0
    assert result.uncertain_axes == []
    assert result.needs_human_review is False


def test_divergent_axis_flags_uncertainty_and_routes_to_human() -> None:
    passes = [
        _axes([8, 7, 6, 3, 6, 7, 5, 6, 7, 8, 6, 5]),
        _axes([8, 7, 6, 8, 6, 7, 5, 6, 7, 8, 6, 5]),
        _axes([8, 7, 6, 5, 6, 7, 5, 6, 7, 8, 6, 5]),
    ]
    result = consensus(passes, AXES)
    assert "d4" in result.uncertain_axes
    assert result.per_axis_spread["d4"] == 5
    assert result.needs_human_review is True


def test_too_few_passes_triggers_review() -> None:
    same = _axes([8, 7, 6, 5, 6, 7, 5, 6, 7, 8, 6, 5])
    result = consensus([same, same], AXES)
    assert result.needs_human_review is True
    assert any("passe" in reason for reason in result.reasons)


def test_custom_absolute_threshold_can_loosen_routing() -> None:
    passes = [
        _axes([8, 7, 6, 3, 6, 7, 5, 6, 7, 8, 6, 5]),
        _axes([8, 7, 6, 6, 6, 7, 5, 6, 7, 8, 6, 5]),
        _axes([8, 7, 6, 5, 6, 7, 5, 6, 7, 8, 6, 5]),
    ]
    loose = EnsembleThresholds(axis_spread_tolerance=3, min_confidence=0.0)
    result = consensus(passes, AXES, loose)
    assert result.uncertain_axes == []
    assert result.needs_human_review is False


def test_scale_max_is_explicit_for_legacy_grid() -> None:
    passes = [{"d1": 80}, {"d1": 70}, {"d1": 60}]
    result = consensus(passes, ["d1"], scale_max=100)
    assert result.axes["d1"] == 70
    assert result.per_axis_spread["d1"] == 20
    assert result.uncertain_axes == []


def test_out_of_range_pass_is_rejected() -> None:
    with pytest.raises(ValueError, match="hors bornes"):
        consensus([{"d1": 11}], ["d1"], scale_max=10)


def test_empty_passes_rejected() -> None:
    with pytest.raises(ValueError):
        consensus([], AXES)
