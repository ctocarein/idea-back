"""Ingestion d'un lot de dossiers — IDX-INCOH-04.

Les dossiers réels ne sont jamais des récits propres : exports Excel en `;` et cp1252,
copier-coller de PDF truffés de retours chariot, colonnes nommées « Présentation du projet »
ou « description_courte ». Ce module absorbe ce désordre pour que le service de détection ne
voie qu'un texte normalisé.

Deux principes :
- **Rien ne disparaît en silence.** Un dossier illisible ou trop court est écarté AVEC son
  motif : le rapport d'audit doit pouvoir dire « 3 dossiers non analysables », jamais laisser
  croire à 30 dossiers traités quand 27 l'ont été.
- **La référence du client est préservée.** Il doit pouvoir relier chaque constat à son propre
  dossier ; c'est lui qui anonymise avant de nous transmettre (cf. kit d'audit rétrospectif).
  `anonymize=True` reste disponible si la transmission n'a pas été anonymisée en amont.
"""

from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from app.core.logging import get_logger
from app.inconsistencies.service import Dossier

logger = get_logger("inconsistencies")

# En deçà, un texte ne peut pas contenir de contradiction interne : il n'y a pas deux
# affirmations à confronter. L'écarter vaut mieux que produire un dossier « propre » trompeur.
MIN_NARRATIVE_LENGTH = 150

# Les exports français sortent rarement en UTF-8 : on tente dans l'ordre du plus probable.
_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

_TEXT_SUFFIXES = (".txt", ".md", ".text")

# Noms de colonne rencontrés pour le corps du dossier, normalisés (sans accent, minuscules).
_NARRATIVE_COLUMNS = (
    "recit",
    "narrative",
    "description",
    "presentation",
    "projet",
    "texte",
    "contenu",
    "resume",
    "description_courte",
    "presentation_du_projet",
)
_REFERENCE_COLUMNS = ("reference", "ref", "id", "identifiant", "dossier", "numero", "code")

# Clé technique où atterrissent les champs surnuméraires d'une ligne mal échappée.
_OVERFLOW = "__overflow__"
_CATEGORY_COLUMNS = ("categorie", "category", "secteur", "sector", "filiere")


@dataclass(frozen=True)
class SkippedDossier:
    reference: str
    reason: str


@dataclass(frozen=True)
class IngestionResult:
    dossiers: list[Dossier] = field(default_factory=list)
    skipped: list[SkippedDossier] = field(default_factory=list)

    @property
    def total_seen(self) -> int:
        return len(self.dossiers) + len(self.skipped)


class IngestionError(RuntimeError):
    """Le lot ne peut pas être lu — message destiné à un humain, pas à un log."""


def _normalize_key(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.strip().lower())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", folded).strip("_")


