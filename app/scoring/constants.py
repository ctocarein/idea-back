"""Grille Radar v2 — 4 piliers × 3 dimensions = 12 dimensions (D1-D12), notées /10.

Cette révision de préproduction fige la structure technique afin que chaque score reste
rejouable. Son activation en production reste soumise à la calibration métier documentée.

Le moteur (`engine.py`) est piloté par la grille : adopter v2 = cette donnée + un seed.
"""

from __future__ import annotations

GRID_VERSION_V2 = "radar-v2.0.0-preprod.1"
SCALE_MAX = 10

# Niveaux de maturité globaux — 6 paliers sur le pourcentage normalisé /100.
# Utilisés dans GridOut, les rapports et le front (badge de maturité).
MATURITY_LEVELS: list[dict] = [
    {
        "key": "idee_brute",
        "label": "Idée brute",
        "min": 0,
        "max": 25,
        "description": "Le projet est encore très flou — travaillons les fondamentaux.",
        "tone": "fragile",
    },
    {
        "key": "a_structurer",
        "label": "Projet à structurer",
        "min": 26,
        "max": 45,
        "description": "Le potentiel existe, mais les bases sont à renforcer.",
        "tone": "watch",
    },
    {
        "key": "prometteur",
        "label": "Projet prometteur",
        "min": 46,
        "max": 60,
        "description": "Le projet commence à être lisible — tu es sur la bonne voie.",
        "tone": "watch",
    },
    {
        "key": "pre_viable",
        "label": "Projet pré-viable",
        "min": 61,
        "max": 75,
        "description": "Le projet peut être testé sérieusement.",
        "tone": "good",
    },
    {
        "key": "business_ready",
        "label": "Business Ready",
        "min": 76,
        "max": 85,
        "description": "Prêt à rencontrer des partenaires, incubateurs ou premiers clients.",
        "tone": "strong",
    },
    {
        "key": "investor_ready",
        "label": "Investor Ready",
        "min": 86,
        "max": 100,
        "description": "Suffisamment structuré pour des financeurs ou institutions.",
        "tone": "strong",
    },
]


def get_maturity_level(overall_pct: int) -> dict:
    """Retourne le niveau de maturité correspondant au score global /100."""
    for level in MATURITY_LEVELS:
        if level["min"] <= overall_pct <= level["max"]:
            return level
    return MATURITY_LEVELS[-1]


# Piliers (vue porteur) — chaque pilier a sa question directrice.
PILLARS: list[dict[str, str]] = [
    {
        "key": "sens",
        "label": "Sens du projet",
        "question": "Le projet répond-il à un vrai problème avec une solution pertinente ?",
    },
    {"key": "viabilite", "label": "Viabilité", "question": "Le projet peut-il tenir économiquement ?"},
    {"key": "scalabilite", "label": "Scalabilité", "question": "Le projet peut-il grandir sans se casser ?"},
    {"key": "execution", "label": "Exécution", "question": "L'équipe peut-elle exécuter et livrer ?"},
]


def _bands(*labels: str) -> list[dict]:
    # 4 paliers contigus couvrant 0-10 : 0-3 / 4-6 / 7-8 / 9-10 (bornes max exclusives).
    edges = [0, 4, 7, 9, 10]
    return [{"min": edges[i], "max": edges[i + 1], "label": labels[i]} for i in range(4)]


