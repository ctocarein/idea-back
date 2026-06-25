"""Orchestrateur du « comité silencieux » — logique PURE (sans DB/HTTP/LLM).

C'est le cœur de risque de PITCH-06, isolé ici pour être prouvé d'abord (cf. SPEC §14.3) :
- la machine à **phases** + transitions ;
- la **prise de parole** en QA (ordre + passage du micro) ;
- les **micro-réactions** silencieuses pendant le pitch ;
- l'évolution de la **conviction** par agent ;
- la sélection d'un **angle de question varié** (déterministe par seed, anti-doublon).

Tout est déterministe et rejouable → testable sans réseau. Le *contenu* (LLM) viendra par-dessus.
"""

from __future__ import annotations

import hashlib
from enum import Enum

from app.core.errors import BusinessRuleError


class PitchPhase(str, Enum):
    BRIEFING = "briefing"
    PITCHING = "pitching"  # comité silencieux
    QA = "qa"  # questions ordonnées
    FREE_ROUND = "free_round"  # les agents se parlent
    DELIBERATING = "deliberating"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


# Transitions autorisées (aucune implicite ; saut illégal → 422).
PHASE_TRANSITIONS: dict[PitchPhase, list[PitchPhase]] = {
    PitchPhase.BRIEFING: [PitchPhase.PITCHING, PitchPhase.ABANDONED],
    PitchPhase.PITCHING: [PitchPhase.QA, PitchPhase.ABANDONED],
    PitchPhase.QA: [PitchPhase.FREE_ROUND, PitchPhase.ABANDONED],
    PitchPhase.FREE_ROUND: [PitchPhase.DELIBERATING, PitchPhase.ABANDONED],
    PitchPhase.DELIBERATING: [PitchPhase.COMPLETED],
    PitchPhase.COMPLETED: [],
    PitchPhase.ABANDONED: [],
}


def can_transition(current: PitchPhase, target: PitchPhase) -> bool:
    return target in PHASE_TRANSITIONS.get(current, [])


def assert_transition(current: PitchPhase, target: PitchPhase) -> None:
    if not can_transition(current, target):
        raise BusinessRuleError(f"Transition de phase illégale : {current.value} → {target.value}")


def _seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


# --- Pool d'angles par axe (placeholder v1 — varié dans le cadre de la pertinence) ---
ANGLE_POOL: dict[str, list[dict]] = {
    "clarte_probleme": [
        {"angle": "pour-qui", "q": "Pour qui exactement, et à quelle fréquence ce problème se pose-t-il ?"},
        {"angle": "cout-actuel", "q": "Que coûte ce problème aujourd'hui à ceux qui le vivent ?"},
    ],
    "solution": [
        {"angle": "differenciation", "q": "En quoi êtes-vous défendable si un grand groupe copie demain ?"},
        {"angle": "faisabilite", "q": "Qu'est-ce qui prouve que c'est faisable techniquement ?"},
    ],
    "marche": [
        {"angle": "source", "q": "Votre chiffre de marché, d'où vient-il ? Donnez-moi la source."},
        {"angle": "adressable", "q": "Quelle part est réellement atteignable, pas le TAM théorique ?"},
        {"angle": "saturation", "q": "Le marché est-il déjà saturé d'acteurs ?"},
    ],
    "business_model": [
        {"angle": "marge", "q": "Quelle est votre marge nette après tous les coûts ?"},
        {"angle": "acquisition", "q": "Combien coûte l'acquisition d'un client ?"},
        {"angle": "recurrence", "q": "Vos revenus sont-ils récurrents ou one-shot ?"},
    ],
    "traction": [
        {"angle": "preuves", "q": "Quelles preuves d'usage chiffrées avez-vous ?"},
        {"angle": "retention", "q": "Vos utilisateurs reviennent-ils ? Quelle rétention ?"},
    ],
    "equipe": [
        {"angle": "legitimite", "q": "Pourquoi votre équipe est-elle la bonne pour exécuter ça ?"},
        {"angle": "complementarite", "q": "Vos profils sont-ils complémentaires ?"},
    ],
    "gestion_questions": [{"angle": "precision", "q": "Répondez précisément à la question posée."}],
    "resilience": [{"angle": "calme", "q": "Reprenez calmement : quel est l'essentiel ?"}],
}

