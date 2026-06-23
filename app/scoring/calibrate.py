"""Harnais de calibration — exécutable hors-ligne (stdlib uniquement).

Charge le golden set, compare la prédiction enregistrée (`model_axes`) à la vérité experte
(`expert_axes`), calcule les métriques d'accord et SORT en code non nul si les seuils ne sont
pas tenus (porte de non-régression pour la CI).

    python -m app.scoring.calibrate                 # golden set par défaut
    python -m app.scoring.calibrate --golden <path> # autre jeu

À LLM-01 : remplacer `model_axes` (statique) par une régénération live du scorer LLM, pour
mesurer l'accord du MODÈLE COURANT et bloquer toute dérive de prompt/grille.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.scoring.calibration import CalibrationThresholds, evaluate
from app.scoring.constants import AXIS_KEYS

_DEFAULT_GOLDEN = Path(__file__).resolve().parents[2] / "calibration" / "golden_set.json"


def _validate_axes(label: str, case_id: str, axes: dict) -> None:
    # Garde-fou : chaque cas doit couvrir les 6 axes, bornés 0-100.
    missing = set(AXIS_KEYS) - set(axes)
    if missing:
        raise SystemExit(f"[{case_id}] {label} : axes manquants {sorted(missing)}")
    for key in AXIS_KEYS:
        value = axes[key]
        if not (0 <= int(value) <= 100):
            raise SystemExit(f"[{case_id}] {label} : axe '{key}' hors bornes (0-100)")


def run(golden_path: Path) -> int:
    data = json.loads(golden_path.read_text(encoding="utf-8"))
    cases_raw = data.get("cases", [])
    if not cases_raw:
        raise SystemExit("Golden set vide.")

    pairs: list[tuple[dict[str, int], dict[str, int]]] = []
    for case in cases_raw:
        _validate_axes("model_axes", case["id"], case["model_axes"])
        _validate_axes("expert_axes", case["id"], case["expert_axes"])
        pairs.append((case["model_axes"], case["expert_axes"]))

    report = evaluate(pairs, AXIS_KEYS, CalibrationThresholds())

    print(f"Calibration — grille {data.get('grid_version', '?')}")
    print(f"  cas: {report.n_cases} · axes/cas: {report.n_axes}")
    print(f"  MAE global: {report.overall_mae} pts")
    print(f"  accord à ±{CalibrationThresholds().tolerance}: {report.within_tolerance_rate:.0%}")
    print(f"  pire écart: {report.max_abs_error} pts · corrélation: {report.correlation}")
    print("  MAE par axe:")
    for axis, axis_mae in report.per_axis_mae.items():
        print(f"    - {axis:<12} {axis_mae}")
    print(f"  => {'PASS' if report.passed else 'FAIL'}")
    for failure in report.failures:
        print(f"     ✗ {failure}")
    return 0 if report.passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Harnais de calibration du scoring Radar.")
    parser.add_argument("--golden", type=Path, default=_DEFAULT_GOLDEN)
    args = parser.parse_args()
    return run(args.golden)


if __name__ == "__main__":
    sys.exit(main())
