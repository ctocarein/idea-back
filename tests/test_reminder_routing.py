"""Rappel J+7 — routage et conditions d'émission, sans DB ni SMTP.

Le point sensible n'est pas l'envoi : c'est de ne JAMAIS référencer une action non
routable. Dix dimensions sur douze pointent vers `academy`/`pitchsim`, modules retirés ;
un rappel les citant dirait « tu devais apprendre X » en renvoyant vers rien.
"""

from __future__ import annotations

import pytest

from app.core.email import reminder_message
from app.notifications.handlers import ROUTABLE_LEVERS, STRONG_THRESHOLD, _find_action
from app.scoring.actions import derive_next_actions
from app.scoring.constants import AXES, AXIS_KEYS, CATEGORY_WEIGHTS, SCALE_MAX


def _pick(actions: list[dict]) -> dict | None:
    # Reproduit la sélection de `_schedule_action_reminder` : premier levier routable
    # rencontré dans l'ordre de priorité du moteur.
    return next((a for a in actions if a.get("lever_type") in ROUTABLE_LEVERS), None)


def test_actions_expose_lever_type_flat_not_nested() -> None:
    """Le contrat réel de `derive_next_actions` : `lever_type` à plat, pas `lever.type`.

    La spec décrivait `action["lever"]["type"]` ; le code fait foi. Ce test fixe le contrat
    pour que la sélection du rappel ne se mette pas à filtrer sur une clé inexistante —
    ce qui se traduirait par « aucun rappel jamais », en silence.
    """
    actions = derive_next_actions(AXES, dict.fromkeys(AXIS_KEYS, 2), CATEGORY_WEIGHTS, "agro", scale_max=SCALE_MAX)
    assert actions
    for action in actions:
        assert "lever_type" in action
        assert "lever" not in action
        assert action["key"] in AXIS_KEYS


def test_weak_traction_routes_to_a_reminder() -> None:
    # D7 Traction porte le levier `document` : c'est un rappel légitime.
    scores = dict.fromkeys(AXIS_KEYS, 9)
    scores["d7"] = 1
    picked = _pick(derive_next_actions(AXES, scores, CATEGORY_WEIGHTS, "agro", scale_max=SCALE_MAX))
    assert picked is not None
    assert picked["key"] == "d7"
    assert picked["lever_type"] == "document"


def test_only_unroutable_levers_produces_no_reminder() -> None:
    """Un projet faible UNIQUEMENT sur des dimensions `academy` ne reçoit rien.

    Couverture partielle assumée : le silence vaut mieux qu'un renvoi vers un module
    retiré. C'est le comportement qui doit tenir tant que SPEC_LEVIERS_V2 n'a pas tranché.
    """
    scores = dict.fromkeys(AXIS_KEYS, 9)
    scores["d1"] = 0  # academy
    scores["d4"] = 0  # academy
    actions = derive_next_actions(AXES, scores, CATEGORY_WEIGHTS, "agro", scale_max=SCALE_MAX)
    assert actions, "des actions existent, mais aucune n'est routable"
    assert _pick(actions) is None


def test_no_actions_produces_no_reminder() -> None:
    # Projet fort partout → aucune action → aucun rappel.
    strong = dict.fromkeys(AXIS_KEYS, SCALE_MAX)
    assert derive_next_actions(AXES, strong, CATEGORY_WEIGHTS, "agro", scale_max=SCALE_MAX) == []


def test_strong_threshold_matches_the_action_engine() -> None:
    """Le seuil d'annulation doit être CELUI qui a produit l'action.

    S'ils divergent, on annule des rappels encore valides (seuil trop bas) ou on en envoie
    sur des actions déjà faites (seuil trop haut).
    """
    scores = dict.fromkeys(AXIS_KEYS, STRONG_THRESHOLD)
    assert derive_next_actions(AXES, scores, CATEGORY_WEIGHTS, "agro", scale_max=SCALE_MAX) == []
    below = dict.fromkeys(AXIS_KEYS, STRONG_THRESHOLD - 1)
    assert derive_next_actions(AXES, below, CATEGORY_WEIGHTS, "agro", scale_max=SCALE_MAX) != []


def test_find_action_by_axis_key() -> None:
    actions = [{"key": "d7", "label": "x"}, {"key": "d10", "label": "y"}]
    assert _find_action(actions, "d10")["label"] == "y"
    assert _find_action(actions, "d1") is None
    assert _find_action(None, "d7") is None


# --- Contenu du mail ------------------------------------------------------


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_reminder_mail_carries_both_issues_and_unsubscribe(lang: str) -> None:
    subject, body = reminder_message(
        name="Sophie",
        dimension="Traction & Preuves",
        action_label="Apporte des preuves : traction & preuves",
        report_id="r-1",
        unsubscribe_token="TOK",
        lang=lang,
    )
    assert "Traction" in subject
    # Deux issues, et les deux mènent au produit.
    assert "/dashboard/diagnostic" in body
    assert "/dashboard/bilan/r-1" in body
    # Le désabonnement est une obligation, pas une option.
    assert "unsubscribe?token=TOK" in body
    assert f"/{lang}/" in body


def test_reminder_mail_is_plain_text_and_not_marketing() -> None:
    _, body = reminder_message(
        name="Sophie",
        dimension="Équipe",
        action_label="Fais-toi accompagner : équipe & compétences",
        report_id="r-1",
        unsubscribe_token="T",
    )
    assert "<" not in body and ">" not in body  # texte brut, aucune balise
    # Le mail référence ce que le porteur a écrit, il ne vend rien.
    assert "Fais-toi accompagner" in body
    for banned in ("offre", "premium", "abonne-toi", "promotion", "-%"):
        assert banned not in body.lower()


def test_unknown_language_falls_back_to_french() -> None:
    subject, _ = reminder_message(
        name="X", dimension="D", action_label="A", report_id="r", unsubscribe_token="T", lang="de"
    )
    assert subject.startswith("Où en es-tu")
