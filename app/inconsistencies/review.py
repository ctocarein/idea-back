"""Relecture humaine des constats — IDX-RAPPORT-01.

Le filtre humain n'est pas une étape annexe : **c'est le produit**. C'est lui qui garantit
qu'aucun constat douteux n'atteint le client, et donc la crédibilité de l'audit. Le réflexe
serait de l'automatiser d'emblée ; ce serait supprimer la propriété qui rend l'audit vendable.

Le mécanisme est volontairement pauvre : on exporte un fichier de relecture, un humain tranche
dans son tableur (il voit tout d'un coup, trie par gravité, filtre par type), on réimporte.
Aucune interface à construire, et la relecture reste plus rapide qu'au terminal.

Garantie centrale, vérifiée en code : **rien ne se publie tant qu'un constat reste `pending`.**
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

REVIEW_COLUMNS = (
    "finding_id",
    "dossier",
    "type",
    "severity",
    "decision",
    "note",
    "quote_a",
    "quote_b",
    "explanation",
)

# Ordre de relecture : le plus grave d'abord, c'est là que se joue la crédibilité du rapport.
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


class Decision(str, Enum):
    PENDING = "pending"
    KEEP = "keep"
    DROP = "drop"


_DECISION_ALIASES = {
    "": Decision.PENDING,
    "o": Decision.KEEP,
    "oui": Decision.KEEP,
    "y": Decision.KEEP,
    "yes": Decision.KEEP,
    "ok": Decision.KEEP,
    "garder": Decision.KEEP,
    "n": Decision.DROP,
    "non": Decision.DROP,
    "no": Decision.DROP,
    "ko": Decision.DROP,
    "rejeter": Decision.DROP,
    "ecarter": Decision.DROP,
}


class ReviewError(RuntimeError):
    """Anomalie de relecture — message destiné à un humain."""


@dataclass(frozen=True)
class ReviewRow:
    finding_id: str
    dossier: str
    type: str
    severity: str
    quote_a: str
    quote_b: str
    explanation: str
    decision: Decision = Decision.PENDING
    note: str = ""


def finding_id(dossier: str, finding: dict) -> str:
    """Identifiant stable d'un constat, indépendant de l'ordre du fichier.

    Le relecteur trie et filtre librement dans son tableur : l'appariement ne peut pas
    reposer sur un numéro de ligne.
    """
    material = "|".join(
        [
            dossier,
            str(finding.get("type", "")),
            str(finding.get("quote_a", "")),
            str(finding.get("quote_b", "")),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:10]


def build_rows(audit: dict) -> list[ReviewRow]:
    """Aplatit un audit en lignes de relecture, les plus graves d'abord."""
    rows: list[ReviewRow] = []
    for analysis in audit.get("analyses", []):
        dossier = str(analysis.get("reference", ""))
        for finding in analysis.get("findings", []):
            rows.append(
                ReviewRow(
                    finding_id=finding_id(dossier, finding),
                    dossier=dossier,
                    type=str(finding.get("type", "")),
                    severity=str(finding.get("severity", "")),
                    quote_a=str(finding.get("quote_a", "")),
                    quote_b=str(finding.get("quote_b", "")),
                    explanation=str(finding.get("explanation", "")),
                    decision=Decision(finding.get("decision", Decision.PENDING.value)),
                    note=str(finding.get("note", "")),
                )
            )
    rows.sort(key=lambda row: (_SEVERITY_ORDER.get(row.severity, 9), row.dossier, row.type))
    return rows


def to_csv(audit: dict) -> str:
    buffer = io.StringIO()
    # Point-virgule : les tableurs francophones ouvrent ainsi le fichier sans assistant d'import.
    writer = csv.DictWriter(buffer, fieldnames=REVIEW_COLUMNS, delimiter=";", lineterminator="\n")
    writer.writeheader()
    for row in build_rows(audit):
        writer.writerow(
            {
                "finding_id": row.finding_id,
                "dossier": row.dossier,
                "type": row.type,
                "severity": row.severity,
                "decision": row.decision.value,
                "note": row.note,
                "quote_a": row.quote_a,
                "quote_b": row.quote_b,
                "explanation": row.explanation,
            }
        )
    return buffer.getvalue()


