"""Profil porteur — onboarding (country, professional_status, project_stage…)

Ajoute 6 colonnes à `users` : country, city, professional_status, project_stage,
weekly_availability, onboarding_completed. Idempotent. Les comptes existants reçoivent
onboarding_completed=true (ils ont été créés avant la feature, on ne les force pas).

Revision ID: 0003_user_onboarding_profile
Revises: 0002_pitch_deck_source
Create Date: 2026-06-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_user_onboarding_profile"
down_revision = "0002_pitch_deck_source"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    cols = _columns("users")

    if "country" not in cols:
        op.add_column("users", sa.Column("country", sa.String(2), nullable=True))
    if "city" not in cols:
        op.add_column("users", sa.Column("city", sa.String(100), nullable=True))
    if "professional_status" not in cols:
        op.add_column("users", sa.Column("professional_status", sa.String(30), nullable=True))
    if "project_stage" not in cols:
        op.add_column("users", sa.Column("project_stage", sa.String(20), nullable=True))
    if "weekly_availability" not in cols:
        op.add_column("users", sa.Column("weekly_availability", sa.String(10), nullable=True))
    if "onboarding_completed" not in cols:
        op.add_column(
            "users",
            sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default="true"),
        )


def downgrade() -> None:
    cols = _columns("users")
    for col in [
        "onboarding_completed",
        "weekly_availability",
        "project_stage",
        "professional_status",
        "city",
        "country",
    ]:
        if col in cols:
            op.drop_column("users", col)
