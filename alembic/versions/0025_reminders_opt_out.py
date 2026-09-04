"""Désabonnement des rappels par email.

Obligation légale, et condition de DÉLIVRABILITÉ : sans lien de désabonnement, un mail non
sollicité dégrade la réputation d'expédition — critique sur IP mutualisée, où la livraison
des emails de vérification de compte est en jeu.

Le drapeau ne couvre QUE les rappels : les emails transactionnels continuent de partir.

Revision ID: 0025_reminders_opt_out
Revises: 0024_diagnostic_drafts
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0025_reminders_opt_out"
down_revision = "0024_diagnostic_drafts"
branch_labels = None
depends_on = None


def _has_column(conn, table: str, column: str) -> bool:
    # Idempotence : `0001_initial` crée déjà le schéma courant des modèles.
    return any(col["name"] == column for col in sa.inspect(conn).get_columns(table))


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_column(conn, "users", "reminders_opt_out"):
        op.add_column(
            "users",
            sa.Column("reminders_opt_out", sa.Boolean(), nullable=False, server_default="false"),
        )


def downgrade() -> None:
    op.drop_column("users", "reminders_opt_out")
