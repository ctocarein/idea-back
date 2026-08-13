"""Retire les tables de l'ancien Academy (leçons + progression).

Les routes `/academy/lessons*`, `/academy/progress` et `/academy/build/*` ont été
supprimées avec le redesign Workshop : plus aucun code ne lit ces deux tables.
Le Workshop actuel s'appuie sur `guided_sessions` et `need_fiches`, qui restent.

Défensive dans les deux sens : la baseline `0001_initial` crée le schéma depuis
`Base.metadata`, donc sur une base neuve ces tables n'existent déjà plus — le drop
doit alors être un no-op. Sur une base existante, elles sont bien présentes.

ATTENTION : `upgrade()` détruit les leçons seedées et l'historique de complétion.
`downgrade()` recrée la structure, pas les données.

Revision ID: 0021_drop_academy_lessons
Revises: 0020_project_memory
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0021_drop_academy_lessons"
down_revision = "0020_project_memory"
branch_labels = None
depends_on = None

_TABLES = ("learning_progress", "academy_lessons")  # ordre : la fille avant la mère (FK)


def _existing() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _existing()
    for table in _TABLES:
        if table in tables:
            op.drop_table(table)


def downgrade() -> None:
    tables = _existing()
    if "academy_lessons" not in tables:
        op.create_table(
            "academy_lessons",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("slug", sa.String(length=80), nullable=False, unique=True),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("topic", sa.String(length=60), nullable=False),
            sa.Column("summary", sa.String(length=400), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_academy_lessons_slug", "academy_lessons", ["slug"], unique=True)
        op.create_index("ix_academy_lessons_topic", "academy_lessons", ["topic"])

    if "learning_progress" not in tables:
        op.create_table(
            "learning_progress",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "lesson_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("academy_lessons.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "lesson_id", name="uq_progress_user_lesson"),
        )
        op.create_index("ix_learning_progress_user_id", "learning_progress", ["user_id"])
        op.create_index("ix_learning_progress_lesson_id", "learning_progress", ["lesson_id"])
