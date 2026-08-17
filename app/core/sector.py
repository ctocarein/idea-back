"""Vocabulaire canonique des secteurs d'activité.

Même patron que `app/core/project_stage.py` : un enum fermé, des alias absorbés par
`_missing_` pour rattraper les valeurs libres historiques, et aucune valeur émise
hors de cette liste.

Deux niveaux, et l'ordre compte :

* `Sector` — 13 valeurs **stockées**. Granularité fine, volontairement.
* `SectorGroup` — 4 familles **dérivées**, jamais stockées, utilisées pour la
  comparaison quand la case sectorielle est trop peu peuplée.

Fusionner plus tard est trivial ; séparer plus tard est impossible (l'information
n'existe plus en base). D'où le stockage fin et le regroupement au moment de lire.

Ce vocabulaire décrit l'économie réelle de la zone UEMOA, pas une taxonomie
« -tech » importée : la dimension numérique/terrain est déjà portée séparément par
`Archetype` (`app/projects/models.py`), et ne doit pas être dupliquée ici.
"""

from __future__ import annotations

import unicodedata
from enum import Enum


class Sector(str, Enum):
    AGRO = "agro"
    COMMERCE = "commerce"
    RESTAURATION = "restauration"
    ARTISANAT_MODE = "artisanat_mode"
    BTP_IMMOBILIER = "btp_immobilier"
    TRANSPORT_LOGISTIQUE = "transport_logistique"
    SANTE = "sante"
    EDUCATION = "education"
    FINANCE = "finance"
    SERVICES_PRO = "services_pro"
    NUMERIQUE = "numerique"
    ENERGIE_ENVIRONNEMENT = "energie_environnement"
    TOURISME_CULTURE = "tourisme_culture"

    # Dernier recours. Exclu de toute comparaison : un projet « autre » ne peut
    # être situé dans aucune population. Un taux > 15 % signale que la liste
    # ci-dessus est fausse, pas que les porteurs se trompent.
    AUTRE = "autre"

    @classmethod
    def _missing_(cls, value: object) -> Sector | None:
        if not isinstance(value, str):
            return None
        return _ALIASES.get(_normalize(value))


class SectorSource(str, Enum):
    """Qui a posé le secteur. Même rôle que `ScoreSource` pour les notes.

    Sans cette trace, un changement de modèle reclasse le corpus sans que rien ne
    le signale, et la comparaison se met à comparer des populations hétérogènes.
    """

    LLM = "llm"  # déduit du récit par l'extraction
    HUMAN = "human"  # confirmé ou corrigé par le porteur
    IMPORT = "import"  # posé lors d'un import de cohorte institutionnelle


class SectorGroup(str, Enum):
    PRODUCTION = "production"
    COMMERCE_FLUX = "commerce_flux"
    SERVICES_PERSONNE = "services_personne"
    SERVICES_NUMERIQUE = "services_numerique"


SECTOR_LABELS: dict[Sector, str] = {
    Sector.AGRO: "Agriculture & agro-transformation",
    Sector.COMMERCE: "Commerce & distribution",
    Sector.RESTAURATION: "Restauration & alimentation",
    Sector.ARTISANAT_MODE: "Artisanat, mode & beauté",
    Sector.BTP_IMMOBILIER: "BTP, matériaux & immobilier",
    Sector.TRANSPORT_LOGISTIQUE: "Transport & logistique",
    Sector.SANTE: "Santé & bien-être",
    Sector.EDUCATION: "Éducation & formation",
    Sector.FINANCE: "Finance & assurance",
    Sector.SERVICES_PRO: "Services aux entreprises",
    Sector.NUMERIQUE: "Logiciel, plateformes & médias",
    Sector.ENERGIE_ENVIRONNEMENT: "Énergie, eau & environnement",
    Sector.TOURISME_CULTURE: "Tourisme, culture & événementiel",
    Sector.AUTRE: "Autre",
}

