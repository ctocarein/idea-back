"""Règle de comparaison d'un projet à sa population.

Un score seul est un jugement ; un score situé dans une population est une
orientation. Mais une comparaison adossée à trois projets détruit plus de
crédibilité que l'absence de comparaison — d'où un seuil, et le silence en
dessous.

Trois issues possibles, dans l'ordre de préférence :

1. `SECTOR` — la case (secteur × palier) est assez peuplée : on compare au secteur.
2. `GROUP`  — elle ne l'est pas, mais la famille l'est : on compare à la famille,
   en le disant explicitement au porteur.
3. `NONE`   — ni l'un ni l'autre : on n'affiche rien. Pas d'approximation.

Le seuil et la règle vivent ici, isolés, pour que l'activation de la comparaison
soit un changement de constante et non une réécriture de la restitution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.core.sector import Sector, SectorGroup, group_of, peers_of

# Effectif minimal d'une case pour qu'une comparaison soit publiable.
# Choisi bas mais non trivial : au-dessous, l'écart-type d'un échantillon de
# scores /100 rend toute affirmation de position hasardeuse.
MIN_COHORT_SIZE = 20


class ComparisonBasis(str, Enum):
    SECTOR = "sector"
    GROUP = "group"
    NONE = "none"


@dataclass(frozen=True)
class ComparisonScope:
    """Sur quelle population comparer, et avec quel effectif."""

    basis: ComparisonBasis
    sectors: tuple[Sector, ...]
    cohort_size: int
    group: SectorGroup | None = None

    @property
    def is_publishable(self) -> bool:
        return self.basis is not ComparisonBasis.NONE


def resolve_scope(
    sector: Sector,
    *,
    sector_count: int,
    group_count: int,
) -> ComparisonScope:
    """Choisit la population de comparaison à partir des effectifs mesurés.

    `sector_count` et `group_count` sont les effectifs déjà filtrés sur le même
    palier de maturité **et** la même version de grille — comparer des scores
    produits par deux grilles différentes n'a pas de sens.

    `Sector.AUTRE` n'a pas de famille : il n'est jamais comparable.
    """
    group = group_of(sector)

    if group is None:
        return ComparisonScope(ComparisonBasis.NONE, (), 0)

    if sector_count >= MIN_COHORT_SIZE:
        return ComparisonScope(ComparisonBasis.SECTOR, (sector,), sector_count, group)

    if group_count >= MIN_COHORT_SIZE:
        return ComparisonScope(ComparisonBasis.GROUP, peers_of(sector), group_count, group)

    return ComparisonScope(ComparisonBasis.NONE, (), 0, group)
