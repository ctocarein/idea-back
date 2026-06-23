"""Ensemble & incertitude — N passes → consensus robuste + signal de confiance.

Un seul appel LLM peut halluciner un axe. On note donc CHAQUE axe sur **N passes
indépendantes** (idéalement N≥3) et on prend :
  - la **médiane** par axe → consensus robuste (insensible à 1 passe aberrante),
  - l'**étendue** (max−min) par axe → mesure d'incertitude.

Un axe dont les passes divergent fortement est **incertain** : le score s'auto-déclare
peu fiable et **appelle l'humain** (route vers la revue analyste) au lieu de mentir avec
assurance. Module PUR (stdlib) : testable hors-ligne, sans IA ni DB.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from statistics import median


@dataclass(frozen=True)
class EnsembleThresholds:
    # Un axe est "incertain" si l'étendue de ses passes dépasse `axis_spread_tolerance`.
    axis_spread_tolerance: int = 20  # points 0-100
    # Confiance globale plancher sous laquelle on route systématiquement vers l'humain.
    min_confidence: float = 0.60
    # Nombre d'axes incertains tolérés avant de déclencher la revue.
    max_uncertain_axes: int = 0


@dataclass
class ConsensusResult:
    axes: dict[str, int]  # médiane par axe (le score retenu)
    per_axis_spread: dict[str, int]  # étendue (max−min) par axe
    mean_spread: float
    uncertain_axes: list[str]
    confidence: float  # 0..1 (1 = passes parfaitement concordantes)
    n_passes: int
    needs_human_review: bool
    reasons: list[str] = field(default_factory=list)


def _confidence_from_spread(mean_spread: float) -> float:
    # Mappe l'étendue moyenne (0..100) en confiance (1..0). 0 pt → 1.0 ; 50 pts → 0.0.
    return round(max(0.0, min(1.0, 1.0 - mean_spread / 50.0)), 3)


def consensus(
    passes: Sequence[dict[str, int]],
    axis_keys: Sequence[str],
    thresholds: EnsembleThresholds | None = None,
) -> ConsensusResult:
    # passes = liste de jeux d'axes (une entrée par passe LLM). Chacune couvre axis_keys.
    if not passes:
        raise ValueError("Au moins une passe est requise.")
    thresholds = thresholds or EnsembleThresholds()

    axes: dict[str, int] = {}
    spread: dict[str, int] = {}
    uncertain: list[str] = []

    for key in axis_keys:
        values = [int(p[key]) for p in passes]
        axes[key] = round(median(values))
        rng = max(values) - min(values)
        spread[key] = rng
        if rng > thresholds.axis_spread_tolerance:
            uncertain.append(key)

    mean_spread = round(sum(spread.values()) / len(spread), 2) if spread else 0.0
    confidence = _confidence_from_spread(mean_spread)

    reasons: list[str] = []
    if len(uncertain) > thresholds.max_uncertain_axes:
        reasons.append(f"{len(uncertain)} axe(s) incertain(s) : {', '.join(uncertain)}")
    if confidence < thresholds.min_confidence:
        reasons.append(f"confiance {confidence} < {thresholds.min_confidence}")
    if len(passes) < 3:
        reasons.append(f"seulement {len(passes)} passe(s) (N≥3 recommandé)")

    needs_review = bool(reasons)

    return ConsensusResult(
        axes=axes,
        per_axis_spread=spread,
        mean_spread=mean_spread,
        uncertain_axes=uncertain,
        confidence=confidence,
        n_passes=len(passes),
        needs_human_review=needs_review,
        reasons=reasons,
    )
