"""Environnement Alembic — migrations asynchrones (asyncpg).

L'URL et les métadonnées proviennent du code (app.core.config + app.models), pas
du .ini : une seule source de vérité, aucun secret versionné.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Importer l'agrégateur enregistre TOUTES les tables sur Base.metadata.
import app.models  # noqa: F401
from alembic import context
from app.core.config import get_settings
from app.core.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Injecte l'URL async résolue depuis la config applicative.
config.set_main_option("sqlalchemy.url", get_settings().async_database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    # Mode "offline" : génère le SQL sans connexion (utile pour relecture).
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # détecte les changements de type de colonne
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
