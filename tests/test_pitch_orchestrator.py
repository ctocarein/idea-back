"""Orchestrateur « comité silencieux » — pur, déterministe, sans DB ni LLM."""

from __future__ import annotations

from app.pitchsim import orchestrator as orch
from app.pitchsim.constants import committee
from app.pitchsim.orchestrator import PitchPhase

INCUB = committee("incubateur")["personas"]


# --- Machine à phases ---


def test_legal_phase_path():
    path = [
        (PitchPhase.BRIEFING, PitchPhase.PITCHING),
        (PitchPhase.PITCHING, PitchPhase.QA),
        (PitchPhase.QA, PitchPhase.FREE_ROUND),
        (PitchPhase.FREE_ROUND, PitchPhase.DELIBERATING),
        (PitchPhase.DELIBERATING, PitchPhase.COMPLETED),
    ]
    for cur, tgt in path:
        assert orch.can_transition(cur, tgt)


def test_illegal_transition_rejected():
    assert not orch.can_transition(PitchPhase.PITCHING, PitchPhase.COMPLETED)
    assert not orch.can_transition(PitchPhase.COMPLETED, PitchPhase.PITCHING)


def test_assert_transition_raises_on_illegal():
    import pytest

    from app.core.errors import BusinessRuleError

    with pytest.raises(BusinessRuleError):
        orch.assert_transition(PitchPhase.BRIEFING, PitchPhase.DELIBERATING)


def test_abandon_from_any_active_phase():
    for ph in (PitchPhase.BRIEFING, PitchPhase.PITCHING, PitchPhase.QA, PitchPhase.FREE_ROUND):
        assert orch.can_transition(ph, PitchPhase.ABANDONED)


# --- Prise de parole ---


def test_qa_order_follows_committee():
    order = orch.qa_order(INCUB)
    assert order == [p["name"] for p in INCUB]
    assert orch.next_speaker(order, 0) == INCUB[0]["name"]
    assert orch.next_speaker(order, len(order)) is None  # plus personne


# --- Micro-réactions (silencieuses) ---


def test_micro_reactions_one_per_agent_and_silent():
    reactions = orch.micro_reactions(INCUB, ["marche"])
    assert len(reactions) == len(INCUB)
    assert all(r["reaction"] in orch.REACTIONS for r in reactions)
    # M. Morel obsède le marché → réaction négative (frown/note), pas un hochement.
    morel = next(r for r in reactions if r["agent"] == "M. Morel")
    assert morel["reaction"] in ("frown", "note")


# --- Conviction ---


def test_conviction_drops_on_weak_obsession_and_clamps():
    conv: dict[str, int] = {}
    for _ in range(5):  # répété → doit se borner à -2
        conv = orch.update_convictions(conv, INCUB, ["marche"])
    assert conv["M. Morel"] == -2  # obsession faible à répétition
    assert conv["Mme Diallo"] == 2  # obsession non touchée → monte et se borne à +2


# --- Angles variés + anti-doublon ---


def test_pick_angle_avoids_repetition():
    first = orch.pick_angle("marche", [], "s")
    assert first is not None
    # Une fois posé, on ne le repropose pas.
    second = orch.pick_angle("marche", [first["angle"]], "s")
    assert second is not None and second["angle"] != first["angle"]


def test_pick_angle_exhausted_returns_none():
    all_angles = [a["angle"] for a in orch.ANGLE_POOL["resilience"]]
    assert orch.pick_angle("resilience", all_angles, "s") is None


def test_next_question_targets_obsession_with_varied_angle():
    morel = next(p for p in INCUB if p["name"] == "M. Morel")
    q1 = orch.next_question(morel, {}, "s")
    assert q1 is not None and q1["axis"] == "marche"
    # Angle déjà posé → question suivante sur un autre angle.
    q2 = orch.next_question(morel, {"marche": [q1["angle"]]}, "s")
    assert q2 is not None and q2["angle"] != q1["angle"]


def test_next_question_none_when_all_angles_used():
    diallo = next(p for p in INCUB if p["name"] == "Mme Diallo")  # obsession equipe
    used = {"equipe": [a["angle"] for a in orch.ANGLE_POOL["equipe"]]}
    assert orch.next_question(diallo, used, "s") is None


def test_free_round_skeptic_speaks_first():
    convictions = {"M. Morel": -2, "Mme Diallo": 2}  # Morel le plus sceptique, Diallo la plus convaincue
    out = orch.free_round(INCUB, convictions)
    assert out and out[0]["actor"] == "M. Morel"
    assert any(p["name"] == "Mme Diallo" for p in INCUB)  # garde-fou données
    assert len(out) >= 2  # le sceptique + un rebond


def test_pick_angle_avoids_history_but_falls_back():
    # L'historique inter-sessions est évité si possible…
    res = orch.pick_angle("marche", [], "s", history=["source"])
    assert res is not None and res["angle"] != "source"
    # …mais relâché s'il couvre tout (l'agent n'est jamais muet).
    everything = [a["angle"] for a in orch.ANGLE_POOL["marche"]]
    assert orch.pick_angle("marche", [], "s", history=everything) is not None
