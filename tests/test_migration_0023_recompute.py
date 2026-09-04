"""La migration 0023 doit reproduire EXACTEMENT le moteur, pas l'approximer.

`0023_overall_scale_100` recalcule `score_runs.overall` depuis `axes` + la grille qui l'a
produit, plutôt que de convertir ×10 : la conception rejouable rend l'exactitude disponible,
s'en priver introduirait une erreur gratuite.

La formule y est INLINÉE (une migration doit produire le même résultat dans dix ans, même si
le moteur évolue). Ce test est la contrepartie de ce choix : il vérifie qu'au moment de la
révision, la copie figée et le moteur coïncident. S'il casse, c'est que le moteur a bougé —
et il faut alors une NOUVELLE migration, pas une retouche de celle-ci.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.scoring import engine
from app.scoring.constants import AXES, AXIS_KEYS, CATEGORY_WEIGHTS, SCALE_MAX

_MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0023_overall_scale_100.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_0023", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_M = _load_migration()

# Profils couvrant les cas qui séparent les deux implémentations : extrêmes, médian,
# dimension calibrée isolée, et un profil quelconque non symétrique.
_PROFILES = [
    dict.fromkeys(AXIS_KEYS, 0),
    dict.fromkeys(AXIS_KEYS, SCALE_MAX),
    dict.fromkeys(AXIS_KEYS, 5),
    dict.fromkeys(AXIS_KEYS, 0) | {"d6": SCALE_MAX},
    {key: (index * 3) % (SCALE_MAX + 1) for index, key in enumerate(AXIS_KEYS)},
]


@pytest.mark.parametrize("axes", _PROFILES)
@pytest.mark.parametrize("sector", ["finance", "agro", "sante", "tourisme_culture", "autre"])
def test_migration_recompute_matches_engine(axes: dict[str, int], sector: str) -> None:
    expected = engine.weighted_overall(AXES, CATEGORY_WEIGHTS, sector, axes, scale_max=SCALE_MAX)
    got = _M._weighted_overall(AXIS_KEYS, CATEGORY_WEIGHTS.get(sector, {}), axes, SCALE_MAX)
    assert got == expected


@pytest.mark.parametrize("axes", _PROFILES)
def test_migration_pillars_match_engine(axes: dict[str, int]) -> None:
    assert _M._pillar_scores(AXES, axes) == engine.pillar_scores(AXES, axes)


def test_migration_output_is_within_the_canonical_scale() -> None:
    for axes in _PROFILES:
        value = _M._weighted_overall(AXIS_KEYS, CATEGORY_WEIGHTS["finance"], axes, SCALE_MAX)
        assert 0 <= value <= engine.OVERALL_SCALE


def test_migration_tolerates_a_missing_grid_shape() -> None:
    # Base partielle : sans référentiel, on ne fabrique pas un score — on rend 0 sans lever.
    assert _M._weighted_overall([], {}, {"d1": 9}, SCALE_MAX) == 0
    assert _M._weighted_overall(AXIS_KEYS, {}, {}, 0) == 0
