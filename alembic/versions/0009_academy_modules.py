"""Academy modules — dimension/phase/form_data sur guided_sessions + table need_fiches.

Revision ID: 0009_academy_modules
Revises: 0008_project_is_public
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009_academy_modules"
down_revision = "0008_project_is_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- guided_sessions : nouveaux champs module ---
    existing_cols = {
        r[0]
        for r in conn.execute(
            sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='guided_sessions'")
        )
    }

    if "dimension" not in existing_cols:
        op.add_column(
            "guided_sessions",
            sa.Column("dimension", sa.String(10), nullable=True),
        )
    if "phase" not in existing_cols:
        op.add_column(
            "guided_sessions",
            sa.Column("phase", sa.String(20), nullable=False, server_default="context"),
        )
    if "form_data" not in existing_cols:
        op.add_column(
            "guided_sessions",
            sa.Column("form_data", sa.dialects.postgresql.JSONB(), nullable=True),
        )
    # section peut déjà exister, mais s'assurer qu'elle accepte la valeur vide
    if "section" not in existing_cols:
        op.add_column(
            "guided_sessions",
            sa.Column("section", sa.String(80), nullable=False, server_default=""),
        )

    # Index sur dimension pour chercher les sessions par axe Radar
    idx_existing = {
        r[0] for r in conn.execute(sa.text("SELECT indexname FROM pg_indexes WHERE tablename='guided_sessions'"))
    }
    if "ix_guided_sessions_dimension" not in idx_existing:
        op.create_index("ix_guided_sessions_dimension", "guided_sessions", ["dimension"])

    # --- need_fiches ---
    tables = {r[0] for r in conn.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))}
    if "need_fiches" not in tables:
        op.create_table(
            "need_fiches",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column(
                "owner_id",
                sa.UUID(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "project_id",
                sa.UUID(),
                sa.ForeignKey("projects.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column(
                "session_id",
                sa.UUID(),
                sa.ForeignKey("guided_sessions.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column("dimension", sa.String(10), nullable=False),
            sa.Column("need_type", sa.String(40), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("details", sa.dialects.postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column(
                "is_validated",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    op.drop_table("need_fiches")
    op.drop_column("guided_sessions", "form_data")
    op.drop_column("guided_sessions", "phase")
    op.drop_column("guided_sessions", "dimension")