def normalize_narrative(raw: str) -> str:
    """Nettoie un récit sans en altérer le sens : sauts de ligne, espaces, caractères parasites.

    Les paragraphes sont préservés (une ligne vide reste une ligne vide) : ils portent la
    structure du dossier, et les citations du modèle doivent rester retrouvables dans le texte.
    """
    text = raw.replace("﻿", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Caractères de contrôle (issus de copier-coller de PDF), sauf tabulation et saut de ligne.
    text = "".join(char for char in text if char in "\n\t" or not unicodedata.category(char).startswith("C"))
    text = text.replace("\t", " ")
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def anonymous_reference(source: str) -> str:
    """Référence stable et non réversible : même dossier ⇒ même identifiant d'un run à l'autre."""
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return f"D-{digest[:8]}"


def _read_text(path: Path) -> str:
    for encoding in _ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise IngestionError(f"Encodage illisible : {path.name} (essayés : {', '.join(_ENCODINGS)}).")


def _pick_column(fieldnames: Iterable[str], candidates: Iterable[str]) -> str | None:
    normalized = {_normalize_key(name): name for name in fieldnames if name}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    # Repli : une colonne qui CONTIENT un des noms attendus (« presentation_du_projet_2024 »).
    for candidate in candidates:
        for key, original in normalized.items():
            if candidate in key:
                return original
    return None


def _build(
    *,
    raw_narrative: str,
    source_reference: str,
    category: str,
    archetype: str,
    anonymize: bool,
) -> tuple[Dossier | None, SkippedDossier | None]:
    reference = anonymous_reference(source_reference) if anonymize else source_reference
    narrative = normalize_narrative(raw_narrative)
    if not narrative:
        return None, SkippedDossier(reference, "récit vide")
    if len(narrative) < MIN_NARRATIVE_LENGTH:
        return None, SkippedDossier(
            reference, f"récit trop court ({len(narrative)} caractères, minimum {MIN_NARRATIVE_LENGTH})"
        )
    return (
        Dossier(reference=reference, narrative=narrative, category=category, archetype=archetype),
        None,
    )


def load_csv(
    path: Path,
    *,
    narrative_column: str | None = None,
    reference_column: str | None = None,
    archetype: str = "?",
    anonymize: bool = False,
) -> IngestionResult:
    text = _read_text(path)
    # Les exports Excel francophones utilisent le point-virgule : on laisse le sniffer décider.
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    # `restkey` capte les champs surnuméraires : sans lui, un CSV mal échappé (récit contenant
    # des virgules, non entouré de guillemets) serait TRONQUÉ EN SILENCE — et l'audit
    # analyserait un texte amputé sans que personne ne s'en aperçoive.
    reader = csv.DictReader(text.splitlines(), dialect=dialect, restkey=_OVERFLOW)
    fieldnames = reader.fieldnames or []
    if not fieldnames:
        raise IngestionError(f"{path.name} : aucune colonne détectée.")

    narrative_key = narrative_column or _pick_column(fieldnames, _NARRATIVE_COLUMNS)
    if narrative_key is None:
        raise IngestionError(
            f"{path.name} : impossible de déterminer la colonne du récit.\n"
            f"Colonnes disponibles : {', '.join(fieldnames)}\n"
            "Précisez-la avec --column."
        )
    if narrative_key not in fieldnames:
        raise IngestionError(
            f"{path.name} : colonne « {narrative_key} » absente. Disponibles : {', '.join(fieldnames)}"
        )

    reference_key = reference_column or _pick_column(fieldnames, _REFERENCE_COLUMNS)
    category_key = _pick_column(fieldnames, _CATEGORY_COLUMNS)

    delimiter = getattr(dialect, "delimiter", ",")
    narrative_is_last = fieldnames[-1] == narrative_key

    dossiers: list[Dossier] = []
    skipped: list[SkippedDossier] = []
    for index, row in enumerate(reader, start=1):
        source_reference = (row.get(reference_key) or "").strip() if reference_key else ""
        if not source_reference:
            source_reference = f"{path.stem}-{index:04d}"

        narrative = row.get(narrative_key) or ""
        overflow = row.get(_OVERFLOW)
        if overflow:
            if narrative_is_last:
                # Cas courant et récupérable : le récit est la dernière colonne et contient des
                # séparateurs non échappés. On recolle plutôt que de rendre un texte amputé.
                narrative = delimiter.join([narrative, *(part or "" for part in overflow)])
            else:
                skipped.append(
                    SkippedDossier(
                        source_reference,
                        f"ligne CSV mal échappée ({len(fieldnames) + len(overflow)} champs "
                        f"pour {len(fieldnames)} colonnes) — récit potentiellement tronqué",
                    )
                )
                continue

        dossier, issue = _build(
            raw_narrative=narrative,
            source_reference=source_reference,
            category=(row.get(category_key) or "?").strip() if category_key else "?",
            archetype=archetype,
            anonymize=anonymize,
        )
        if dossier is not None:
            dossiers.append(dossier)
        elif issue is not None:
            skipped.append(issue)

    logger.info(
        "ingestion_csv",
        source=path.name,
        column=narrative_key,
        loaded=len(dossiers),
        skipped=len(skipped),
    )
    return IngestionResult(dossiers=dossiers, skipped=skipped)


def load_directory(
    path: Path, *, category: str = "?", archetype: str = "?", anonymize: bool = False
) -> IngestionResult:
    files = sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in _TEXT_SUFFIXES)
    if not files:
        raise IngestionError(f"{path} : aucun fichier {', '.join(_TEXT_SUFFIXES)} trouvé.")

    dossiers: list[Dossier] = []
    skipped: list[SkippedDossier] = []
    for file in files:
        try:
            raw = _read_text(file)
        except IngestionError as exc:
            skipped.append(SkippedDossier(file.stem, str(exc)))
            continue
        dossier, issue = _build(
            raw_narrative=raw,
            source_reference=file.stem,
            category=category,
            archetype=archetype,
            anonymize=anonymize,
        )
        if dossier is not None:
            dossiers.append(dossier)
        elif issue is not None:
            skipped.append(issue)

    logger.info("ingestion_directory", source=path.name, loaded=len(dossiers), skipped=len(skipped))
    return IngestionResult(dossiers=dossiers, skipped=skipped)


def load(
    path: Path,
    *,
    narrative_column: str | None = None,
    reference_column: str | None = None,
    category: str = "?",
    archetype: str = "?",
    anonymize: bool = False,
) -> IngestionResult:
    """Charge un lot depuis un CSV ou un répertoire de fichiers texte."""
    if not path.exists():
        raise IngestionError(f"Introuvable : {path}")
    if path.is_dir():
        return load_directory(path, category=category, archetype=archetype, anonymize=anonymize)
    if path.suffix.lower() in (".csv", ".tsv"):
        return load_csv(
            path,
            narrative_column=narrative_column,
            reference_column=reference_column,
            archetype=archetype,
            anonymize=anonymize,
        )
    raise IngestionError(
        f"Format non pris en charge : {path.suffix or '(sans extension)'}. "
        "Attendu : un fichier .csv/.tsv, ou un répertoire de fichiers .txt/.md."
    )
