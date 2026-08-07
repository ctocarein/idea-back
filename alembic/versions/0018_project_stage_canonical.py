"""Unifie le vocabulaire des étapes projet.

Revision ID: 0018_project_stage_canonical
Revises: 0017_scoring_integrity
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0018_project_stage_canonical"
down_revision = "0017_scoring_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `projects.stage` utilise l'enum PostgreSQL natif `projectstage`. PostgreSQL
    # exige que l'ajout de valeurs soit validé avant leur utilisation.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE projectstage ADD VALUE IF NOT EXISTS 'VALIDATION'")
        op.execute("ALTER TYPE projectstage ADD VALUE IF NOT EXISTS 'MVP'")
        op.execute("ALTER TYPE projectstage ADD VALUE IF NOT EXISTS 'TRACTION'")
        op.execute("ALTER TYPE projectstage ADD VALUE IF NOT EXISTS 'SCALE'")

    conn = op.get_bind()
    conn.execute(sa.text("UPDATE projects SET stage = 'MVP' WHERE stage::text = 'PROTOTYPE'"))
    conn.execute(sa.text("UPDATE projects SET stage = 'TRACTION' WHERE stage::text = 'FIRST_CUSTOMERS'"))
    conn.execute(sa.text("UPDATE projects SET stage = 'SCALE' WHERE stage::text = 'GROWING'"))

    # `users.project_stage` est une chaîne et utilisait déjà le vocabulaire cible.
    # Ces aliases couvrent d'éventuelles valeurs injectées par les anciens formulaires.
    conn.execute(sa.text("UPDATE users SET project_stage = 'mvp' WHERE project_stage = 'prototype'"))
    conn.execute(sa.text("UPDATE users SET project_stage = 'traction' WHERE project_stage = 'first_customers'"))
    conn.execute(sa.text("UPDATE users SET project_stage = 'scale' WHERE project_stage = 'growing'"))


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE projectstage ADD VALUE IF NOT EXISTS 'PROTOTYPE'")
        op.execute("ALTER TYPE projectstage ADD VALUE IF NOT EXISTS 'FIRST_CUSTOMERS'")
        op.execute("ALTER TYPE projectstage ADD VALUE IF NOT EXISTS 'GROWING'")

    conn = op.get_bind()
    conn.execute(sa.text("UPDATE projects SET stage = 'PROTOTYPE' WHERE stage::text IN ('VALIDATION', 'MVP')"))
    conn.execute(sa.text("UPDATE projects SET stage = 'FIRST_CUSTOMERS' WHERE stage::text = 'TRACTION'"))
    conn.execute(sa.text("UPDATE projects SET stage = 'GROWING' WHERE stage::text = 'SCALE'"))
    conn.execute(sa.text("UPDATE users SET project_stage = 'prototype' WHERE project_stage IN ('validation', 'mvp')"))
    conn.execute(sa.text("UPDATE users SET project_stage = 'first_customers' WHERE project_stage = 'traction'"))
    conn.execute(sa.text("UPDATE users SET project_stage = 'growing' WHERE project_stage = 'scale'"))
    # PostgreSQL ne permet pas de retirer proprement une valeur d'enum sans
    # recréer le type. Les labels supplémentaires restent donc inoffensifs.
