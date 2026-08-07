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
    # Un axe est "incertain" si l'étendue de ses passes dépasse cette part de
    # l'échelle. Un seuil relatif évite de mélanger les grilles /10 et /100.
    axis_spread_tolerance_ratio: float = 0.20
    # Surcharge absolue, utile pour une grille calibrée ou un test ciblé.
    axis_spread_tolerance: float | None = None
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


def _validate_thresholds(thresholds: EnsembleThresholds) -> None:
    if not 0 <= thresholds.axis_spread_tolerance_ratio <= 1:
        raise ValueError("axis_spread_tolerance_ratio doit être compris entre 0 et 1.")
    if thresholds.axis_spread_tolerance is not None and thresholds.axis_spread_tolerance < 0:
        raise ValueError("axis_spread_tolerance doit être positif.")
    if not 0 <= thresholds.min_confidence <= 1:
        raise ValueError("min_confidence doit être compris entre 0 et 1.")


def _confidence_from_spread(mean_spread: float, scale_max: int) -> float:
    # Une divergence moyenne égale à la moitié de l'échelle donne une confiance
    # nulle. La formule reste ainsi identique pour une grille /10 ou /100.
    zero_confidence_spread = scale_max * 0.5
    return round(max(0.0, min(1.0, 1.0 - mean_spread / zero_confidence_spread)), 3)


def consensus(
    passes: Sequence[dict[str, int]],
    axis_keys: Sequence[str],
    thresholds: EnsembleThresholds | None = None,
    *,
    scale_max: int = 10,
) -> ConsensusResult:
    # passes = liste de jeux d'axes (une entrée par passe LLM). Chacune couvre axis_keys.
    if not passes:
        raise ValueError("Au moins une passe est requise.")
    if scale_max <= 0:
        raise ValueError("scale_max doit être strictement positif.")
    thresholds = thresholds or EnsembleThresholds()
    _validate_thresholds(thresholds)
    tolerance = (
        thresholds.axis_spread_tolerance
        if thresholds.axis_spread_tolerance is not None
        else scale_max * thresholds.axis_spread_tolerance_ratio
    )

    axes: dict[str, int] = {}
    spread: dict[str, int] = {}
    uncertain: list[str] = []

    for key in axis_keys:
        try:
            values = [int(p[key]) for p in passes]
        except KeyError as exc:
            raise ValueError(f"Dimension manquante dans une passe : {key}.") from exc
        if any(value < 0 or value > scale_max for value in values):
            raise ValueError(f"Dimension '{key}' hors bornes (0-{scale_max}).")
        axes[key] = round(median(values))
        rng = max(values) - min(values)
        spread[key] = rng
        if rng > tolerance:
            uncertain.append(key)

    mean_spread = round(sum(spread.values()) / len(spread), 2) if spread else 0.0
    confidence = _confidence_from_spread(mean_spread, scale_max)

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
