"""Traitement d'un lot de dossiers en ligne de commande — IDX-INCOH-05.

    python -m app.inconsistencies.run_batch --input dossiers.csv --output audit.json
    python -m app.inconsistencies.run_batch --input ./dossiers/ --output audit.json --limit 30
    python -m app.inconsistencies.run_batch --input dossiers.csv --output audit.json --resume

`--resume` relit la sortie existante et ne retraite que les dossiers absents ou en échec :
sur un lot de 300, une coupure réseau ne doit pas coûter les 250 dossiers déjà payés.

La sortie JSON est la matière du rapport d'audit (S8). Elle porte tout ce qu'exige la
traçabilité d'un audit : version de prompt, modèle, contexte retenu par dossier, constats
écartés, dossiers non analysables.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.inconsistencies.ingestion import IngestionError, IngestionResult, load
from app.inconsistencies.service import (
    DEFAULT_CONCURRENCY,
    Dossier,
    DossierAnalysis,
    InconsistencyService,
    summarize,
)
from app.llm.factory import get_llm
from app.llm.prompt import CONTEXT_PROMPT_VERSION, INCONSISTENCY_PROMPT_VERSION


def _analysis_to_dict(analysis: DossierAnalysis) -> dict:
    return {
        "reference": analysis.reference,
        "findings": [
            {
                "type": finding.type.value,
                "severity": finding.severity.value,
                "quote_a": finding.quote_a,
                "quote_b": finding.quote_b,
                "explanation": finding.explanation,
                "merged_types": [t.value for t in finding.merged_types],
            }
            for finding in analysis.findings
        ],
        "context": analysis.context,
        "dropped": analysis.dropped,
        "failed_passes": analysis.failed_passes,
        "llm_calls": analysis.llm_calls,
        "error": analysis.error,
    }


def _load_previous(path: Path) -> dict[str, dict]:
    """Références déjà analysées AVEC SUCCÈS lors d'un run précédent."""
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        entry["reference"]: entry
        for entry in payload.get("analyses", [])
        if isinstance(entry, dict) and entry.get("reference") and not entry.get("error")
    }


def _print_ingestion(result: IngestionResult) -> None:
    print(f"Lot chargé : {len(result.dossiers)} dossier(s) analysable(s) sur {result.total_seen}")
    if result.skipped:
        # Rien ne disparaît en silence : le rapport devra mentionner ces dossiers.
        print(f"  {len(result.skipped)} écarté(s) à l'ingestion :")
        for issue in result.skipped[:10]:
            print(f"    - {issue.reference} : {issue.reason}")
        if len(result.skipped) > 10:
            print(f"    … et {len(result.skipped) - 10} autre(s)")


def _print_summary(analyses: list[DossierAnalysis], skipped: int) -> None:
    summary = summarize(analyses)
    print()
    print("=" * 70)
    print(f"  analysés            : {summary.analyzed}")
    print(f"  avec incohérence(s) : {summary.with_findings}")
    print(f"  SANS incohérence    : {summary.clean}")
    if summary.failed:
        print(f"  en échec            : {summary.failed}")
    if skipped:
        print(f"  non analysables     : {skipped}")
    print(f"  constats retenus    : {summary.total_findings} · par type : {summary.by_type or '—'}")
    print(f"  appels LLM          : {summary.llm_calls}")
    dropped = sum(analysis.dropped for analysis in analyses)
    if dropped:
        # Un taux qui grimpe signale une dérive du prompt ou du modèle.
        print(f"  constats écartés    : {dropped} (citations introuvables dans le récit)")


async def run(args: argparse.Namespace) -> int:
    try:
        ingested = load(
            args.input,
            narrative_column=args.column,
            reference_column=args.reference_column,
            category=args.category,
            archetype=args.archetype,
            anonymize=args.anonymize,
        )
    except IngestionError as exc:
        print(f"Erreur d'ingestion : {exc}", file=sys.stderr)
        return 2

    _print_ingestion(ingested)
    dossiers: list[Dossier] = ingested.dossiers
    if args.limit is not None:
        dossiers = dossiers[: args.limit]

    previous: dict[str, dict] = _load_previous(args.output) if args.resume else {}
    pending = [dossier for dossier in dossiers if dossier.reference not in previous]
    if previous:
        print(f"Reprise : {len(previous)} dossier(s) déjà analysé(s), {len(pending)} à traiter.")
    if not pending and not previous:
        print("Rien à analyser.")
        return 1

    settings = get_settings()
    provider = get_llm(settings)
    model = getattr(provider, "model", settings.llm_provider)
    print(f"Modèle : {model} · prompt {INCONSISTENCY_PROMPT_VERSION} · concurrence {args.concurrency}")

    service = InconsistencyService(
        provider,
        concurrency=args.concurrency,
        detect_context=not args.no_context,
    )
    fresh = await service.analyze_batch(pending)

    analyses_payload = [*previous.values(), *(_analysis_to_dict(analysis) for analysis in fresh)]
    _print_summary(fresh, skipped=len(ingested.skipped))

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": str(args.input),
        "model": model,
        "prompt_versions": {
            "context": CONTEXT_PROMPT_VERSION,
            "inconsistency": INCONSISTENCY_PROMPT_VERSION,
        },
        "not_analyzable": [asdict(issue) for issue in ingested.skipped],
        "analyses": analyses_payload,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nÉcrit : {args.output}")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # sorties accentuées sous Windows
    parser = argparse.ArgumentParser(description="Détection d'incohérences sur un lot de dossiers.")
    parser.add_argument("--input", type=Path, required=True, help="CSV, ou répertoire de fichiers .txt/.md")
    parser.add_argument("--output", type=Path, required=True, help="fichier JSON de sortie")
    parser.add_argument("--column", default=None, help="colonne du récit (sinon détectée)")
    parser.add_argument("--reference-column", default=None, help="colonne de la référence dossier")
    parser.add_argument("--category", default="?", help="secteur, si absent du fichier")
    parser.add_argument("--archetype", default="?", help="archétype, si absent du fichier")
    parser.add_argument("--limit", type=int, default=None, help="ne traiter que les N premiers")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--anonymize", action="store_true", help="remplace les références par un condensé stable")
    parser.add_argument("--no-context", action="store_true", help="désactive la détection pays/devise")
    parser.add_argument("--resume", action="store_true", help="ne retraite pas les dossiers déjà analysés")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