# Micro-réactions silencieuses possibles (envoyées au front).
REACTIONS = ("nod", "frown", "note", "glance", "impatient", "none")


def micro_reactions(personas: list[dict], weak_axes: list[str]) -> list[dict]:
    """Pour chaque agent : un signal silencieux selon son obsession (jamais de parole)."""
    weak = set(weak_axes)
    out: list[dict] = []
    for p in personas:
        if p["obsession"] in weak:
            reaction = "note" if _seed(p["name"], p["obsession"]) % 2 else "frown"
        else:
            reaction = "nod"
        out.append({"agent": p["name"], "reaction": reaction})
    return out


def update_convictions(convictions: dict[str, int], personas: list[dict], weak_axes: list[str]) -> dict[str, int]:
    """Conviction par agent (−2..+2) : baisse si son obsession est faible, monte sinon."""
    weak = set(weak_axes)
    updated = dict(convictions)
    for p in personas:
        delta = -1 if p["obsession"] in weak else 1
        updated[p["name"]] = max(-2, min(2, updated.get(p["name"], 0) + delta))
    return updated


def qa_order(personas: list[dict]) -> list[str]:
    # Ordre de parole = ordre du comité (l'expert métier est inséré à sa place).
    return [p["name"] for p in personas]


def free_round(personas: list[dict], convictions: dict[str, int]) -> list[dict]:
    """Tour libre : les agents se parlent (déterministe, d'après les convictions).

    Le plus sceptique exprime un doute ; le plus convaincu rebondit. Donne le *débat* sans LLM.
    """
    if not personas:
        return []
    skeptic = min(personas, key=lambda p: convictions.get(p["name"], 0))
    champion = max(personas, key=lambda p: convictions.get(p["name"], 0))
    out = [
        {
            "actor": skeptic["name"],
            "content": f"{skeptic['name']} : Je reste sceptique sur {skeptic['obsession'].replace('_', ' ')}.",
        }
    ]
    if champion["name"] != skeptic["name"]:
        out.append(
            {
                "actor": champion["name"],
                "content": f"{champion['name']} : Sa remarque est dure mais juste — j'aimerais entendre votre réponse.",
            }
        )
    return out


def next_speaker(order: list[str], index: int) -> str | None:
    return order[index] if 0 <= index < len(order) else None


def pick_angle(axis: str, asked_angles: list[str], seed_key: str, history: list[str] | None = None) -> dict | None:
    """Choisit un angle sur cet axe (varié, déterministe).

    `asked_angles` = déjà posés DANS la session (anti-doublon dur). `history` = angles posés aux
    sessions PRÉCÉDENTES (filtre SOUPLE inter-sessions : évité si possible, ignoré s'il épuise tout).
    None seulement si tous les angles intra-session sont épuisés.
    """
    pool = ANGLE_POOL.get(axis, [])
    intra = set(asked_angles)
    hist = set(history or [])
    fresh = [a for a in pool if a["angle"] not in intra and a["angle"] not in hist]
    if not fresh:  # l'historique inter-sessions a tout couvert → on le relâche
        fresh = [a for a in pool if a["angle"] not in intra]
    if not fresh:
        return None
    return fresh[_seed(seed_key, axis) % len(fresh)]


def next_question(
    persona: dict,
    asked_angles_by_axis: dict[str, list[str]],
    seed_key: str,
    history_by_axis: dict[str, list[str]] | None = None,
) -> dict | None:
    """Prochaine question d'un agent sur SON obsession (angle varié, anti-doublon intra + inter)."""
    axis = persona["obsession"]
    chosen = pick_angle(
        axis,
        asked_angles_by_axis.get(axis, []),
        seed_key,
        history=(history_by_axis or {}).get(axis),
    )
    if chosen is None:
        return None
    return {
        "agent": persona["name"],
        "axis": axis,
        "angle": chosen["angle"],
        "content": f"{persona['name']} : {chosen['q']}",
    }
