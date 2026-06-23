"""Tests du routage déterministe — derive_next_actions (pur, hors-ligne)."""

from __future__ import annotations

from app.scoring.actions import derive_next_actions
from app.scoring.constants import AXES, AXIS_KEYS, CATEGORY_WEIGHTS, SCALE_MAX


def _scores(**weak: int) -> dict[str, int]:
    base = {k: 9 for k in AXIS_KEYS}  # tout fort par défaut
    base.update(weak)
    return base


def test_strong_project_has_no_action() -> None:
    assert derive_next_actions(AXES, _scores(), CATEGORY_WEIGHTS, "fintech") == []


def test_weakest_weighted_axis_is_primary() -> None:
    # d6 (modèle éco) faible ET survalorisé en fintech → action n°1.
    actions = derive_next_actions(AXES, _scores(d6=4, d12=5, d5=6), CATEGORY_WEIGHTS, "fintech", scale_max=SCALE_MAX)
    assert actions[0]["key"] == "d6" and actions[0]["primary"] is True
    assert actions[0]["lever_type"] == "academy"
    assert actions[0]["topic"] == "modele_economique"
    assert actions[0]["label"].startswith("Apprends")
    assert len(actions) == 3 and not actions[1]["primary"]


def test_lever_type_drives_cta_wording() -> None:
    # d3 route vers le simulateur de pitch → CTA « Entraîne-toi ».
    actions = derive_next_actions(AXES, _scores(d3=4), CATEGORY_WEIGHTS, "autre")
    assert actions[0]["key"] == "d3"
    assert actions[0]["lever_type"] == "pitchsim"
    assert actions[0]["label"].startswith("Entraîne-toi")


def test_max_actions_caps_the_list() -> None:
    actions = derive_next_actions(AXES, _scores(d1=2, d2=3, d4=4, d6=5, d9=6), CATEGORY_WEIGHTS, "autre", max_actions=2)
    assert len(actions) == 2


def test_category_weight_changes_ranking() -> None:
    # Mêmes scores : en santé, d12 (×1.4) passe devant d6.
    scores = _scores(d6=5, d12=5)
    fin = derive_next_actions(AXES, scores, CATEGORY_WEIGHTS, "fintech")
    sante = derive_next_actions(AXES, scores, CATEGORY_WEIGHTS, "sante")
    assert fin[0]["key"] == "d6"  # fintech survalorise le modèle éco
    assert sante[0]["key"] == "d12"  # santé survalorise les risques
