"""initial schema (baseline)

Baseline du schéma MVP. CHOIX ASSUMÉ : on délègue à `Base.metadata` plutôt que d'écrire le
DDL à la main. Avantage : le schéma créé est **exactement** celui que l'ORM attend (types
ENUM PG, JSONB, ARRAY, tz-aware, FK) — impossible de diverger. Les révisions SUIVANTES sont
incrémentales et autogénérées (`make revision`), diffées contre cette baseline.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-23
"""

from __future__ import annotations

# Importer l'agrégateur enregistre TOUTES les tables sur Base.metadata.
import app.models  # noqa: F401
from alembic import op
from app.core.database import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crée toutes les tables + types ENUM dans l'ordre de dépendance des FK.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Réversible : supprime tables + types ENUM.
    Base.metadata.drop_all(bind=op.get_bind())
