"""Tests du moteur de scoring v2 — 12 dimensions / 4 piliers / 10, ancrées et pondérées."""

from __future__ import annotations

from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from app.core.errors import BusinessRuleError
from app.scoring import engine
from app.scoring.constants import (
    AXES,
    AXIS_KEYS,
    CALIBRATED_SECTORS,
    CATEGORY_WEIGHTS,
    MATURITY_LEVELS,
    PILLARS,
    SCALE_MAX,
    get_maturity_level,
)
from app.scoring.schemas import RadarScore, ScoreResult, radar_payload

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
    equal = engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "inconnue", _VALID, scale_max=SCALE_MAX)
    finance = engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "finance", _VALID, scale_max=SCALE_MAX)
    assert equal == 68  # round(81/12 * 10)
    assert finance < equal  # d5/d6/d12 (=0) survalorisés → tire le global vers le bas


# --- Échelle du global : /100, unique dans tout le système (SPEC C3) ------


def test_overall_is_normalized_to_100() -> None:
    """Tous les axes à 5 → 50, quels que soient les poids.

    C'est le test qui prouve la NORMALISATION : sans elle, une pondération non neutre
    déplacerait un score pourtant parfaitement médian.
    """
    mid = {key: 5 for key in AXIS_KEYS}
    assert engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "finance", mid, scale_max=SCALE_MAX) == 50
    assert engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "inconnue", mid, scale_max=SCALE_MAX) == 50


def test_overall_bounds() -> None:
    zero = {key: 0 for key in AXIS_KEYS}
    full = {key: SCALE_MAX for key in AXIS_KEYS}
    assert engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "finance", zero, scale_max=SCALE_MAX) == 0
    assert engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "finance", full, scale_max=SCALE_MAX) == 100


def test_weighting_lifts_a_strong_calibrated_dimension() -> None:
    # D6 seule au maximum : pondérée ×1.5 en finance, elle pèse plus qu'à poids neutre.
    axes = {key: 0 for key in AXIS_KEYS} | {"d6": SCALE_MAX}
    finance = engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "finance", axes, scale_max=SCALE_MAX)
    neutral = engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "inconnue", axes, scale_max=SCALE_MAX)
    assert finance > neutral


def test_overall_granularity_beats_ten_scale() -> None:
    """Deux profils distincts ne doivent pas s'écraser sur le même nombre.

    Sur /10 arrondi, 11 valeurs seulement étaient disponibles pour 12 dimensions : des
    projets différents sortaient au même score. La comparabilité EST le produit.
    """
    a = {key: 5 for key in AXIS_KEYS} | {"d1": 6}
    b = {key: 5 for key in AXIS_KEYS} | {"d1": 7}
    scores = {engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "inconnue", axes, scale_max=SCALE_MAX) for axes in (a, b)}
    assert len(scores) == 2


# --- Neutralité ASSUMÉE, pas silencieuse (SPEC C2) ------------------------


def test_uncalibrated_sector_is_neutral_and_flagged() -> None:
    weights = engine.weights_for_category(AXES, CATEGORY_WEIGHTS, "tourisme_culture")
    assert set(weights.values()) == {1.0}
    assert engine.is_calibrated(CATEGORY_WEIGHTS, "tourisme_culture") is False
    assert engine.is_calibrated(CATEGORY_WEIGHTS, "finance") is True


def test_calibrated_sectors_matches_weight_table() -> None:
    assert CALIBRATED_SECTORS == frozenset(CATEGORY_WEIGHTS)


def test_uncalibrated_sector_logs_exactly_one_warning() -> None:
    # Le fallback neutre reste valide, mais cesse d'être invisible en exploitation :
    # un pic sur ce warning signale une grille désalignée du vocabulaire sectoriel.
    with capture_logs() as logs:
        engine.weights_for_category(AXES, CATEGORY_WEIGHTS, "tourisme_culture")
    assert [entry["event"] for entry in logs] == ["scoring_category_unweighted"]
    assert logs[0]["category"] == "tourisme_culture"


def test_calibrated_sector_logs_nothing() -> None:
    with capture_logs() as logs:
        engine.weights_for_category(AXES, CATEGORY_WEIGHTS, "finance")
    assert logs == []


