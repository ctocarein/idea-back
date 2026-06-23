"""Prochaines actions — routage DÉTERMINISTE du porteur depuis ses axes faibles.

Le bilan devient *actionnable par construction* : on dérive, des dimensions sous le seuil,
1 à N actions priorisées (par faiblesse × poids catégorie), chacune pointant un LEVIER typé
(academy / pitchsim / document / mentor) défini DANS la grille. On émet des *intents* (type +
topic), pas des liens : les features les résolvent quand elles existent — jamais de lien mort.

Pur (stdlib) : pas d'IA, pas de DB, pas de fastapi → testable hors-ligne. C'est du code, pas
du LLM (même philosophie que l'agrégation : déterministe, rejouable).
"""

from __future__ import annotations

from collections.abc import Sequence

# Préfixe de CTA selon le type de levier (ton non culpabilisant : « renforce », pas « tu es nul »).
_CTA = {
    "academy": "Apprends",
    "pitchsim": "Entraîne-toi",
    "document": "Apporte des preuves",
    "mentor": "Fais-toi accompagner",
}


def derive_next_actions(
    grid_axes: Sequence[dict],
    scores: dict[str, int],
    category_weights: dict[str, dict[str, float]],
    category: str,
    *,
    scale_max: int = 10,
    strong_threshold: int = 8,
    max_actions: int = 3,
) -> list[dict]:
    # Candidats : dimensions NON fortes (< strong_threshold) ayant un levier défini.
    overrides = category_weights.get(category, {})
    ranked: list[tuple[float, dict, int]] = []
    for axis in grid_axes:
        score = int(scores.get(axis["key"], 0))
        lever = axis.get("lever")
        if score >= strong_threshold or not lever:
            continue
        weight = float(overrides.get(axis["key"], 1.0))
        # Priorité = faiblesse × poids catégorie : un axe bas ET lourd pour le secteur prime.
        priority = (scale_max - score) * weight
        ranked.append((priority, axis, score))

    ranked.sort(key=lambda t: t[0], reverse=True)

    actions: list[dict] = []
    for index, (_priority, axis, score) in enumerate(ranked[:max_actions]):
        lever = axis["lever"]
        ltype = lever.get("type", "academy")
        actions.append(
            {
                "key": axis["key"],
                "code": axis.get("code", ""),
                "dimension": axis["label"],
                "score": score,
                "severity": "faible" if score < 5 else "moyen",
                "lever_type": ltype,
                "topic": lever.get("topic"),
                "label": f"{_CTA.get(ltype, 'Travaille')} : {axis['label'].lower()}",
                "primary": index == 0,
            }
        )
    return actions
