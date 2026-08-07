"""Sécurise le scoring v2 et retire les tokens de partage en clair.

Revision ID: 0017_scoring_integrity
Revises: 0016_user_language
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0017_scoring_integrity"
down_revision = "0016_user_language"
branch_labels = None
depends_on = None

OLD_GRID_VERSION = "v2-placeholder"
NEW_GRID_VERSION = "radar-v2.0.0-preprod.1"


def upgrade() -> None:
    conn = op.get_bind()

    # Correction d'identifiant uniquement : la définition JSON de cette révision
    # reste inchangée. Les prochaines évolutions créeront une nouvelle grille.
    conn.execute(
        sa.text("UPDATE scoring_grids SET version = :new WHERE version = :old"),
        {"old": OLD_GRID_VERSION, "new": NEW_GRID_VERSION},
    )
    conn.execute(
        sa.text("UPDATE score_runs SET grid_version = :new WHERE grid_version = :old"),
        {"old": OLD_GRID_VERSION, "new": NEW_GRID_VERSION},
    )
    conn.execute(
        sa.text("UPDATE reports SET grid_version = :new WHERE grid_version = :old"),
        {"old": OLD_GRID_VERSION, "new": NEW_GRID_VERSION},
    )
    conn.execute(
        sa.text(
            """
            UPDATE reports
            SET radar_score = jsonb_set(
                radar_score,
                '{gridVersion}',
                to_jsonb(CAST(:new AS text)),
                false
            )
            WHERE radar_score->>'gridVersion' = :old
            """
        ),
        {"old": OLD_GRID_VERSION, "new": NEW_GRID_VERSION},
    )

    # Les références optionnelles devenues orphelines sont neutralisées avant
    # d'activer les contraintes. Un ScoreRun sans projet bloque volontairement
    # la migration : le supprimer automatiquement détruirait une trace d'audit.
    conn.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM score_runs sr
                    LEFT JOIN projects p ON p.id = sr.project_id
                    WHERE p.id IS NULL
                ) THEN
                    RAISE EXCEPTION 'score_runs contient une référence project_id orpheline';
                END IF;
            END $$
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE score_runs sr
            SET diagnostic_id = NULL
            WHERE diagnostic_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM diagnostics d WHERE d.id = sr.diagnostic_id)
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE score_runs sr
            SET report_id = NULL
            WHERE report_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM reports r WHERE r.id = sr.report_id)
            """
        )
    )

    constrained = {tuple(fk["constrained_columns"]) for fk in sa.inspect(conn).get_foreign_keys("score_runs")}
    if ("project_id",) not in constrained:
        op.create_foreign_key(
            "fk_score_runs_project_id_projects",
            "score_runs",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="CASCADE",
        )
    if ("diagnostic_id",) not in constrained:
        op.create_foreign_key(
            "fk_score_runs_diagnostic_id_diagnostics",
            "score_runs",
            "diagnostics",
            ["diagnostic_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if ("report_id",) not in constrained:
        op.create_foreign_key(
            "fk_score_runs_report_id_reports",
            "score_runs",
            "reports",
            ["report_id"],
            ["id"],
            ondelete="SET NULL",
        )

    columns = {
        row[0]
        for row in conn.execute(
            sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='project_shares'")
        )
    }
    if "token" in columns:
        op.drop_column("project_shares", "token")


def downgrade() -> None:
    op.add_column("project_shares", sa.Column("token", sa.String(length=64), nullable=True))
    for fk in sa.inspect(op.get_bind()).get_foreign_keys("score_runs"):
        if fk["constrained_columns"] in (["report_id"], ["diagnostic_id"], ["project_id"]) and fk["name"]:
            op.drop_constraint(fk["name"], "score_runs", type_="foreignkey")

    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE reports SET grid_version = :old WHERE grid_version = :new"),
        {"old": OLD_GRID_VERSION, "new": NEW_GRID_VERSION},
    )
    conn.execute(
        sa.text("UPDATE score_runs SET grid_version = :old WHERE grid_version = :new"),
        {"old": OLD_GRID_VERSION, "new": NEW_GRID_VERSION},
    )
    conn.execute(
        sa.text("UPDATE scoring_grids SET version = :old WHERE version = :new"),
        {"old": OLD_GRID_VERSION, "new": NEW_GRID_VERSION},
    )
    conn.execute(
        sa.text(
            """
            UPDATE reports
            SET radar_score = jsonb_set(
                radar_score,
                '{gridVersion}',
                to_jsonb(CAST(:old AS text)),
                false
            )
            WHERE radar_score->>'gridVersion' = :new
            """
        ),
        {"old": OLD_GRID_VERSION, "new": NEW_GRID_VERSION},
    )
