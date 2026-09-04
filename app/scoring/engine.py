"""Moteur de scoring — fonctions PURES, pilotées par une grille passée en argument.

Version-correct : un score est agrégé/validé selon la grille EXACTE qui l'a produit
(`grid_version`, `scale_max`). Aucune dépendance DB/IA. Générique sur l'échelle (v1 /100,
v2 /10) et le groupement (`pillar` en v2, `lens` en v1 — fallback).
"""

from __future__ import annotations

from app.core.errors import BusinessRuleError
from app.core.logging import get_logger

logger = get_logger("scoring.engine")

DEFAULT_WEIGHT = 1.0
DEFAULT_SCALE_MAX = 10
# Échelle canonique du score global (cf. SPEC_SCORING_INTEGRITY C3). Les dimensions
# restent notées /10 ; le global est un POURCENTAGE normalisé, pas une note /100.
OVERALL_SCALE = 100


def axis_keys(grid_axes: list[dict]) -> list[str]:
    return [axis["key"] for axis in grid_axes]


def _group_of(axis: dict) -> str:
    # Clé de groupement : pilier (v2) ou lentille (v1).
    return axis.get("pillar") or axis.get("lens") or "_"


def find_anchor(axis_def: dict, value: int) -> dict | None:
    # Palier d'ancre où tombe `value` (max exclusif, sauf le palier le plus haut, inclusif).
    bands = axis_def.get("anchors", [])
    if not bands:
        return None
    top_max = max(b["max"] for b in bands)
    for band in bands:
        if band["min"] <= value < band["max"]:
            return band
        if value == top_max and band["max"] == top_max:
            return band
    return None


def anchors_cover_range(axis_def: dict, scale_max: int = DEFAULT_SCALE_MAX) -> bool:
    # Intégrité : les ancres couvrent 0..scale_max de façon contiguë (ni trou ni recouvrement).
    bands = sorted(axis_def.get("anchors", []), key=lambda b: b["min"])
    if not bands or bands[0]["min"] != 0 or bands[-1]["max"] != scale_max:
        return False
    return all(bands[i]["max"] == bands[i + 1]["min"] for i in range(len(bands) - 1))


def validate_grid(grid_axes: list[dict], scale_max: int = DEFAULT_SCALE_MAX) -> None:
    # Vérifie qu'une grille est saine AVANT de l'activer (seed/admin).
    if not grid_axes:
        raise BusinessRuleError("Grille vide : aucune dimension.")
    for axis in grid_axes:
        if not anchors_cover_range(axis, scale_max):
            raise BusinessRuleError(f"Ancres de la dimension '{axis.get('key')}' ne couvrent pas 0-{scale_max}.")


def validate_axes(grid_axes: list[dict], axes: dict[str, int], scale_max: int = DEFAULT_SCALE_MAX) -> None:
    # Validation stricte d'un score : exactement les dimensions de la grille, bornées
    # 0..scale_max, chaque valeur dans un palier d'ancre.
    expected = set(axis_keys(grid_axes))
    got = set(axes)
    missing, extra = expected - got, got - expected
    if missing or extra:
        raise BusinessRuleError(
            "Dimensions du score non conformes à la grille.",
            details=sorted([f"-{k}" for k in missing] + [f"+{k}" for k in extra]),
        )
    by_key = {axis["key"]: axis for axis in grid_axes}
    for key, value in axes.items():
        if not (0 <= int(value) <= scale_max):
            raise BusinessRuleError(f"Dimension '{key}' hors bornes (0-{scale_max}).")
        if find_anchor(by_key[key], int(value)) is None:
            raise BusinessRuleError(f"Dimension '{key}' : valeur hors des ancres.")


def pillar_scores(grid_axes: list[dict], axes: dict[str, int]) -> dict[str, int]:
    """Vue porteur : moyenne SIMPLE des dimensions de chaque pilier, sur l'échelle de la grille.

    Divergence assumée (SPEC_SCORING_INTEGRITY C5) : **la moyenne des piliers ne
    reconstitue pas `weighted_overall`** dès que le secteur est calibré. Ce n'est pas
    une incohérence, c'est une différence de rôle — le pilier décrit un état (photo
    brute, lisible), le global sert la comparaison entre projets (donc pondéré).

    Verrouillé par `test_pillar_mean_differs_from_weighted_overall_on_calibrated_sector`.
    """
    groups: dict[str, list[int]] = {}
    for axis in grid_axes:
        groups.setdefault(_group_of(axis), []).append(int(axes.get(axis["key"], 0)))
    return {key: round(sum(vals) / len(vals)) for key, vals in groups.items() if vals}


def is_calibrated(category_weights: dict[str, dict[str, float]], category: str) -> bool:
    """Le secteur a-t-il une pondération calibrée dans CETTE grille ?

    Faux = toutes les dimensions comptent également. C'est une neutralité ASSUMÉE
    (SPEC_SCORING_INTEGRITY C2, option B), pas un oubli — mais elle doit être dite au
    porteur, d'où l'exposition du drapeau jusque dans le bilan.
    """
    return bool(category_weights.get(category))


def weights_for_category(
    grid_axes: list[dict],
    category_weights: dict[str, dict[str, float]],
    category: str,
) -> dict[str, float]:
    overrides = category_weights.get(category, {})
    if not overrides:
        # Le fallback neutre reste valide ; il cesse d'être SILENCIEUX. Un pic sur ce
        # warning signale une clé de poids morte (grille désalignée du vocabulaire
        # sectoriel), pas un secteur exotique.
        logger.warning("scoring_category_unweighted", category=category)
    return {key: float(overrides.get(key, DEFAULT_WEIGHT)) for key in axis_keys(grid_axes)}


def weighted_overall(
    grid_axes: list[dict],
    category_weights: dict[str, dict[str, float]],
    category: str,
    axes: dict[str, int],
    *,
    scale_max: int = DEFAULT_SCALE_MAX,
) -> int:
    """Score global NORMALISÉ 0..100 = moyenne pondérée des dimensions selon la catégorie.

    Échelle unique du système (SPEC_SCORING_INTEGRITY C3) : back, API et écran affichent
    ce nombre tel quel. Les paliers `MATURITY_LEVELS` sont définis dessus.

    Normalisation en fin de chaîne, sans arrondi intermédiaire : arrondir d'abord sur /10
    n'offrirait que 11 valeurs possibles pour 12 dimensions et écraserait les écarts entre
    projets — donc la comparabilité, qui est le produit.
    """
    weights = weights_for_category(grid_axes, category_weights, category)
    total_w = sum(weights.values())
    if total_w == 0 or scale_max <= 0:
        return 0
    weighted = sum(int(axes.get(k, 0)) * weights[k] for k in weights)
    return round((weighted / total_w) * (OVERALL_SCALE / scale_max))