def test_legacy_sector_key_no_longer_weights() -> None:
    """`fintech` n'est plus une clé de pondération : le lookup retombe à 1.0.

    Les grilles ANCIENNES gardent leurs clés « -tech » et restent rejouables telles
    quelles ; la grille active (`radar-v2.1.0`) porte les clés canoniques. Ce test fixe
    la conséquence pour qu'elle ne soit pas redécouverte comme un bug.
    """
    equal = engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "inconnue", _VALID, scale_max=SCALE_MAX)
    assert engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "fintech", _VALID, scale_max=SCALE_MAX) == equal


# --- Divergence pilier / global : VOULUE (SPEC C5) ------------------------


def test_pillar_mean_differs_from_weighted_overall_on_calibrated_sector() -> None:
    """Divergence VOULUE (cf. SPEC_SCORING_INTEGRITY C5). Si ce test casse, une décision a changé.

    Le pilier est une moyenne SIMPLE — il décrit un état. Le global est PONDÉRÉ — il sert
    la comparaison. Les deux ne se reconstituent pas l'un l'autre, et c'est écrit à l'écran
    plutôt que laissé à la déduction du porteur.
    """
    pillars = engine.pillar_scores(AXES, _VALID)
    pillar_mean_100 = round(sum(pillars.values()) / len(pillars) * (100 / SCALE_MAX))
    finance = engine.weighted_overall(AXES, CATEGORY_WEIGHTS, "finance", _VALID, scale_max=SCALE_MAX)
    assert pillar_mean_100 != finance


def test_find_anchor_on_ten_scale() -> None:
    d1 = next(a for a in AXES if a["key"] == "d1")
    assert engine.find_anchor(d1, 0)["min"] == 0
    assert engine.find_anchor(d1, 10)["max"] == 10


# --- Paliers de maturité : source unique (SPEC C4) ------------------------


def test_maturity_levels_tile_the_whole_overall_scale() -> None:
    """Les paliers couvrent 0..100 sans trou ni recouvrement.

    C'est ce qui rend `MATURITY_LEVELS` utilisable comme SOURCE UNIQUE : le front les
    reçoit via `GET /scoring/grid` et n'a aucune borne à redéfinir. Un trou obligerait
    chaque client à inventer un repli — et à diverger.
    """
    levels = sorted(MATURITY_LEVELS, key=lambda lvl: lvl["min"])
    assert levels[0]["min"] == 0
    assert levels[-1]["max"] == engine.OVERALL_SCALE
    for lower, upper in zip(levels, levels[1:], strict=False):
        assert upper["min"] == lower["max"] + 1


@pytest.mark.parametrize(
    ("overall", "expected"),
    [
        (0, "idee_brute"),
        (25, "idee_brute"),
        (26, "a_structurer"),
        (45, "a_structurer"),
        (46, "prometteur"),
        (60, "prometteur"),
        (61, None),
        (75, None),
        (76, None),
        (85, None),
        (86, "investor_ready"),
        (100, "investor_ready"),
    ],
)
def test_maturity_boundaries(overall: int, expected: str | None) -> None:
    # Les bornes exactes — c'est là que les définitions dupliquées divergeaient.
    level = get_maturity_level(overall)
    assert level["min"] <= overall <= level["max"]
    if expected is not None:
        assert level["key"] == expected


def test_every_overall_value_resolves_to_a_level() -> None:
    assert all(get_maturity_level(value) for value in range(0, engine.OVERALL_SCALE + 1))


# --- Le global voyage AVEC le radar (SPEC C3, cause racine) ---------------


def test_radar_payload_carries_the_served_overall() -> None:
    """Le payload persisté porte le global : aucun client n'a plus à le réagréger."""
    result = ScoreResult(
        run_id=uuid4(),
        grid_version="radar-v2.1.0",
        scale_max=SCALE_MAX,
        axes=_VALID,
        pillars=engine.pillar_scores(AXES, _VALID),
        overall=68,
        sector_calibrated=True,
    )
    payload = radar_payload(result)
    assert payload["overall"] == 68
    assert payload["sectorCalibrated"] is True
    assert payload["gridVersion"] == "radar-v2.1.0"

    # Et il se relit dans le DTO servi au client, alias camelCase compris.
    parsed = RadarScore.model_validate(payload)
    assert parsed.overall == 68
    assert parsed.sector_calibrated is True


def test_radar_score_stays_readable_without_the_new_fields() -> None:
    # Compatibilité ascendante : un bilan d'avant la correction reste servable.
    legacy = RadarScore.model_validate({"gridVersion": "radar-v2.0.0-preprod.1", "axes": _VALID})
    assert legacy.overall is None
    assert legacy.sector_calibrated is None