# 12 dimensions ancrées. `key` = d1..d12 (clé technique) ; `code` = D1..D12 (affichage).
AXES: list[dict] = [
    {
        "key": "d1",
        "code": "D1",
        "label": "Problème",
        "pillar": "sens",
        "central_question": "Le problème est-il réel, intense, fréquent, et conscient ?",
        "anchors": _bands(
            "Supposé, rare ou non prouvé",
            "Réel mais ponctuel / peu conscient",
            "Réel, fréquent, cible claire",
            "Douleur aiguë, fréquente, reconnue",
        ),
        "guiding_questions": [
            "Qui vit ce problème, à quelle fréquence ?",
            "Quelle preuve qu'il est ressenti (pas supposé) ?",
        ],
    },
    {
        "key": "d2",
        "code": "D2",
        "label": "Solution",
        "pillar": "sens",
        "central_question": "La solution résout-elle le problème de façon crédible et faisable ?",
        "anchors": _bands(
            "Floue ou non faisable",
            "Plausible, faisabilité non démontrée",
            "Crédible et faisable",
            "Éprouvée, adéquation claire",
        ),
        "guiding_questions": [
            "Comment résout-elle concrètement le problème ?",
            "Est-elle techniquement/opérationnellement faisable ?",
        ],
    },
    {
        "key": "d3",
        "code": "D3",
        "label": "Proposition de valeur",
        "pillar": "sens",
        "central_question": "La promesse est-elle claire, différenciante et mémorisable ?",
        "anchors": _bands(
            "Confuse ou indifférenciée",
            "Claire mais peu différenciante",
            "Claire et différenciante",
            "Nette, différenciante, mémorable",
        ),
        "guiding_questions": [
            "Quelle promesse unique en une phrase ?",
            "En quoi diffère-t-elle des alternatives ?",
        ],
    },
    {
        "key": "d4",
        "code": "D4",
        "label": "Marché",
        "pillar": "viabilite",
        "central_question": "Le marché est-il assez grand, en croissance, et accessible ?",
        "anchors": _bands(
            "Indéfini ou trop étroit",
            "Identifié, accès difficile / stagnant",
            "Significatif, en croissance, accessible",
            "Grand, en croissance, accès prouvé",
        ),
        "guiding_questions": [
            "Taille et croissance du marché cible ?",
            "Le segment initial est-il accessible ?",
        ],
    },
    {
        "key": "d5",
        "code": "D5",
        "label": "Concurrence & Benchmark",
        "pillar": "viabilite",
        "central_question": "Le paysage concurrentiel est-il connu et l'avantage est-il défendable ?",
        "anchors": _bands(
            "Ignorée / avantage inexistant",
            "Partiellement connue, avantage fragile",
            "Maîtrisée, avantage réel",
            "Cartographiée, avantage défendable",
        ),
        "guiding_questions": [
            "Qui sont les concurrents directs/indirects ?",
            "Quel avantage défendable (barrière) ?",
        ],
    },
    {
        "key": "d6",
        "code": "D6",
        "label": "Modèle économique",
        "pillar": "viabilite",
        "central_question": "Les revenus sont-ils crédibles, récurrents, et la marge est-elle saine ?",
        "anchors": _bands(
            "Absent ou irréaliste",
            "Plausible, unit economics non prouvées",
            "Revenus crédibles, marge raisonnable",
            "Récurrents prouvés, marge saine",
        ),
        "guiding_questions": ["Comment et combien facture-t-il ?", "Marges et récurrence crédibles ?"],
    },
    {
        "key": "d7",
        "code": "D7",
        "label": "Traction & Preuves",
        "pillar": "scalabilite",
        "central_question": "Y a-t-il des signaux clients, des revenus, des témoignages ?",
        "anchors": _bands(
            "Aucune preuve (théorique)",
            "Signaux faibles (intérêt déclaré)",
            "Premiers clients/revenus ou usage réel",
            "Traction mesurable et croissante",
        ),
        "guiding_questions": [
            "Quels signaux réels (clients, revenus, usage, témoignages) ?",
            "Sont-ils mesurables et croissants ?",
        ],
    },
    {
        "key": "d8",
        "code": "D8",
        "label": "Potentiel de croissance",
        "pillar": "scalabilite",
        "central_question": "Le modèle peut-il scaler sans proportionner les coûts ?",
        "anchors": _bands(
            "Non scalable (coûts proportionnels)",
            "Scalabilité limitée / coûteuse",
            "Bon levier de scalabilité",
            "Forte scalabilité / effet réseau",
        ),
        "guiding_questions": [
            "Les coûts croissent-ils moins vite que les revenus ?",
            "Quels leviers (effet réseau, automatisation) ?",
        ],
    },
    {
        "key": "d9",
        "code": "D9",
        "label": "Stratégie Go-to-Market",
        "pillar": "scalabilite",
        "central_question": "Le plan d'acquisition client est-il clair, réaliste et financé ?",
        "anchors": _bands(
            "Aucun plan d'acquisition",
            "Vague ou non chiffré",
            "Clair et réaliste",
            "Chiffré, financé, amorcé",
        ),
        "guiding_questions": [
            "Par quels canaux acquérir les 1ers clients ?",
            "Coût d'acquisition connu et finançable ?",
        ],
    },
    {
        "key": "d10",
        "code": "D10",
        "label": "Équipe & Compétences",
        "pillar": "execution",
        "central_question": "Les fondateurs ont-ils la légitimité, la complémentarité et la résilience ?",
        "anchors": _bands(
            "Compétences clés manquantes",
            "Partielle / peu complémentaire",
            "Crédible et complémentaire",
            "Complète, légitime, éprouvée",
        ),
        "guiding_questions": [
            "Les compétences clés sont-elles couvertes ?",
            "Complémentarité et résilience dans la durée ?",
        ],
    },
    {
        "key": "d11",
        "code": "D11",
        "label": "Niveau d'avancement",
        "pillar": "execution",
        "central_question": "Où en est le projet ? Qu'est-ce qui est fait ? Qu'est-ce qui manque ?",
        "anchors": _bands(
            "Idée sur le papier",
            "Prototype / MVP en cours",
            "Produit lancé, premiers usages",
            "En marché avec traction établie",
        ),
        "guiding_questions": [
            "Qu'est-ce qui est réellement fait/lancé ?",
            "Qu'est-ce qui manque pour l'étape suivante ?",
        ],
    },
    {
        "key": "d12",
        "code": "D12",
        "label": "Risques & Freins",
        "pillar": "execution",
        "central_question": "Les risques majeurs sont-ils identifiés et un plan de mitigation existe-t-il ?",
        "anchors": _bands(
            "Ignorés ou niés",
            "Partiellement identifiés, sans plan",
            "Identifiés, mitigation amorcée",
            "Majeurs identifiés + plan crédible",
        ),
        "guiding_questions": [
            "Quels sont les 3 risques majeurs ?",
            "Existe-t-il un plan de mitigation par risque ?",
        ],
    },
]

