"""Post-mortem — logique pure : niveau gamifié + plan d'entraînement déterministe.

Le plan route chaque faiblesse vers une destination (Academy / preuves / mentor / nouvelle
session / opportunités) — même esprit que `next_actions` du diagnostic. Réutilisable et testable.
"""

from __future__ import annotations

# Niveaux gamifiés (sur /100) — cf. UX §8.
_LEVELS = [
    (0, "Novice", "🌱"),
    (40, "Apprenti", "🌿"),
    (55, "Pitcheur", "🌳"),
    (70, "Orateur", "🏆"),
    (85, "Maître du Pitch", "👑"),
]

# Routage d'une faiblesse (axe Fond) → action concrète.
_AXIS_PLAN: dict[str, dict] = {
    "clarte_probleme": {"type": "academy", "topic": "probleme", "label": "Revois comment poser le problème"},
    "marche": {"type": "academy", "topic": "marche", "label": "Travaille ton dimensionnement de marché"},
    "business_model": {"type": "academy", "topic": "modele_economique", "label": "Clarifie ton modèle économique"},
    "solution": {"type": "academy", "topic": "solution", "label": "Renforce la différenciation de ta solution"},
    "traction": {"type": "document", "label": "Apporte des preuves de traction"},
    "equipe": {"type": "mentor", "label": "Fais-toi accompagner sur la crédibilité de l'équipe"},
    "gestion_questions": {"type": "pitchsim", "label": "Rejoue une session pour muscler tes réponses"},
    "resilience": {"type": "pitchsim", "label": "Entraîne-toi sous pression (mode Contrarian)"},
}


def level_for(global_100: float) -> dict:
    chosen = _LEVELS[0]
    level_index = 1
    for i, band in enumerate(_LEVELS):
        if global_100 >= band[0]:
            chosen = band
            level_index = i + 1
    return {"level": level_index, "title": chosen[1], "badge": chosen[2]}


def training_plan(weaknesses: list[dict]) -> list[dict]:
    plan: list[dict] = []
    for w in weaknesses:
        item = _AXIS_PLAN.get(w.get("axis", ""))
        if item is not None:
            plan.append(item)
    # Toujours : l'orientation vers les opportunités (la « visibilité »).
    plan.append({"type": "opportunity", "label": "Consulte les opportunités correspondant à ton niveau"})
    return plan
