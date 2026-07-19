"""Déduplication déterministe des constats — IDX-INCOH-02.

Le modèle signale volontiers la MÊME contradiction sous plusieurs types. Sur le corpus de
calibration, un constat est ressorti **trois fois** (arithmetic, market, internal) avec les
mêmes citations et la même explication ; un autre deux fois (internal, regulatory).

Deux consignes anti-doublon successives dans le prompt ont échoué à le corriger. On tranche
donc **en code** : même paire de citations ⇒ un seul constat, on garde le type le plus
vérifiable et la gravité la plus haute du groupe.

Module PUR (stdlib) : testable hors-ligne, sans IA ni DB — même parti pris que
`app/scoring/ensemble.py`. C'est ce qui permet de le prouver sans dépenser un appel LLM.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import Enum


class InconsistencyType(str, Enum):
    ARITHMETIC = "arithmetic"
    TEMPORAL = "temporal"
    REGULATORY = "regulatory"
    MARKET = "market"
    CAPACITY = "capacity"
    INTERNAL = "internal"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Ordre de SPÉCIFICITÉ, du plus vérifiable au plus générique.
# `internal` est le fourre-tout (« ces deux phrases se contredisent ») : tout autre type dit
# quelque chose de plus précis sur la NATURE du conflit. À paire de citations égale, on retient
# donc le type qui informe le plus l'évaluateur — et qu'il peut recouper le plus facilement.
_SPECIFICITY: tuple[InconsistencyType, ...] = (
    InconsistencyType.ARITHMETIC,  # se rejoue avec une calculatrice
    InconsistencyType.TEMPORAL,  # se rejoue avec un calendrier
    InconsistencyType.REGULATORY,  # renvoie à une obligation identifiable
    InconsistencyType.MARKET,  # renvoie à un repère de pouvoir d'achat
    InconsistencyType.CAPACITY,  # confronte des moyens à des prétentions
    InconsistencyType.INTERNAL,  # générique
)

_SEVERITY_RANK: dict[Severity, int] = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2}

# Le modèle répond en français : on traduit à la frontière, le domaine reste en anglais.
_TYPE_ALIASES: dict[str, InconsistencyType] = {
    "arithmetique": InconsistencyType.ARITHMETIC,
    "arithmétique": InconsistencyType.ARITHMETIC,
    "temporelle": InconsistencyType.TEMPORAL,
    "temporel": InconsistencyType.TEMPORAL,
    "reglementaire": InconsistencyType.REGULATORY,
    "réglementaire": InconsistencyType.REGULATORY,
    "marche": InconsistencyType.MARKET,
    "marché": InconsistencyType.MARKET,
    "capacite": InconsistencyType.CAPACITY,
    "capacité": InconsistencyType.CAPACITY,
    "interne": InconsistencyType.INTERNAL,
}

_SEVERITY_ALIASES: dict[str, Severity] = {
    "basse": Severity.LOW,
    "moyenne": Severity.MEDIUM,
    "haute": Severity.HIGH,
}

# En deçà de cette longueur, un préfixe commun ne prouve rien : deux citations distinctes
# peuvent partager leurs premiers mots (« Notre cible, ce sont… »). Au-delà, la coïncidence
# devient improbable et l'on peut conclure qu'il s'agit de la même phrase, tronquée.
_MIN_PREFIX_LENGTH = 40


@dataclass(frozen=True)
class Finding:
    """Un constat d'incohérence : deux citations qui ne peuvent pas être vraies ensemble."""

    type: InconsistencyType
    quote_a: str
    quote_b: str
    explanation: str
    severity: Severity
    # Types sous lesquels le modèle avait AUSSI signalé ce même constat. Conservé pour la
    # traçabilité de l'audit : on doit pouvoir expliquer pourquoi un doublon a disparu.
    merged_types: tuple[InconsistencyType, ...] = ()


def normalize_quote(text: str) -> str:
    """Réduit une citation à sa forme comparable (casse, accents, ponctuation, espaces).

    Les espaces INTERNES AUX NOMBRES sont supprimés : le français écrit « 1 500 FCFA » là où
    le modèle recopie volontiers « 1500 FCFA ». Sans cette normalisation, un constat parfaitement
    valide serait écarté pour une question de séparateur de milliers.
    """
    folded = unicodedata.normalize("NFKD", text.strip().lower())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    folded = re.sub(r"[^a-z0-9 ]+", " ", folded)
    folded = re.sub(r"\s+", " ", folded).strip()
    return re.sub(r"(?<=\d) (?=\d)", "", folded)


