"""Moteur de scoring — fonctions PURES, pilotées par une grille passée en argument.

Version-correct : un score est agrégé/validé selon la grille EXACTE qui l'a produit
(`grid_version`, `scale_max`). Aucune dépendance DB/IA. Générique sur l'échelle (v1 /100,
v2 /10) et le groupement (`pillar` en v2, `lens` en v1 — fallback).
"""

from __future__ import annotations

from app.core.errors import BusinessRuleError

DEFAULT_WEIGHT = 1.0
DEFAULT_SCALE_MAX = 10


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
    # Vue porteur : moyenne simple des dimensions de chaque pilier.
    groups: dict[str, list[int]] = {}
    for axis in grid_axes:
        groups.setdefault(_group_of(axis), []).append(int(axes.get(axis["key"], 0)))
    return {key: round(sum(vals) / len(vals)) for key, vals in groups.items() if vals}


def weights_for_category(
    grid_axes: list[dict],
    category_weights: dict[str, dict[str, float]],
    category: str,
) -> dict[str, float]:
    overrides = category_weights.get(category, {})
    return {key: float(overrides.get(key, DEFAULT_WEIGHT)) for key in axis_keys(grid_axes)}


def weighted_overall(
    grid_axes: list[dict],
    category_weights: dict[str, dict[str, float]],
    category: str,
    axes: dict[str, int],
) -> int:
    # Score global = moyenne PONDÉRÉE des dimensions selon la catégorie.
    weights = weights_for_category(grid_axes, category_weights, category)
    total_w = sum(weights.values())
    if total_w == 0:
        return 0
    weighted = sum(int(axes.get(k, 0)) * weights[k] for k in weights)
    return round(weighted / total_w)
