"""Agrégation Fond + score Forme — purs, déterministes."""

from __future__ import annotations

from app.pitchsim import evaluate, forme
from app.pitchsim.constants import PITCH_AXES


def test_weighted_overall_bounds():
    full = {a["key"]: 10 for a in PITCH_AXES}
    zero = {a["key"]: 0 for a in PITCH_AXES}
    assert evaluate.weighted_overall(PITCH_AXES, full) == 10.0
    assert evaluate.weighted_overall(PITCH_AXES, zero) == 0.0


def test_top_bottom_orders_strengths_and_weaknesses():
    axes = {a["key"]: 5 for a in PITCH_AXES}
    axes["marche"] = 1  # le plus faible
    axes["equipe"] = 9  # le plus fort
    strengths, weaknesses = evaluate.top_bottom(PITCH_AXES, axes, {}, n=2)
    assert strengths[0]["axis"] == "equipe"
    assert weaknesses[0]["axis"] == "marche"


def test_forme_completeness_from_answers():
    r = forme.score_forme(narration_text="bla", n_questions=2, n_answers=1, duration_min=5)
    assert r["scores"]["completude"] == 5.0


def test_forme_penalizes_fillers():
    clean = forme.score_forme(narration_text="un pitch clair et direct", n_questions=0, n_answers=0, duration_min=5)
    noisy = forme.score_forme(
        narration_text="euh du coup en fait voilà bah", n_questions=0, n_answers=0, duration_min=5
    )
    assert noisy["scores"]["fluidite"] < clean["scores"]["fluidite"]


def test_forme_structure_rewards_sections():
    text = "Le problème est réel, notre solution adresse le marché, le modèle de revenu, notre demande."
    r = forme.score_forme(narration_text=text, n_questions=0, n_answers=0, duration_min=5)
    assert r["scores"]["structure"] == 10.0
