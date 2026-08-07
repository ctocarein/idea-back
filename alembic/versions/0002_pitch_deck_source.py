"""pitch deck source file (présentation persistée dans la session)

Ajoute `source_key` + `source_content_type` à `pitch_decks` : le deck partagé dans le salon
est stocké (MinIO) et ré-affiché au reload. Idempotent (guard d'existence) pour cohabiter avec
la baseline `create_all` sur une base fraîche.

Revision ID: 0002_pitch_deck_source
Revises: 0001_initial
Create Date: 2026-06-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_pitch_deck_source"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    cols = _columns("pitch_decks")
    if "source_key" not in cols:
        op.add_column("pitch_decks", sa.Column("source_key", sa.String(length=300), nullable=True))
    if "source_content_type" not in cols:
        op.add_column("pitch_decks", sa.Column("source_content_type", sa.String(length=100), nullable=True))


def downgrade() -> None:
    cols = _columns("pitch_decks")
    if "source_content_type" in cols:
        op.drop_column("pitch_decks", "source_content_type")
    if "source_key" in cols:
        op.drop_column("pitch_decks", "source_key")