# Exemples affichés sous chaque option du sélecteur. Un porteur qui hésite plus de
# deux secondes choisit « autre » : ces exemples sont ce qui protège le corpus.
SECTOR_HINTS: dict[Sector, str] = {
    Sector.AGRO: "maraîchage, anacarde, attiéké, élevage, pêche",
    Sector.COMMERCE: "boutique, grossiste, import-export, e-commerce",
    Sector.RESTAURATION: "maquis, traiteur, pâtisserie, boissons",
    Sector.ARTISANAT_MODE: "pagne, couture, cosmétique, coiffure, décoration",
    Sector.BTP_IMMOBILIER: "construction, briqueterie, agence immobilière",
    Sector.TRANSPORT_LOGISTIQUE: "livraison, VTC, fret, entreposage",
    Sector.SANTE: "clinique, pharmacie, laboratoire, nutrition",
    Sector.EDUCATION: "école, centre de formation, soutien scolaire",
    Sector.FINANCE: "mobile money, microfinance, tontine, assurance",
    Sector.SERVICES_PRO: "conseil, comptabilité, marketing, RH, sécurité",
    Sector.NUMERIQUE: "SaaS, application, agence web, production de contenu",
    Sector.ENERGIE_ENVIRONNEMENT: "solaire, forage, déchets, recyclage",
    Sector.TOURISME_CULTURE: "hôtellerie, agence de voyage, événementiel, sport",
    Sector.AUTRE: "aucun des secteurs ci-dessus",
}

SECTOR_GROUPS: dict[SectorGroup, tuple[Sector, ...]] = {
    SectorGroup.PRODUCTION: (
        Sector.AGRO,
        Sector.ARTISANAT_MODE,
        Sector.BTP_IMMOBILIER,
        Sector.ENERGIE_ENVIRONNEMENT,
    ),
    SectorGroup.COMMERCE_FLUX: (
        Sector.COMMERCE,
        Sector.RESTAURATION,
        Sector.TRANSPORT_LOGISTIQUE,
    ),
    SectorGroup.SERVICES_PERSONNE: (
        Sector.SANTE,
        Sector.EDUCATION,
        Sector.TOURISME_CULTURE,
    ),
    SectorGroup.SERVICES_NUMERIQUE: (
        Sector.SERVICES_PRO,
        Sector.NUMERIQUE,
        Sector.FINANCE,
    ),
}

SECTOR_GROUP_LABELS: dict[SectorGroup, str] = {
    SectorGroup.PRODUCTION: "Production & transformation",
    SectorGroup.COMMERCE_FLUX: "Commerce & flux",
    SectorGroup.SERVICES_PERSONNE: "Services à la personne",
    SectorGroup.SERVICES_NUMERIQUE: "Services & numérique",
}

_GROUP_OF: dict[Sector, SectorGroup] = {
    sector: group for group, sectors in SECTOR_GROUPS.items() for sector in sectors
}


def group_of(sector: Sector) -> SectorGroup | None:
    """Famille de comparaison d'un secteur. `None` pour `AUTRE`, non comparable."""
    return _GROUP_OF.get(sector)


def peers_of(sector: Sector) -> tuple[Sector, ...]:
    """Secteurs partageant la famille de `sector`, `sector` inclus. Vide si `AUTRE`."""
    group = group_of(sector)
    return SECTOR_GROUPS[group] if group else ()


def _normalize(value: str) -> str:
    """Minuscules, sans accents, séparateurs unifiés — pour la table d'alias."""
    stripped = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_only = "".join(c for c in stripped if not unicodedata.combining(c))
    for separator in (" ", "-", "/", "'", "’", "&", ",", "."):
        ascii_only = ascii_only.replace(separator, "_")
    while "__" in ascii_only:
        ascii_only = ascii_only.replace("__", "_")
    return ascii_only.strip("_")


