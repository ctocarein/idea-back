"""Vérification des citations — un constat doit être recoupable dans le récit source.

Deux défauts mesurés justifient ce garde-fou, tous deux impossibles à corriger par le prompt :

1. Le modèle cite le **bloc de contexte** (« revenu d'un ménage modeste ≈ 100 000 XOF ») comme
   s'il s'agissait d'une phrase du dossier. Une consigne explicite n'y a rien changé.
2. Le modèle **fabrique** parfois une citation (« 1 200 × 5 000 = 6 000 000 »), qui est un
   calcul, pas un extrait.

Or la promesse du produit est « vérifiez vous-même en cinq secondes ». Une citation
introuvable dans le récit détruit cette promesse et, dans un rapport d'audit remis à une
institution, se retourne immédiatement contre nous. On tranche donc en code, comme pour la
déduplication : ce qui ne se recoupe pas ne sort pas.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.inconsistencies.dedup import Finding, normalize_quote

# Le modèle tronque, recolle et reponctue ses citations. On compare donc sur la forme
# normalisée, et on tolère qu'une citation soit un fragment CONTINU du récit.
_MIN_QUOTE_LENGTH = 12


def quote_is_grounded(quote: str, narrative: str) -> bool:
    """Vrai si la citation se retrouve telle quelle dans le récit, à la normalisation près."""
    normalized_quote = normalize_quote(quote)
    if len(normalized_quote) < _MIN_QUOTE_LENGTH:
        # Trop courte pour être vérifiable par un lecteur : sans valeur d'audit.
        return False
    return normalized_quote in normalize_quote(narrative)


def is_grounded(finding: Finding, narrative: str) -> bool:
    """Un constat n'est recevable que si ses DEUX citations viennent du récit."""
    return quote_is_grounded(finding.quote_a, narrative) and quote_is_grounded(finding.quote_b, narrative)


def keep_grounded(findings: Sequence[Finding], narrative: str) -> tuple[list[Finding], list[Finding]]:
    """Sépare les constats recoupables de ceux qui ne le sont pas.

    Renvoie `(retenus, écartés)`. Les écartés ne sont pas perdus en silence : ils sont
    remontés à l'appelant, qui doit pouvoir les journaliser — un taux d'écart qui grimpe
    est le signal d'une dérive du prompt ou du modèle.
    """
    kept: list[Finding] = []
    dropped: list[Finding] = []
    for finding in findings:
        (kept if is_grounded(finding, narrative) else dropped).append(finding)
    return kept, dropped