AXIS_KEYS: list[str] = [axis["key"] for axis in AXES]

# Levier d'action par dimension : où router le porteur si la dimension est faible.
# DATA (réglable en atelier) → le routage reste déterministe et découplé des features
# (cf. `app/scoring/actions.py`). type ∈ {academy, pitchsim, document, mentor}.
_LEVERS: dict[str, dict[str, str]] = {
    "d1": {"type": "academy", "topic": "probleme"},
    "d2": {"type": "academy", "topic": "solution"},
    "d3": {"type": "pitchsim", "topic": "proposition_valeur"},
    "d4": {"type": "academy", "topic": "marche"},
    "d5": {"type": "academy", "topic": "concurrence"},
    "d6": {"type": "academy", "topic": "modele_economique"},
    "d7": {"type": "document", "topic": "preuves_traction"},
    "d8": {"type": "academy", "topic": "croissance"},
    "d9": {"type": "academy", "topic": "go_to_market"},
    "d10": {"type": "mentor", "topic": "equipe"},
    "d11": {"type": "academy", "topic": "avancement"},
    "d12": {"type": "academy", "topic": "risques"},
}
for _axis in AXES:
    _axis["lever"] = _LEVERS.get(_axis["key"])

# Pondération par catégorie : { catégorie: { dimKey: poids } }. Non listé = 1.0.
CATEGORY_WEIGHTS: dict[str, dict[str, float]] = {
    "fintech": {"d6": 1.5, "d12": 1.3, "d5": 1.2},
    "agritech": {"d7": 1.3, "d4": 1.2, "d9": 1.2},
    "edtech": {"d7": 1.3, "d3": 1.2, "d8": 1.2},
    "sante": {"d12": 1.4, "d10": 1.3, "d2": 1.2},
    "commerce": {"d6": 1.3, "d7": 1.2, "d9": 1.2},
}

# Agrégation et validation : `app/scoring/engine.py` (opère sur la grille passée, version-correcte).
