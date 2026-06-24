"""Éligibilité DÉTERMINISTE projet → opportunité.

Fonction pure (primitives, pas d'ORM) : testable, reproductible, sans LLM. Renvoie
(éligible, ce-qu'il-manque) — le « ce qu'il te manque pour viser plus haut » côté porteur.
"""

from __future__ import annotations


def evaluate_eligibility(
    *,
    min_overall: float,
    min_maturity: int | None,
    opp_sector: str | None,
    overall: float,
    maturity: int | None,
    sector: str | None,
) -> tuple[bool, list[str]]:
    missing: list[str] = []
    if overall < min_overall:
        missing.append(f"Score global de {min_overall:.0f}/10 requis (actuel {overall:.0f}/10).")
    if min_maturity is not None and (maturity is None or maturity < min_maturity):
        actuel = "n/d" if maturity is None else f"{maturity}/10"
        missing.append(f"Avancement (D11) de {min_maturity}/10 requis (actuel {actuel}).")
    if opp_sector and sector and opp_sector != sector:
        missing.append(f"Réservé au secteur « {opp_sector} ».")
    return (len(missing) == 0, missing)
