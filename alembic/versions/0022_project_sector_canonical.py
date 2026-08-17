"""Ferme le vocabulaire sectoriel et rattrape les valeurs libres.

`projects.sector` était un `String(120)` libre, passé tel quel comme clé de
pondération (`CATEGORY_WEIGHTS`). Toute valeur qui ne tombait pas exactement sur
l'une des cinq clés minuscules faisait échouer la recherche en silence : les poids
retombaient à 1 sans erreur ni log. Le calcul restait juste, mais la pondération
sectorielle n'a jamais eu d'effet.

Conséquence plus lourde que le calcul : sans vocabulaire fermé, aucun regroupement
n'est possible, donc aucune comparaison à une population. Chaque diagnostic
enregistré en texte libre est perdu pour le corpus.

Cette migration résout les valeurs existantes via la table d'alias de
`app.core.sector`, bascule les inconnues sur `autre`, resserre la colonne et pose
l'index composite qui portera les requêtes de comparaison.

Revision ID: 0022_project_sector_canonical
Revises: 0021_drop_academy_lessons
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.core.sector import Sector, normalize_sector

revision = "0022_project_sector_canonical"
down_revision = "0021_drop_academy_lessons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Backfill — résolution alias par alias, sur les valeurs distinctes présentes.
    #    On passe par Python plutôt que par du SQL : la table d'alias est la même
    #    que celle utilisée à l'ingestion, elle ne doit exister qu'à un seul endroit.
    rows = conn.execute(sa.text("SELECT DISTINCT sector FROM projects")).fetchall()
    for (raw,) in rows:
        canonical = normalize_sector(raw)
        if raw == canonical.value:
            continue
        conn.execute(
            sa.text("UPDATE projects SET sector = :canonical WHERE sector = :raw"),
            {"canonical": canonical.value, "raw": raw},
        )

    # 2. Filet : toute valeur nulle ou vide devient explicitement `autre`.
    conn.execute(
        sa.text(
            "UPDATE projects SET sector = :autre "
            "WHERE sector IS NULL OR btrim(sector) = ''"
        ),
        {"autre": Sector.AUTRE.value},
    )

    # 3. Resserrement de la colonne. 40 caractères couvrent la plus longue clé
    #    (`energie_environnement`, 21) avec une marge confortable.
    op.alter_column(
        "projects",
        "sector",
        existing_type=sa.String(length=120),
        type_=sa.String(length=40),
        existing_nullable=False,
    )

    # 4. Index de corpus : toute comparaison filtre sur (secteur, palier).
    op.create_index("ix_projects_sector_stage", "projects", ["sector", "stage"])


def downgrade() -> None:
    op.drop_index("ix_projects_sector_stage", table_name="projects")
    op.alter_column(
        "projects",
        "sector",
        existing_type=sa.String(length=40),
        type_=sa.String(length=120),
        existing_nullable=False,
    )
    # Les valeurs libres d'origine ne sont pas restaurables : le backfill est
    # destructif par nature. C'est assumé — l'information perdue était du bruit.
