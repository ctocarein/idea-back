"""Éligibilité DÉTERMINISTE projet → opportunité.

Fonction pure (primitives, pas d'ORM) : testable, reproductible, sans LLM. Renvoie
(éligible, ce-qu'il-manque) — le « ce qu'il te manque pour viser plus haut » côté porteur.
"""

from __future__ import annotations


def evaluate_eligibility(
    *,
    min_overall: float,  # seuil sur le score GLOBAL, /100
    min_advancement: int | None,  # seuil sur la DIMENSION D11 « Niveau d'avancement », /10
    opp_sector: str | None,
    overall: float,  # score global du projet, /100
    advancement: int | None,  # D11 du projet, /10
    sector: str | None,
) -> tuple[bool, list[str]]:
    """Deux seuils, deux échelles — ne pas les confondre (SPEC_SCORING_INTEGRITY C4).

    `min_overall` porte sur le score global normalisé /100 ; `min_advancement` sur la
    seule dimension D11, /10. L'ancien nom `min_maturity` faisait lire « maturité 6 »
    comme un palier global : la collision de vocabulaire est levée ici.
    """
    missing: list[str] = []
    if overall < min_overall:
        missing.append(f"Score global de {min_overall:.0f}/100 requis (actuel {overall:.0f}/100).")
    if min_advancement is not None and (advancement is None or advancement < min_advancement):
        actuel = "n/d" if advancement is None else f"{advancement}/10"
        missing.append(f"Avancement (D11) de {min_advancement}/10 requis (actuel {actuel}).")
    if opp_sector and sector and opp_sector != sector:
        missing.append(f"Réservé au secteur « {opp_sector} ».")
    return (len(missing) == 0, missing)
