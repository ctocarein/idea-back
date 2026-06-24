"""Agrégation du score Fond — pur, déterministe (à partir des axes notés par le LLM).

Le LLM note les axes (ancrés) ; l'agrégation (pondération, forces/faiblesses) est calculée
ici en clair → reproductible et auditable, comme pour le scoring Radar.
"""

from __future__ import annotations


def weighted_overall(rubric_axes: list[dict], axes: dict[str, int]) -> float:
    # Moyenne pondérée par les poids de la rubrique (qui somment à 1) → 0..10.
    total = sum(axes[a["key"]] * a["weight"] for a in rubric_axes if a["key"] in axes)
    return round(total, 1)


def top_bottom(
    rubric_axes: list[dict],
    axes: dict[str, int],
    justifications: dict[str, str],
    *,
    n: int = 3,
) -> tuple[list[dict], list[dict]]:
    # n meilleurs = forces, n moins bons = faiblesses (avec libellé + justification).
    labels = {a["key"]: a["label"] for a in rubric_axes}
    ordered = sorted(axes.items(), key=lambda kv: kv[1])

    def _item(key: str, score: int) -> dict:
        return {
            "axis": key,
            "label": labels.get(key, key),
            "score": score,
            "note": justifications.get(key, ""),
        }

    weaknesses = [_item(k, v) for k, v in ordered[:n]]
    strengths = [_item(k, v) for k, v in reversed(ordered[-n:])]
    return strengths, weaknesses
