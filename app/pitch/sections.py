"""Structure canonique d'un pitch (V1.2 éditeur).

Chaque section a une clé stable, un titre, un indice (hint) et, quand c'est
pertinent, la dimension Workshop (`d1..d12`) dont la synthèse sert à amorcer le
contenu. `ask` est amorcée par les fiches de besoin plutôt qu'une dimension.
"""

from __future__ import annotations

PITCH_SECTIONS: list[dict] = [
    {"key": "hook", "title": "Accroche", "hint": "Une phrase qui résume ton projet et donne envie.", "dimension": None},
    {"key": "problem", "title": "Problème", "hint": "Le problème que tu résous, pour qui, et pourquoi il compte.", "dimension": "d1"},
    {"key": "solution", "title": "Solution", "hint": "Ce que tu proposes concrètement et en quoi ça résout le problème.", "dimension": "d2"},
    {"key": "value", "title": "Proposition de valeur", "hint": "Le bénéfice unique, mesurable, pour ton utilisateur.", "dimension": "d3"},
    {"key": "market", "title": "Marché", "hint": "La taille de l'opportunité (TAM/SAM/SOM) et pourquoi maintenant.", "dimension": "d4"},
    {"key": "business_model", "title": "Modèle économique", "hint": "Qui paie, combien, comment tu gagnes de l'argent.", "dimension": "d6"},
    {"key": "traction", "title": "Traction", "hint": "Tes preuves : clients, chiffres, jalons atteints.", "dimension": "d7"},
    {"key": "competition", "title": "Concurrence", "hint": "Les alternatives et ta différence défendable.", "dimension": "d5"},
    {"key": "team", "title": "Équipe", "hint": "Qui vous êtes et pourquoi vous êtes les bons pour ce projet.", "dimension": "d10"},
    {"key": "ask", "title": "Nos besoins", "hint": "Ce dont tu as besoin pour passer à l'échelle (talents, financement, partenaires).", "dimension": None},
]

SECTION_KEYS = [s["key"] for s in PITCH_SECTIONS]


def default_sections() -> list[dict]:
    """Sections vierges pour un nouveau pitch (contenu vide, à générer/éditer)."""
    return [{"key": s["key"], "title": s["title"], "content": ""} for s in PITCH_SECTIONS]