def write_review(path: Path, audit: dict) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    # `utf-8-sig` : sans BOM, Excel affiche « MÃ©nage » au lieu de « Ménage ».
    path.write_text(to_csv(audit), encoding="utf-8-sig")
    return len(build_rows(audit))


def _parse_decision(raw: str) -> Decision:
    value = raw.strip().lower()
    try:
        return Decision(value)
    except ValueError:
        pass
    if value in _DECISION_ALIASES:
        return _DECISION_ALIASES[value]
    raise ReviewError(
        f"Décision « {raw} » non comprise. Attendu : keep / drop (ou oui / non), ou vide si non tranché."
    )


def read_review(path: Path) -> dict[str, tuple[Decision, str]]:
    """Relit le fichier tranché par l'humain : identifiant → (décision, note)."""
    if not path.exists():
        raise ReviewError(f"Fichier de relecture introuvable : {path}")
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines(), delimiter=";")
    if not reader.fieldnames or "finding_id" not in reader.fieldnames:
        raise ReviewError(f"{path.name} : colonne « finding_id » absente — ce n'est pas un fichier de relecture.")

    decisions: dict[str, tuple[Decision, str]] = {}
    for row in reader:
        key = (row.get("finding_id") or "").strip()
        if not key:
            continue
        decisions[key] = (_parse_decision(row.get("decision") or ""), (row.get("note") or "").strip())
    return decisions


def apply_decisions(audit: dict, decisions: dict[str, tuple[Decision, str]]) -> dict:
    """Reporte les décisions sur l'audit. Un constat absent du fichier reste `pending`."""
    updated = dict(audit)
    analyses = []
    for analysis in audit.get("analyses", []):
        dossier = str(analysis.get("reference", ""))
        findings = []
        for finding in analysis.get("findings", []):
            key = finding_id(dossier, finding)
            decision, note = decisions.get(key, (Decision.PENDING, ""))
            findings.append({**finding, "decision": decision.value, "note": note})
        analyses.append({**analysis, "findings": findings})
    updated["analyses"] = analyses
    return updated


def pending_count(audit: dict) -> int:
    return sum(1 for row in build_rows(audit) if row.decision is Decision.PENDING)


def ensure_publishable(audit: dict) -> None:
    """Interdit la publication tant qu'un constat n'a pas été tranché.

    C'est la garantie du produit : aucun constat ne part chez un client sans avoir été vu.
    Elle est vérifiée ICI, en code, et non laissée à la discipline de l'opérateur.
    """
    pending = pending_count(audit)
    if pending:
        raise ReviewError(
            f"{pending} constat(s) non tranché(s) : le rapport ne peut pas être produit. "
            "Complétez la colonne « decision » du fichier de relecture (keep / drop)."
        )


def kept_findings(audit: dict) -> dict:
    """Ne conserve que les constats validés — la matière du rapport client."""
    ensure_publishable(audit)
    analyses = []
    for analysis in audit.get("analyses", []):
        kept = [f for f in analysis.get("findings", []) if f.get("decision") == Decision.KEEP.value]
        analyses.append({**analysis, "findings": kept})
    return {**audit, "analyses": analyses}


def rejection_notes(audit: dict) -> list[tuple[str, str]]:
    """Motifs de rejet — matière première pour corriger le prompt au tour suivant."""
    return [(row.type, row.note) for row in build_rows(audit) if row.decision is Decision.DROP and row.note]


def summarize_review(rows: Sequence[ReviewRow] | Iterable[ReviewRow]) -> dict[str, int]:
    counts = {decision.value: 0 for decision in Decision}
    for row in rows:
        counts[row.decision.value] += 1
    return counts
