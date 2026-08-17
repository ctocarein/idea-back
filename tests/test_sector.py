"""Vocabulaire sectoriel fermé : résolution des alias, familles, comparaison.

Ce qui est testé ici n'est pas du calcul mais une **frontière** : rien ne doit
entrer en base hors des 14 clés, et rien ne doit sortir en comparaison sans
effectif suffisant. Les deux échouent en silence si on ne les fixe pas.
"""

from __future__ import annotations

import pytest

from app.core.sector import (
    SECTOR_GROUPS,
    SECTOR_HINTS,
    SECTOR_LABELS,
    Sector,
    SectorGroup,
    group_of,
    normalize_sector,
    peers_of,
)
from app.scoring.comparison import (
    MIN_COHORT_SIZE,
    ComparisonBasis,
    resolve_scope,
)

# --- Vocabulaire ------------------------------------------------------------


def test_every_sector_has_a_label_and_a_hint() -> None:
    """Un secteur sans exemple pousse le porteur vers « autre », qui casse le corpus."""
    for sector in Sector:
        assert SECTOR_LABELS[sector].strip()
        assert SECTOR_HINTS[sector].strip()


def test_every_sector_but_autre_belongs_to_exactly_one_family() -> None:
    grouped = [sector for sectors in SECTOR_GROUPS.values() for sector in sectors]
    assert len(grouped) == len(set(grouped)), "un secteur ne peut appartenir à deux familles"
    assert set(grouped) == set(Sector) - {Sector.AUTRE}
    assert group_of(Sector.AUTRE) is None
    assert peers_of(Sector.AUTRE) == ()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Clés « -tech » de la grille v2, réellement présentes en base.
        ("agritech", Sector.AGRO),
        ("fintech", Sector.FINANCE),
        ("edtech", Sector.EDUCATION),
        # Texte libre saisi avant la fermeture : casse, accents, séparateurs.
        ("Agro-alimentaire", Sector.AGRO),
        ("ÉNERGIE", Sector.ENERGIE_ENVIRONNEMENT),
        ("import / export", Sector.COMMERCE),
        ("mobile money", Sector.FINANCE),
        ("bien-être", Sector.SANTE),
        ("  Transport  ", Sector.TRANSPORT_LOGISTIQUE),
        # Les valeurs canoniques se résolvent toujours.
        ("energie_environnement", Sector.ENERGIE_ENVIRONNEMENT),
        ("autre", Sector.AUTRE),
        # Inconnu → AUTRE, signal et non repli acceptable.
        ("nanotechnologie quantique", Sector.AUTRE),
        ("", Sector.AUTRE),
        (None, Sector.AUTRE),
    ],
)
def test_normalize_sector_resolves_legacy_values(raw: str | None, expected: Sector) -> None:
    assert normalize_sector(raw) is expected


def test_enum_coercion_accepts_aliases() -> None:
    """`Sector("fintech")` doit marcher : c'est ce que fait le DTO à l'entrée d'API."""
    assert Sector("fintech") is Sector.FINANCE
    with pytest.raises(ValueError):
        Sector("nanotechnologie quantique")


def test_canonical_keys_fit_the_migrated_column() -> None:
    """La migration 0022 resserre la colonne à 40 caractères."""
    assert max(len(sector.value) for sector in Sector) <= 40


# --- Comparaison ------------------------------------------------------------


def test_populated_sector_is_compared_to_itself() -> None:
    scope = resolve_scope(Sector.AGRO, sector_count=MIN_COHORT_SIZE, group_count=200)
    assert scope.basis is ComparisonBasis.SECTOR
    assert scope.sectors == (Sector.AGRO,)
    assert scope.cohort_size == MIN_COHORT_SIZE
    assert scope.is_publishable


def test_thin_sector_falls_back_to_its_family() -> None:
    scope = resolve_scope(Sector.AGRO, sector_count=MIN_COHORT_SIZE - 1, group_count=MIN_COHORT_SIZE)
    assert scope.basis is ComparisonBasis.GROUP
    assert scope.group is SectorGroup.PRODUCTION
    assert set(scope.sectors) == set(SECTOR_GROUPS[SectorGroup.PRODUCTION])
    assert scope.is_publishable


def test_thin_family_publishes_nothing() -> None:
    """Une comparaison sur trop peu de projets coûte plus qu'elle ne rapporte."""
    scope = resolve_scope(Sector.AGRO, sector_count=3, group_count=8)
    assert scope.basis is ComparisonBasis.NONE
    assert scope.sectors == ()
    assert not scope.is_publishable
    # La famille reste renseignée : utile pour tracer POURQUOI on s'est tu.
    assert scope.group is SectorGroup.PRODUCTION


def test_autre_is_never_comparable_even_when_crowded() -> None:
    scope = resolve_scope(Sector.AUTRE, sector_count=10_000, group_count=10_000)
    assert scope.basis is ComparisonBasis.NONE
    assert scope.group is None
    assert not scope.is_publishable
