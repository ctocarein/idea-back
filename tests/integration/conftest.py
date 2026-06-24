"""Fixtures d'intégration — app réelle (httpx ASGI) sur un Postgres de test.

Le schéma est créé via `Base.metadata.create_all` (= ce que l'ORM attend), la grille v2 est
seedée, et le LLM est le provider `mock` (déterministe, hors-ligne). Sans `TEST_DATABASE_URL`,
les tests d'intégration sont **ignorés** (pas de Postgres → skip).

Lancement : `TEST_DATABASE_URL=postgresql://ideaxion:ideaxion@localhost:5432/ideaxion uv run pytest tests/integration`
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

_TEST_DB = os.getenv("TEST_DATABASE_URL")


@pytest_asyncio.fixture
async def client():
    if not _TEST_DB:
        pytest.skip("TEST_DATABASE_URL non défini — test d'intégration ignoré.")

    # Config AVANT toute construction d'engine/settings.
    os.environ["DATABASE_URL"] = _TEST_DB
    os.environ.setdefault("JWT_SECRET", "integration-secret-32-bytes-minimum-ok")
    os.environ["LLM_PROVIDER"] = "mock"
    # MinIO désactivé en test (pas de serveur) : storage None → PDF/health dégradent.
    os.environ["MINIO_ACCESS_KEY"] = ""
    os.environ["MINIO_SECRET_KEY"] = ""

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.core import cache as cache_mod
    from app.core import database as db

    await db.dispose_engine()  # repart d'un engine propre, pointé sur la DB de test
    # Reset du client Redis global : il est lié à la boucle d'event ; chaque test a la
    # sienne (function scope) → on force un client frais pour éviter "different loop".
    cache_mod._redis = None

    import app.models  # noqa: F401  (enregistre les tables)
    from app.core.database import Base, get_engine, get_session_factory

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Seed minimal : la grille v2 active (le scoring en a besoin).
    from app.scoring.constants import (
        AXES,
        CATEGORY_WEIGHTS,
        GRID_VERSION_V2,
        PILLARS,
        SCALE_MAX,
    )
    from app.scoring.repository import ScoringRepository
    from app.seed import _seed_lessons, _seed_opportunities

    async with get_session_factory()() as session:
        async with session.begin():
            await ScoringRepository(session).create(
                version=GRID_VERSION_V2,
                pillars=PILLARS,
                axes=AXES,
                category_weights=CATEGORY_WEIGHTS,
                is_active=True,
                scale_max=SCALE_MAX,
            )
            # Sprint 3 : leçons (topics alignés aux leviers) + catalogue d'opportunités.
            await _seed_lessons(session)
            await _seed_opportunities(session)

    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db.dispose_engine()
