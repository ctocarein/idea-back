"""Banc d'essai du TAUX D'EXCEPTION — mesure la charge de revue humaine du Radar.

Thèse à prouver (PROJET_IDEAXION_V2 §19/§20) : une institution paie parce qu'Ideaxion
réduit le temps de pré-évaluation. Hypothèse porteuse (§20.3) : « moins de 10 à 20 % des
dimensions nécessitent une revue humaine ». Ce banc la MESURE au lieu de la supposer.

Méthode (reproduit le chemin de prod, sans DB) : pour chaque récit du corpus, on note les
12 dimensions sur N passes LLM indépendantes (angle d'analyse variable), puis `consensus()`
transforme la divergence inter-passes en signal d'incertitude — exactement ce qui route un
score vers la revue analyste en production (`needs_review`).

    uv run python -m app.scoring.exception_bench                    # provider de la config, temp de la config
    uv run python -m app.scoring.exception_bench --mock             # câblage seulement (déterministe, PAS un signal)
    uv run python -m app.scoring.exception_bench --sweep 0.2,0.7,1.0  # sensibilité à la température
    uv run python -m app.scoring.exception_bench --out calibration/out/exceptions.json

CE QUE ÇA MESURE : le taux d'exception OPÉRATIONNEL = la part de dimensions que le système
COURANT routerait vers un humain. C'est le pilote direct de la charge évaluateur (l'argument
de vente). CE QUE ÇA NE MESURE PAS : la justesse absolue — un modèle peut être confiant ET
faux (divergence faible, score faux). Le taux réel de dimensions contestables est donc ≥ ce
chiffre. Seuls des labels experts sur la grille v2 (golden set à migrer) donneraient le vrai.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import get_settings
from app.llm.base import LLMProvider
from app.llm.factory import get_llm
from app.llm.prompt import PROMPT_VERSION, build_scoring_prompt
from app.scoring.constants import AXES, AXIS_KEYS, SCALE_MAX
from app.scoring.ensemble import EnsembleThresholds, consensus

_DEFAULT_CORPUS = Path(__file__).resolve().parents[2] / "calibration" / "exception_corpus.json"
N_PASSES = 3  # aligné sur la prod (app/diagnostics/handlers.py)
_HYPOTHESIS_MAX = 0.20  # seuil §20.3 : au-delà, la thèse « on réduit la charge » vacille


# --- Pilotage de la température (introspection réservée au banc) ---------------
def _set_temperature(provider: LLMProvider, temperature: float) -> None:
    """Force la température sur le provider (et sa chaîne de fallback) pour le sweep.

    On touche un attribut privé (`_temperature`) : acceptable dans un outil de mesure
    hors-ligne, où l'on VEUT explorer l'effet de la température sur l'incertitude.
    """
    if hasattr(provider, "_temperature"):
        provider._temperature = temperature  # type: ignore[attr-defined]
    for sub in getattr(provider, "_providers", []) or []:
        _set_temperature(sub, temperature)


# --- Exécution d'un cas --------------------------------------------------------
@dataclass
class CaseResult:
    case_id: str
    tags: dict
    kept_passes: int
    confidence: float
    uncertain_axes: list[str]
    per_axis_spread: dict[str, int]
    needs_review: bool
    consensus_axes: dict[str, int]
    error: str | None = None


async def _score_case(provider: LLMProvider, case: dict, *, n_passes: int) -> CaseResult:
    tags = case.get("tags", {})

    async def _one_pass(perspective: int) -> dict:
        prompt = build_scoring_prompt(
            AXES,
            category=case.get("category", "commerce"),
            archetype=case.get("archetype", "digital"),
            description=case.get("description"),
            answers=case.get("answers") or {},
            perspective=perspective,
            lang="fr",
        )
        return await provider.analyze_json(prompt)

    # TOLÉRANT comme la prod : une passe qui échoue ne fait pas tomber le cas.
    raw = await asyncio.gather(*(_one_pass(k) for k in range(n_passes)), return_exceptions=True)

    passes: list[dict[str, int]] = []
    for out in raw:
        if not (isinstance(out, dict) and isinstance(out.get("axes"), dict)):
            continue
        axes = out["axes"]
        # Ne garder qu'une passe qui couvre les 12 dimensions dans les bornes.
        try:
            coerced = {key: int(axes[key]) for key in AXIS_KEYS}
        except (KeyError, TypeError, ValueError):
            continue
        if all(0 <= v <= SCALE_MAX for v in coerced.values()):
            passes.append(coerced)

    if len(passes) < 2:
        # <2 passes valides : on ne peut PAS mesurer une divergence → cas exclu du taux.
        first_exc = next((r for r in raw if isinstance(r, Exception)), None)
        reason = str(first_exc) if first_exc else f"seulement {len(passes)} passe(s) valide(s)"
        return CaseResult(
            case_id=case["id"], tags=tags, kept_passes=len(passes), confidence=0.0,
            uncertain_axes=[], per_axis_spread={}, needs_review=True, consensus_axes={},
            error=reason,
        )

    cons = consensus(passes, AXIS_KEYS, EnsembleThresholds(), scale_max=SCALE_MAX)
    return CaseResult(
        case_id=case["id"], tags=tags, kept_passes=cons.n_passes, confidence=cons.confidence,
        uncertain_axes=cons.uncertain_axes, per_axis_spread=cons.per_axis_spread,
        needs_review=cons.needs_human_review, consensus_axes=cons.axes,
    )


# --- Agrégation ----------------------------------------------------------------
@dataclass
class Aggregate:
    temperature: float | None
    n_cases_total: int
    n_cases_measured: int
    dimension_exception_rate: float
    project_review_rate: float
    mean_confidence: float
    per_dimension_uncertain: dict[str, int]
    by_quality: dict[str, float]
    excluded: list[str] = field(default_factory=list)
    cases: list[CaseResult] = field(default_factory=list)


def _aggregate(results: list[CaseResult], temperature: float | None) -> Aggregate:
    measured = [r for r in results if r.error is None]
    excluded = [f"{r.case_id} ({r.error})" for r in results if r.error is not None]

    total_axis_instances = len(measured) * len(AXIS_KEYS)
    total_uncertain = sum(len(r.uncertain_axes) for r in measured)
    dim_rate = (total_uncertain / total_axis_instances) if total_axis_instances else 0.0
    project_rate = (sum(r.needs_review for r in measured) / len(measured)) if measured else 0.0
    mean_conf = round(statistics.fmean(r.confidence for r in measured), 3) if measured else 0.0

    per_dim = Counter()
    for r in measured:
        per_dim.update(r.uncertain_axes)

    # Taux par tranche de qualité de récit : le taux baisse-t-il quand le récit est riche ?
    by_quality: dict[str, float] = {}
    for tier in ("thin", "medium", "rich"):
        tier_cases = [r for r in measured if r.tags.get("quality") == tier]
        if tier_cases:
            inst = len(tier_cases) * len(AXIS_KEYS)
            unc = sum(len(r.uncertain_axes) for r in tier_cases)
            by_quality[tier] = round(unc / inst, 3)

    return Aggregate(
        temperature=temperature,
        n_cases_total=len(results),
        n_cases_measured=len(measured),
        dimension_exception_rate=round(dim_rate, 3),
        project_review_rate=round(project_rate, 3),
        mean_confidence=mean_conf,
        per_dimension_uncertain={k: per_dim[k] for k in AXIS_KEYS if per_dim[k]},
        by_quality=by_quality,
        excluded=excluded,
        cases=measured,
    )


# --- Rendu ---------------------------------------------------------------------
_LABELS = {axis["key"]: axis["label"] for axis in AXES}


def _verdict(rate: float) -> str:
    if rate <= _HYPOTHESIS_MAX:
        return f"✅ {rate:.0%} ≤ {_HYPOTHESIS_MAX:.0%} — l'hypothèse §20.3 TIENT sur ce corpus."
    if rate <= _HYPOTHESIS_MAX * 2:
        return (
            f"⚠️  {rate:.0%} > {_HYPOTHESIS_MAX:.0%} — au-dessus de l'hypothèse : "
            "la charge évaluateur serait notable."
        )
    return (
        f"🔴 {rate:.0%} — {rate / _HYPOTHESIS_MAX:.1f}× l'hypothèse : à ce niveau, "
        "la thèse « on réduit la charge » ne tient pas."
    )


def _print_aggregate(agg: Aggregate) -> None:
    head = "BANC D'EXCEPTION" + (f" — température {agg.temperature}" if agg.temperature is not None else "")
    print(f"\n=== {head} ===")
    print(f"  cas mesurés : {agg.n_cases_measured}/{agg.n_cases_total} · dimensions/cas : {len(AXIS_KEYS)}")
    print(
        f"  TAUX D'EXCEPTION (dimension) : {agg.dimension_exception_rate:.1%}"
        f"   ← vs hypothèse ≤ {_HYPOTHESIS_MAX:.0%}"
    )
    print(f"  projets routés vers l'humain : {agg.project_review_rate:.1%} (seuil prod : ≥1 axe incertain)")
    print(f"  confiance moyenne : {agg.mean_confidence}")
    if agg.by_quality:
        tiers = " · ".join(f"{tier}={rate:.0%}" for tier, rate in agg.by_quality.items())
        print(f"  taux par qualité de récit : {tiers}")
    if agg.per_dimension_uncertain:
        print("  dimensions les plus incertaines :")
        for key, count in sorted(agg.per_dimension_uncertain.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"    - {key} {_LABELS.get(key, ''):<26} {count} cas / {agg.n_cases_measured}")
    if agg.excluded:
        print(f"  exclus (mesure impossible) : {', '.join(agg.excluded)}")
    print(f"  => {_verdict(agg.dimension_exception_rate)}")


def _serialize(agg: Aggregate) -> dict:
    return {
        "temperature": agg.temperature,
        "n_cases_total": agg.n_cases_total,
        "n_cases_measured": agg.n_cases_measured,
        "dimension_exception_rate": agg.dimension_exception_rate,
        "project_review_rate": agg.project_review_rate,
        "mean_confidence": agg.mean_confidence,
        "by_quality": agg.by_quality,
        "per_dimension_uncertain": agg.per_dimension_uncertain,
        "excluded": agg.excluded,
        "hypothesis_max": _HYPOTHESIS_MAX,
        "cases": [
            {
                "id": r.case_id,
                "tags": r.tags,
                "kept_passes": r.kept_passes,
                "confidence": r.confidence,
                "needs_review": r.needs_review,
                "uncertain_axes": r.uncertain_axes,
                "per_axis_spread": r.per_axis_spread,
                "consensus_axes": r.consensus_axes,
            }
            for r in agg.cases
        ],
    }


# --- Orchestration -------------------------------------------------------------
async def run(
    corpus_path: Path,
    *,
    provider: LLMProvider,
    n_passes: int,
    temperatures: list[float] | None,
    limit: int | None,
) -> list[Aggregate]:
    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if not cases:
        raise SystemExit("Corpus vide.")
    if limit:
        cases = cases[:limit]

    aggregates: list[Aggregate] = []
    temps: list[float | None] = list(temperatures) if temperatures else [None]
    for temp in temps:
        if temp is not None:
            _set_temperature(provider, temp)
        # Cas en séquence (borne la charge sur le provider) ; passes d'un cas en parallèle.
        results = [await _score_case(provider, case, n_passes=n_passes) for case in cases]
        aggregates.append(_aggregate(results, temp))
    return aggregates


def main() -> int:
    # Console Windows (cp1252) : les accents + emoji du rapport cassent l'encodage par défaut.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Banc d'essai du taux d'exception du Radar.")
    parser.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS)
    parser.add_argument("--passes", type=int, default=N_PASSES, help="passes LLM par cas (défaut 3)")
    parser.add_argument(
        "--sweep", type=str, default=None, help="températures séparées par des virgules, ex. 0.2,0.7,1.0"
    )
    parser.add_argument("--limit", type=int, default=None, help="ne traiter que les N premiers cas")
    parser.add_argument("--mock", action="store_true", help="provider mock (câblage SEULEMENT — pas un signal réel)")
    parser.add_argument("--out", type=Path, default=None, help="écrit le rapport JSON à ce chemin")
    args = parser.parse_args()

    settings = get_settings()
    if args.mock:
        from app.llm.mock import MockProvider

        provider: LLMProvider = MockProvider(settings)
        print("⚠️  Mode MOCK : scores déterministes dérivés du prompt — valide le CÂBLAGE, pas le taux réel.")
    else:
        provider = get_llm(settings)

    temperatures = [float(t) for t in args.sweep.split(",")] if args.sweep else None
    aggregates = asyncio.run(
        run(args.corpus, provider=provider, n_passes=args.passes, temperatures=temperatures, limit=args.limit)
    )

    for agg in aggregates:
        _print_aggregate(agg)

    if len(aggregates) > 1:
        print("\n--- Sensibilité à la température (taux d'exception dimension) ---")
        for agg in aggregates:
            print(f"    temp {agg.temperature} : {agg.dimension_exception_rate:.1%} · confiance {agg.mean_confidence}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"corpus": str(args.corpus), "model": getattr(provider, "model", "?"),
                   "prompt_version": PROMPT_VERSION, "runs": [_serialize(a) for a in aggregates]}
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nRapport écrit : {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
