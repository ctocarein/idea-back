"""Calibration du scoring — métriques d'accord IA ↔ expert (la PREUVE de robustesse).

Sans dépendance externe (stdlib uniquement) : utilisable en CI/harnais hors-ligne.
On mesure à quel point les scores produits (modèle, ou un humain) collent à une vérité
terrain experte sur un golden set. Tout changement de prompt/grille qui dégrade ces
métriques doit être bloqué (non-régression).

Métriques :
  - MAE global et par axe (écart absolu moyen, en points 0-100),
  - taux d'accord à tolérance (|pred - expert| <= tolerance),
  - écart absolu maximum (le pire cas),
  - corrélation (accord de forme, pas seulement de niveau).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from statistics import mean


@dataclass(frozen=True)
class CalibrationThresholds:
    # Seuils de passage. Conservateurs par défaut ; à durcir avec la maturité de la grille.
    max_overall_mae: float = 10.0  # écart moyen acceptable, en points
    min_within_tolerance_rate: float = 0.80  # part des axes notés "d'accord"
    tolerance: int = 15  # un axe est "d'accord" si l'écart <= 15 pts
    max_axis_mae: float = 18.0  # aucun axe ne doit dériver au-delà


@dataclass
class CalibrationReport:
    n_cases: int
    n_axes: int
    overall_mae: float
    per_axis_mae: dict[str, float]
    within_tolerance_rate: float
    max_abs_error: int
    correlation: float | None
    passed: bool
    failures: list[str] = field(default_factory=list)


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    # Corrélation de Pearson, sans dépendance. None si l'un des vecteurs est constant.
    n = len(xs)
    if n < 2:
        return None
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def evaluate(
    cases: Sequence[tuple[dict[str, int], dict[str, int]]],
    axis_keys: Sequence[str],
    thresholds: CalibrationThresholds | None = None,
) -> CalibrationReport:
    # cases = liste de (axes_prédits, axes_experts). Les deux couvrent `axis_keys`.
    thresholds = thresholds or CalibrationThresholds()
    per_axis_err: dict[str, list[int]] = {k: [] for k in axis_keys}
    all_pred: list[float] = []
    all_expert: list[float] = []

    for predicted, expert in cases:
        for key in axis_keys:
            err = abs(int(predicted[key]) - int(expert[key]))
            per_axis_err[key].append(err)
            all_pred.append(int(predicted[key]))
            all_expert.append(int(expert[key]))

    flat_errors = [e for errs in per_axis_err.values() for e in errs]
    overall_mae = round(mean(flat_errors), 2) if flat_errors else 0.0
    per_axis_mae = {k: round(mean(v), 2) for k, v in per_axis_err.items() if v}
    within_rate = round(mean([1 if e <= thresholds.tolerance else 0 for e in flat_errors]), 3) if flat_errors else 1.0
    max_abs = max(flat_errors) if flat_errors else 0
    correlation = _pearson(all_pred, all_expert)
    if correlation is not None:
        correlation = round(correlation, 3)

    # Évaluation des seuils → liste des échecs (vide = passé).
    failures: list[str] = []
    if overall_mae > thresholds.max_overall_mae:
        failures.append(f"MAE global {overall_mae} > {thresholds.max_overall_mae}")
    if within_rate < thresholds.min_within_tolerance_rate:
        failures.append(f"accord à ±{thresholds.tolerance} {within_rate} < {thresholds.min_within_tolerance_rate}")
    for axis, axis_mae in per_axis_mae.items():
        if axis_mae > thresholds.max_axis_mae:
            failures.append(f"axe '{axis}' MAE {axis_mae} > {thresholds.max_axis_mae}")

    return CalibrationReport(
        n_cases=len(cases),
        n_axes=len(axis_keys),
        overall_mae=overall_mae,
        per_axis_mae=per_axis_mae,
        within_tolerance_rate=within_rate,
        max_abs_error=max_abs,
        correlation=correlation,
        passed=not failures,
        failures=failures,
    )
