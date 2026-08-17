"""Tests du moteur de scoring v2 — 12 dimensions / 4 piliers / 10, ancrées et pondérées."""

from __future__ import annotations

import pytest

from app.core.errors import BusinessRuleError
from app.scoring import engine
from app.scoring.constants import AXES, AXIS_KEYS, CATEGORY_WEIGHTS, PILLARS, SCALE_MAX

# Score valide : 9 partout, sauf d5/d6/d12 à 0 (les dimensions survalorisées en fintech).
_VALID = {key: 9 for key in AXIS_KEYS}
_VALID.update({"d5": 0, "d6": 0, "d12": 0})


# --- Structure & intégrité ------------------------------------------------


def test_structure_12_dims_4_pillars() -> None:
    assert len(AXES) == 12
    assert len(PILLARS) == 4
    pillar_keys = {p["key"] for p in PILLARS}
    assert all(a["pillar"] in pillar_keys for a in AXES)
    # 3 dimensions par pilier.
    for pk in pillar_keys:
        assert sum(1 for a in AXES if a["pillar"] == pk) == 3


def test_anchors_cover_0_to_10() -> None:
    for axis in AXES:
        assert engine.anchors_cover_range(axis, SCALE_MAX), axis["key"]
    engine.validate_grid(AXES, SCALE_MAX)


def test_validate_grid_rejects_gap() -> None:
    broken = [{"key": "x", "pillar": "sens", "anchors": [{"min": 0, "max": 5, "label": "bas"}]}]  # ne couvre pas 5-10
    with pytest.raises(BusinessRuleError):
        engine.validate_grid(broken, SCALE_MAX)


# --- Validation stricte ----------------------------------------------------


def test_valid_score_passes() -> None:
    engine.validate_axes(AXES, _VALID, SCALE_MAX)


def test_missing_dimension_rejected() -> None:
    incomplete = {k: v for k, v in _VALID.items() if k != "d6"}
    with pytest.raises(BusinessRuleError):
        engine.validate_axes(AXES, incomplete, SCALE_MAX)


def test_out_of_bounds_rejected() -> None:
    with pytest.raises(BusinessRuleError):
        engine.validate_axes(AXES, {**_VALID, "d4": 12}, SCALE_MAX)


def test_unknown_dimension_rejected() -> None:
    with pytest.raises(BusinessRuleError):
        engine.validate_axes(AXES, {**_VALID, "d99": 5}, SCALE_MAX)


# --- Agrégation déterministe ----------------------------------------------


def test_pillar_scores() -> None:
    pillars = engine.pillar_scores(AXES, _VALID)
    assert pillars["sens"] == 9  # d1,d2,d3 = 9,9,9
    assert pillars["viabilite"] == 3  # d4,d5,d6 = 9,0,0 → 3
    assert pillars["scalabilite"] == 9  # d7,d8,d9 = 9,9,9
    assert pillars["execution"] == 6  # d10,d11,d12 = 9,9,0 → 6


def test_weighted_overall_penalizes_finance() -> None:
    # Clé canonique depuis la fermeture du vocabulaire sectoriel (`finance`, ex-`fintech`).
    equal = engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "inconnue", _VALID)
    finance = engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "finance", _VALID)
    assert equal == 7  # round(81/12)
    assert finance == 6  # d5/d6/d12 (=0) survalorisés → tire le global vers le bas
    assert finance < equal


def test_legacy_sector_key_no_longer_weights() -> None:
    """`fintech` n'est plus une clé de pondération : le lookup retombe à 1.0.

    C'est le comportement voulu — les grilles déjà en base gardent leurs clés, et
    aucun bilan existant n'est recalculé. Ce test fixe la conséquence pour qu'elle
    ne soit pas redécouverte comme un bug.
    """
    equal = engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "inconnue", _VALID)
    assert engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "fintech", _VALID) == equal


def test_find_anchor_on_ten_scale() -> None:
    d1 = next(a for a in AXES if a["key"] == "d1")
    assert engine.find_anchor(d1, 0)["min"] == 0
    assert engine.find_anchor(d1, 10)["max"] == 10
