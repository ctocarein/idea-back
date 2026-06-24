"""Post-mortem — niveau gamifié, plan d'entraînement, rendu HTML (purs)."""

from __future__ import annotations

from app.pitchsim import postmortem
from app.pitchsim.pdf import render_postmortem_html
from app.pitchsim.schemas import PostMortemOut


def test_level_thresholds():
    assert postmortem.level_for(10)["title"] == "Novice"
    assert postmortem.level_for(60)["title"] == "Pitcheur"
    assert postmortem.level_for(90)["title"] == "Maître du Pitch"
    assert postmortem.level_for(90)["level"] == 5


def test_training_plan_routes_weaknesses_and_adds_opportunity():
    plan = postmortem.training_plan([{"axis": "marche"}, {"axis": "equipe"}, {"axis": "gestion_questions"}])
    types = [p["type"] for p in plan]
    assert "academy" in types  # marché → leçon
    assert "mentor" in types  # équipe → mentor
    assert "pitchsim" in types  # gestion des questions → rejouer
    assert plan[-1]["type"] == "opportunity"  # toujours l'orientation finale


def test_training_plan_always_has_opportunity_even_without_weaknesses():
    plan = postmortem.training_plan([])
    assert len(plan) == 1 and plan[0]["type"] == "opportunity"


def _sample() -> PostMortemOut:
    return PostMortemOut(
        committee_key="incubateur",
        scores={
            "global": 5.1,
            "fond": 5.0,
            "forme": 5.5,
            "global_100": 51,
            "level": postmortem.level_for(51),
        },
        radar=[
            {"axis": "marche", "label": "Marché", "score": 5, "kind": "fond"},
            {"axis": "posture_regard", "label": "Posture & regard", "score": None, "kind": "bio"},
        ],
        timeline=[],
        strengths=[{"axis": "solution", "label": "Solution", "score": 7, "note": ""}],
        weaknesses=[{"axis": "marche", "label": "Marché", "score": 3, "note": ""}],
        progression=[{"global": 4.0}, {"global": 5.1}],
        training_plan=postmortem.training_plan([{"axis": "marche"}]),
    )


def test_render_html_contains_key_sections():
    html = render_postmortem_html(_sample())
    assert "51/100" in html
    assert "Apprenti" in html  # niveau pour 51
    assert "Marché" in html
    assert "Mode Caméra" in html  # axe biométrique non noté
    assert "Plan d'entraînement" in html