# Alias historiques : texte libre saisi avant la fermeture du vocabulaire, plus les
# clés « -tech » de la grille v2. Toute valeur absente ici retombe sur `AUTRE`, ce
# qui est un signal à surveiller — pas une valeur de repli acceptable en régime.
_RAW_ALIASES: dict[Sector, tuple[str, ...]] = {
    Sector.AGRO: (
        "agritech", "agriculture", "agro", "agroalimentaire", "agro_alimentaire",
        "agro_transformation", "agrobusiness", "agri", "elevage", "peche",
        "aquaculture", "maraichage", "transformation_agricole", "agro_industrie",
    ),
    Sector.COMMERCE: (
        "commerce", "distribution", "retail", "vente", "negoce", "import_export",
        "ecommerce", "e_commerce", "commerce_general", "boutique", "grossiste",
    ),
    Sector.RESTAURATION: (
        "restauration", "alimentation", "food", "foodtech", "traiteur",
        "restaurant", "maquis", "patisserie", "boulangerie", "boissons",
    ),
    Sector.ARTISANAT_MODE: (
        "artisanat", "mode", "textile", "couture", "beaute", "cosmetique",
        "coiffure", "decoration", "bijouterie", "art", "artisanat_mode",
    ),
    Sector.BTP_IMMOBILIER: (
        "btp", "batiment", "construction", "immobilier", "materiaux",
        "genie_civil", "architecture", "btp_immobilier",
    ),
    Sector.TRANSPORT_LOGISTIQUE: (
        "transport", "logistique", "livraison", "mobilite", "vtc", "fret",
        "entreposage", "supply_chain", "transport_logistique",
    ),
    Sector.SANTE: (
        "sante", "healthtech", "health", "medical", "pharmacie", "clinique",
        "bien_etre", "nutrition", "laboratoire",
    ),
    Sector.EDUCATION: (
        "education", "edtech", "formation", "enseignement", "ecole",
        "soutien_scolaire", "e_learning", "elearning",
    ),
    Sector.FINANCE: (
        "finance", "fintech", "assurance", "insurtech", "banque", "microfinance",
        "mobile_money", "tontine", "paiement", "credit",
    ),
    Sector.SERVICES_PRO: (
        "services", "services_pro", "services_aux_entreprises", "b2b", "conseil",
        "consulting", "comptabilite", "marketing", "communication", "rh",
        "recrutement", "securite", "juridique", "audit",
    ),
    Sector.NUMERIQUE: (
        "numerique", "digital", "tech", "informatique", "logiciel", "software",
        "saas", "application", "plateforme", "web", "medias", "media",
        "audiovisuel", "contenu", "ia", "data",
    ),
    Sector.ENERGIE_ENVIRONNEMENT: (
        "energie", "environnement", "cleantech", "greentech", "solaire",
        "energies_renouvelables", "dechets", "recyclage", "eau", "assainissement",
        "energie_environnement",
    ),
    Sector.TOURISME_CULTURE: (
        "tourisme", "culture", "evenementiel", "hotellerie", "voyage", "loisirs",
        "sport", "divertissement", "tourisme_culture",
    ),
    Sector.AUTRE: ("autre", "other", "divers", "non_precise", "n_a", "na"),
}

_ALIASES: dict[str, Sector] = {
    _normalize(alias): sector for sector, aliases in _RAW_ALIASES.items() for alias in aliases
}
# La valeur canonique doit toujours se résoudre, même absente de la table d'alias.
_ALIASES.update({_normalize(sector.value): sector for sector in Sector})


def normalize_sector(value: str | None) -> Sector:
    """Résout une valeur libre en secteur canonique. Inconnue → `AUTRE`.

    Utilisé par le backfill de migration et par toute ingestion d'un lot
    institutionnel (import de cohorte), jamais par l'API porteur : côté API, le
    DTO impose déjà l'enum et rejette ce qui n'en fait pas partie.
    """
    if not value:
        return Sector.AUTRE
    try:
        return Sector(value)
    except ValueError:
        return Sector.AUTRE
