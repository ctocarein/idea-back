"""Intégrité de la rubrique de pitch + cohérence des comités (pur, sans DB).

Mêmes garanties que la grille Radar : les ancres couvrent 0..10, les poids sont sains,
et chaque obsession de juge pointe un axe Fond réel (lien faiblesse→juge du moteur de scénario).
"""

from __future__ import annotations

import pytest

from app.pitchsim.constants import (
    BIO_AXES,
    COMMITTEES,
    PITCH_AXES,
    PITCH_SCALE_MAX,
)
from app.scoring import engine


def test_rubric_has_eight_fond_axes():
    assert len(PITCH_AXES) == 8
    assert all(a["kind"] == "fond" and a["source"] == "llm" for a in PITCH_AXES)


def test_anchors_cover_full_range():
    # Réutilise la validation de la grille Radar : ancres contiguës 0..10.
    engine.validate_grid(PITCH_AXES, PITCH_SCALE_MAX)


def test_weights_sum_to_one():
    total = sum(a["weight"] for a in PITCH_AXES)
    assert abs(total - 1.0) < 1e-9


def test_axis_keys_unique():
    keys = [a["key"] for a in PITCH_AXES]
    assert len(keys) == len(set(keys))


def test_bio_axes_are_deferred():
    assert len(BIO_AXES) == 2
    assert all(a["source"] == "biometric" and a["available"] == "camera" for a in BIO_AXES)


def test_three_committees_with_personas():
    keys = {c["key"] for c in COMMITTEES}
    assert keys == {"incubateur", "concours", "investisseur"}
    assert all(len(c["personas"]) >= 3 for c in COMMITTEES)


def test_every_persona_obsession_is_a_real_fond_axis():
    fond_keys = {a["key"] for a in PITCH_AXES}
    for c in COMMITTEES:
        for p in c["personas"]:
            assert p["obsession"] in fond_keys, f"{p['name']} vise un axe inconnu : {p['obsession']}"


@pytest.mark.parametrize("axis", PITCH_AXES)
def test_each_axis_has_a_central_question(axis):
    assert axis["central_question"].strip()