def _same_quote(left: str, right: str) -> bool:
    normalized_left, normalized_right = normalize_quote(left), normalize_quote(right)
    if not normalized_left or not normalized_right:
        return normalized_left == normalized_right
    if normalized_left == normalized_right:
        return True
    # Le modèle tronque ses citations à des longueurs variables d'une passe à l'autre :
    # un préfixe commun assez long désigne la même phrase.
    shorter, longer = sorted((normalized_left, normalized_right), key=len)
    return len(shorter) >= _MIN_PREFIX_LENGTH and longer.startswith(shorter)


def _same_pair(left: Finding, right: Finding) -> bool:
    # L'ordre des deux citations n'est pas stable d'une passe à l'autre : A/B et B/A
    # désignent la même contradiction.
    direct = _same_quote(left.quote_a, right.quote_a) and _same_quote(left.quote_b, right.quote_b)
    crossed = _same_quote(left.quote_a, right.quote_b) and _same_quote(left.quote_b, right.quote_a)
    return direct or crossed


def _merge(cluster: Sequence[Finding]) -> Finding:
    kept = min(cluster, key=lambda finding: _SPECIFICITY.index(finding.type))
    # On retient la gravité la plus haute du groupe : si une passe a jugé « haute », le
    # constat mérite l'attention de l'évaluateur, même si une autre l'a minorée.
    severity = max(cluster, key=lambda finding: _SEVERITY_RANK[finding.severity]).severity
    others = {finding.type for finding in cluster} - {kept.type}
    merged_types = tuple(sorted(others, key=_SPECIFICITY.index))
    return replace(kept, severity=severity, merged_types=merged_types)


def deduplicate(findings: Sequence[Finding]) -> list[Finding]:
    """Regroupe les constats portant sur la même paire de citations et n'en garde qu'un.

    L'ordre d'entrée est préservé pour le premier représentant de chaque groupe : le rapport
    reste lisible dans l'ordre où les passes ont travaillé.
    """
    clusters: list[list[Finding]] = []
    for finding in findings:
        for cluster in clusters:
            if any(_same_pair(finding, member) for member in cluster):
                cluster.append(finding)
                break
        else:
            clusters.append([finding])
    return [_merge(cluster) for cluster in clusters]


def parse_finding(raw: dict, *, fallback_type: str | None = None) -> Finding | None:
    """Convertit une sortie brute du modèle en `Finding`, ou None si elle est inexploitable.

    Un constat sans ses DEUX citations n'est pas vérifiable par le client : il n'a aucune
    valeur d'audit et doit être écarté ici plutôt que d'atteindre le rapport.
    """
    quote_a = str(raw.get("quote_a") or raw.get("passage_a") or "").strip()
    quote_b = str(raw.get("quote_b") or raw.get("passage_b") or "").strip()
    if not quote_a or not quote_b:
        return None

    raw_type = str(raw.get("type") or fallback_type or "").strip().lower()
    try:
        inconsistency_type = InconsistencyType(raw_type)
    except ValueError:
        inconsistency_type = _TYPE_ALIASES.get(raw_type, InconsistencyType.INTERNAL)

    raw_severity = str(raw.get("severity") or raw.get("gravite") or "").strip().lower()
    try:
        severity = Severity(raw_severity)
    except ValueError:
        severity = _SEVERITY_ALIASES.get(raw_severity, Severity.MEDIUM)

    return Finding(
        type=inconsistency_type,
        quote_a=quote_a,
        quote_b=quote_b,
        explanation=str(raw.get("explanation") or raw.get("explication") or "").strip(),
        severity=severity,
    )


def parse_findings(raws: Iterable[dict], *, fallback_type: str | None = None) -> list[Finding]:
    parsed = (parse_finding(raw, fallback_type=fallback_type) for raw in raws)
    return [finding for finding in parsed if finding is not None]


def parse_analysis(payload: dict) -> list[Finding]:
    """Aplatit la sortie `analysis` (une entrée par type) en constats typés.

    Le modèle doit se prononcer sur chaque type, y compris pour dire qu'il n'a rien trouvé :
    les entrées vides sont donc normales et simplement ignorées ici.
    """
    findings: list[Finding] = []
    for entry in payload.get("analysis") or payload.get("analyse") or []:
        if not isinstance(entry, dict):
            continue
        raws = entry.get("findings") or entry.get("contradictions") or []
        findings.extend(parse_findings(raws, fallback_type=str(entry.get("type") or "")))
    return findings
