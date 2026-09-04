"""Unifie le score global sur /100 et lève la collision de vocabulaire « maturité ».

Le backend calculait le global sur /10 (`weighted_overall`) et ne le servait jamais
avec le radar : le contrat `RadarScore` ne portait que `axes`. Tout client était donc
contraint de le réagréger lui-même — sans les poids sectoriels, et sur /100. Le nombre
montré au porteur et le nombre persisté divergeaient en formule ET en échelle.

Cette migration aligne le stock sur la nouvelle échelle :

1. `score_runs.overall` est RECALCULÉ depuis `axes` + la grille qui l'a produit, pas
   converti par ×10. C'est précisément ce que la conception rejouable permet ; une
   conversion perdrait l'arrondi d'origine et introduirait une erreur là où l'exactitude
   est disponible. `axes` et `raw_output` ne sont pas touchés : seul l'agrégat bouge,
   donc tout reste auditable.
2. `reports.radar_score` reçoit `overall`, `pillars` et `sectorCalibrated` — le global
   voyage désormais AVEC le radar, et n'est plus jamais recalculé à l'affichage.
3. `opportunities.min_overall` passe de /10 à /100 (×10). Sans cela, un seuil de 6
   deviendrait 6/100 et l'opportunité s'ouvrirait silencieusement à tout le monde.
4. `opportunities.min_maturity` → `min_advancement` : le seuil porte sur la seule
   dimension D11 (/10), pas sur le palier de maturité globale (/100).

La formule de pondération est INLINÉE ici plutôt qu'importée de `app.scoring.engine` :
une migration doit produire le même résultat dans dix ans, même si le moteur évolue.

Revision ID: 0023_overall_scale_100
Revises: 0022_project_sector_canonical
"""

from __future__ import annotations

import json

import sqlalchemy as sa

from alembic import op

revision = "0023_overall_scale_100"
down_revision = "0022_project_sector_canonical"
branch_labels = None
depends_on = None

OVERALL_SCALE = 100
DEFAULT_WEIGHT = 1.0


def _weighted_overall(
    axis_keys: list[str],
    weights_override: dict,
    axes: dict,
    scale_max: int,
) -> int:
    # Copie FIGÉE de `engine.weighted_overall` au moment de cette révision.
    if not axis_keys or scale_max <= 0:
        return 0
    weights = {key: float((weights_override or {}).get(key, DEFAULT_WEIGHT)) for key in axis_keys}
    total_w = sum(weights.values())
    if total_w == 0:
        return 0
    weighted = sum(float(axes.get(key) or 0) * weights[key] for key in weights)
    return round((weighted / total_w) * (OVERALL_SCALE / scale_max))


def _pillar_scores(grid_axes: list[dict], axes: dict) -> dict:
    # Copie figée de `engine.pillar_scores` : moyenne SIMPLE par pilier.
    groups: dict[str, list[int]] = {}
    for axis in grid_axes:
        key = axis.get("pillar") or axis.get("lens") or "_"
        groups.setdefault(key, []).append(int(axes.get(axis["key"]) or 0))
    return {key: round(sum(vals) / len(vals)) for key, vals in groups.items() if vals}


def _has_column(conn, table: str, column: str) -> bool:
    """`0001_initial` crée le schéma COURANT des modèles via `create_all` : sur une base
    vierge, la colonne porte DÉJÀ son nom d'arrivée. Chaque révision qui altère une table
    doit donc être idempotente, sous peine de casser `upgrade head` from scratch.
    """
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        ).first()
    )


def _load_grids(conn) -> dict:
    rows = conn.execute(sa.text("SELECT version, axes, category_weights, scale_max FROM scoring_grids")).mappings()
    return {
        row["version"]: {
            "axes": row["axes"] or [],
            "category_weights": row["category_weights"] or {},
            "scale_max": row["scale_max"] or 10,
        }
        for row in rows
    }


def upgrade() -> None:
    conn = op.get_bind()
    grids = _load_grids(conn)

    # --- 1. score_runs : recalcul exact de l'agrégat ------------------------------
    runs = conn.execute(
        sa.text(
            "SELECT r.id, r.grid_version, r.axes, p.sector FROM score_runs r JOIN projects p ON p.id = r.project_id"
        )
    ).mappings()
    for run in runs:
        grid = grids.get(run["grid_version"])
        if grid is None:
            # Grille absente (base partielle) : sans référentiel, pas de recalcul honnête.
            continue
        keys = [axis["key"] for axis in grid["axes"]]
        overall = _weighted_overall(
            keys,
            (grid["category_weights"] or {}).get(run["sector"], {}),
            run["axes"] or {},
            grid["scale_max"],
        )
        conn.execute(
            sa.text("UPDATE score_runs SET overall = :overall WHERE id = :id"),
            {"overall": overall, "id": run["id"]},
        )

    # --- 2. reports : le global voyage avec le radar ------------------------------
    reports = conn.execute(
        sa.text(
            "SELECT rp.id, rp.radar_score, rp.comprehension, p.sector "
            "FROM reports rp JOIN projects p ON p.id = rp.project_id "
            "WHERE rp.radar_score IS NOT NULL"
        )
    ).mappings()
    for report in reports:
        radar = dict(report["radar_score"] or {})
        axes = radar.get("axes") or {}
        if not axes:
            continue
        grid = grids.get(radar.get("gridVersion"))
        if grid is None:
            continue
        sector_weights = (grid["category_weights"] or {}).get(report["sector"], {})
        overall = _weighted_overall(
            [axis["key"] for axis in grid["axes"]],
            sector_weights,
            axes,
            grid["scale_max"],
        )
        pillars = _pillar_scores(grid["axes"], axes)
        radar.update({"overall": overall, "pillars": pillars, "sectorCalibrated": bool(sector_weights)})
        comprehension = dict(report["comprehension"] or {})
        comprehension.update({"overall": overall, "pillars": pillars})
        conn.execute(
            sa.text(
                "UPDATE reports SET radar_score = CAST(:radar AS jsonb), "
                "comprehension = CAST(:comprehension AS jsonb) WHERE id = :id"
            ),
            {
                "radar": json.dumps(radar),
                "comprehension": json.dumps(comprehension),
                "id": report["id"],
            },
        )

    # --- 3 & 4. opportunities : seuils réétalonnés, vocabulaire levé ---------------
    if _has_column(conn, "opportunities", "min_maturity"):
        op.alter_column("opportunities", "min_maturity", new_column_name="min_advancement")
    conn.execute(sa.text("UPDATE opportunities SET min_overall = LEAST(min_overall * 10, 100)"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE opportunities SET min_overall = min_overall / 10"))
    if _has_column(conn, "opportunities", "min_advancement"):
        op.alter_column("opportunities", "min_advancement", new_column_name="min_maturity")

    # Retour à /10 pour les agrégats. Approximatif par construction — l'arrondi d'origine
    # n'est pas récupérable — mais `axes` et `raw_output` sont intacts : un rejeu redonne
    # la valeur exacte. C'est la raison d'être de la conception rejouable.
    conn.execute(sa.text("UPDATE score_runs SET overall = ROUND(overall / 10.0)"))
    conn.execute(
        sa.text(
            "UPDATE reports SET radar_score = radar_score - 'overall' - 'pillars' - 'sectorCalibrated', "
            "comprehension = jsonb_set(comprehension, '{overall}', "
            "to_jsonb(ROUND((comprehension->>'overall')::numeric / 10))) "
            "WHERE radar_score IS NOT NULL AND comprehension ? 'overall'"
        )
    )
