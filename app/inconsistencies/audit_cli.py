"""Relecture et production du rapport d'audit — IDX-RAPPORT-01/02/03/04.

Deux temps, séparés à dessein : la machine propose, l'humain tranche, puis seulement le
rapport se produit.

    # 1. exporter les constats à relire (s'ouvre dans un tableur)
    python -m app.inconsistencies.audit_cli review --audit audit.json --out relecture.csv

    # 2. … l'humain remplit la colonne « decision » : keep ou drop …

    # 3. produire le rapport à partir des seuls constats validés
    python -m app.inconsistencies.audit_cli report --audit audit.json --review relecture.csv \\
        --out rapport.html --pdf rapport.pdf --csv constats.csv --client "Concours X"

L'étape 3 REFUSE de produire quoi que ce soit tant qu'un constat n'a pas été tranché.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.inconsistencies.report import render_audit_html, render_audit_pdf, to_client_csv
from app.inconsistencies.review import (
    ReviewError,
    apply_decisions,
    build_rows,
    read_review,
    rejection_notes,
    summarize_review,
    write_review,
)


def _load_audit(path: Path) -> dict:
    if not path.exists():
        raise ReviewError(f"Audit introuvable : {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _cmd_review(args: argparse.Namespace) -> int:
    audit = _load_audit(args.audit)
    count = write_review(args.out, audit)
    print(f"{count} constat(s) à relire → {args.out}")
    if count:
        print("Ouvrez le fichier, remplissez la colonne « decision » avec keep ou drop,")
        print("et notez le motif des rejets dans « note » — c'est ce qui fera progresser le détecteur.")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    audit = _load_audit(args.audit)
    reviewed = apply_decisions(audit, read_review(args.review))

    counts = summarize_review(build_rows(reviewed))
    print(f"Relecture : {counts['keep']} retenu(s) · {counts['drop']} écarté(s) · {counts['pending']} non tranché(s)")

    # Lève si un constat reste `pending` : rien ne part chez un client sans avoir été vu.
    html = render_audit_html(reviewed, client=args.client, reference=args.reference)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"Rapport HTML → {args.out}")

    if args.csv:
        args.csv.write_text(to_client_csv(reviewed), encoding="utf-8-sig")
        print(f"Export tableur → {args.csv}")

    if args.pdf:
        try:
            args.pdf.write_bytes(render_audit_pdf(html))
            print(f"Rapport PDF → {args.pdf}")
        except ImportError:
            print("PDF non produit : WeasyPrint absent (extra « pdf »). Le HTML reste livrable.", file=sys.stderr)

    notes = rejection_notes(reviewed)
    if notes:
        print(f"\n{len(notes)} motif(s) de rejet — à rejouer sur le corpus avant le prochain lot :")
        for type_, note in notes[:10]:
            print(f"  - [{type_}] {note}")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # sorties accentuées sous Windows
    parser = argparse.ArgumentParser(description="Relecture humaine et rapport d'audit.")
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser("review", help="exporter les constats à relire")
    review.add_argument("--audit", type=Path, required=True)
    review.add_argument("--out", type=Path, required=True)
    review.set_defaults(func=_cmd_review)

    report = sub.add_parser("report", help="produire le rapport à partir des constats validés")
    report.add_argument("--audit", type=Path, required=True)
    report.add_argument("--review", type=Path, required=True)
    report.add_argument("--out", type=Path, required=True, help="rapport HTML")
    report.add_argument("--pdf", type=Path, default=None)
    report.add_argument("--csv", type=Path, default=None, help="export tableur des constats")
    report.add_argument("--client", default=None, help="nom affiché en titre")
    report.add_argument("--reference", default=None, help="référence du lot")
    report.set_defaults(func=_cmd_report)

    args = parser.parse_args()
    try:
        return int(args.func(args))
    except ReviewError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
