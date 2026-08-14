"""Non-régression migrations : `alembic upgrade head` doit passer sur une base VIDE.

Porte contre le bug historique : `0001_initial` fait `Base.metadata.create_all()` (crée tout
le schéma courant des modèles), donc chaque révision suivante qui ALTER une table/colonne déjà
créée doit être idempotente. Une base construite au fil des sprints ne révèle jamais le
problème ; seule une reconstruction *from scratch* le fait — c'est exactement ce que ce test
fait (DROP SCHEMA public CASCADE → base vierge → upgrade head).

Sans `TEST_DATABASE_URL`, le test est ignoré (pas de Postgres jetable).

Lancement : `TEST_DATABASE_URL=postgresql://ideaxion:ideaxion@localhost:5432/ideaxion uv run pytest tests/integration/test_migrations.py`
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

_TEST_DB = os.getenv("TEST_DATABASE_URL")

# Racine du repo (contient alembic.ini + le dossier alembic/).
_REPO_ROOT = Path(__file__).resolve().parents[2]


async def _reset_schema(async_url: str) -> None:
    """Repart d'une base réellement vierge : tables ET types ENUM supprimés."""
    import asyncpg

    # asyncpg veut une URL nue (sans le suffixe de driver +asyncpg).
    dsn = async_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    finally:
        await conn.close()


async def _current_revision(async_url: str) -> str | None:
    import asyncpg

    dsn = async_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        return await conn.fetchval("SELECT version_num FROM alembic_version")
    finally:
        await conn.close()


def test_upgrade_head_on_empty_database() -> None:
    if not _TEST_DB:
        pytest.skip("TEST_DATABASE_URL non défini — test de migration ignoré.")

    # Config AVANT toute lecture de settings (env.py alembic lit get_settings()).
    os.environ["DATABASE_URL"] = _TEST_DB
    os.environ.setdefault("JWT_SECRET", "integration-secret-32-bytes-minimum-ok")

    from app.core.config import get_settings

    get_settings.cache_clear()
    async_url = get_settings().async_database_url

    # Base vierge : le create_all de 0001 va tout créer, les révisions suivantes ne
    # doivent PAS collisionner (DuplicateColumn/DuplicateTable) — c'est ce qu'on prouve.
    asyncio.run(_reset_schema(async_url))

    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_REPO_ROOT / "alembic.ini"))
    # script_location est relatif dans le .ini ; on l'ancre en absolu (CWD indépendant).
    cfg.set_main_option("script_location", str(_REPO_ROOT / "alembic"))

    # Tête attendue = dérivée des scripts (pas de valeur en dur à maintenir).
    expected_head = ScriptDirectory.from_config(cfg).get_current_head()

    try:
        # Le cœur de l'assertion : ne doit lever aucune exception (le bug faisait échouer
        # 0006 avec `DuplicateColumnError: column "session_at" ... already exists`).
        command.upgrade(cfg, "head")

        head = asyncio.run(_current_revision(async_url))
        assert head == expected_head, f"tête inattendue après upgrade : {head!r}"
    finally:
        # Laisse la base propre pour les autres tests d'intégration (chacun recrée son schéma).
        asyncio.run(_reset_schema(async_url))
        get_settings.cache_clear()
