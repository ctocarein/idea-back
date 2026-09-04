"""Persiste le diagnostic EN COURS de saisie (brouillon serveur).

`_start()` crée projet + diagnostic + rapport + job en une seule transaction : le statut
`DRAFT` ne dure que le temps de cette transaction. Un porteur qui abandonnait en cours de
saisie ne laissait donc AUCUNE ligne en base — et le taux d'abandon, comme l'étape où il
survient, étaient inconnus. Pour un produit dont le seul signal utilisateur validé porte
sur le moment du diagnostic, c'est la donnée manquante la plus coûteuse : elle ne se
déduit d'aucune autre.

Table SÉPARÉE plutôt qu'un statut sur `diagnostics` : un statut contaminerait tout le
pipeline, qui est sain. Le brouillon est un STOCKAGE, jamais un objet métier.

RGPD : aucune ligne avant création de compte (le parcours anonyme reste sur le
`localStorage` du visiteur), `consent_at` propre au brouillon, et purge — pas archivage —
au-delà de `draft_ttl_days`. L'effacement du compte est couvert par la cascade FK.

Revision ID: 0024_diagnostic_drafts
Revises: 0023_overall_scale_100
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0024_diagnostic_drafts"
down_revision = "0023_overall_scale_100"
branch_labels = None
depends_on = None

_TABLE = "diagnostic_drafts"
_INDEX = "uq_active_draft_per_owner"


def _has_table(conn, table: str) -> bool:
    # `0001_initial` crée le schéma COURANT des modèles via `create_all` : sur une base
    # vierge, la table existe déjà. Chaque révision doit donc être idempotente.
    return bool(sa.inspect(conn).has_table(table))


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_table(conn, _TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "owner_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("answers", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("mode", sa.String(length=20), nullable=False, server_default="GUIDED"),
            sa.Column("last_dimension", sa.String(length=10), nullable=True),
            sa.Column("consent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(f"ix_{_TABLE}_owner_id", _TABLE, ["owner_id"])
        op.create_index(f"ix_{_TABLE}_updated_at", _TABLE, ["updated_at"])
        op.create_index(f"ix_{_TABLE}_submitted_at", _TABLE, ["submitted_at"])

    # Un seul brouillon ACTIF par porteur. Index PARTIEL : les brouillons soumis sont
    # conservés pour l'analyse et ne doivent pas entrer dans l'unicité, sinon un porteur
    # ne pourrait jamais faire un second diagnostic.
    existing = {ix["name"] for ix in sa.inspect(conn).get_indexes(_TABLE)}
    if _INDEX not in existing:
        op.create_index(
            _INDEX,
            _TABLE,
            ["owner_id"],
            unique=True,
            postgresql_where=sa.text("submitted_at IS NULL"),
        )


def downgrade() -> None:
    op.drop_table(_TABLE)
