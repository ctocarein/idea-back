"""Accès base de données — engine async, session factory, Base ORM, helper de transaction.

Tout est asynchrone (SQLAlchemy 2.0 + asyncpg). Le `repository` reçoit une `AsyncSession` ;
il ne crée jamais l'engine lui-même. Les transactions sont portées par le `service` (§4.3 archi).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    # Base déclarative commune à TOUS les modèles ORM.
    # Alembic lit `Base.metadata` pour l'autogénération des migrations.
    #
    # type_annotation_map : tout `Mapped[datetime]` devient une colonne TIMESTAMP
    # WITH TIME ZONE. Indispensable pour que asyncpg renvoie des datetimes *aware*
    # et éviter les comparaisons naïf/aware (TypeError) côté service.
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


# Engine et session factory uniques pour le process. Créés paresseusement
# pour que les tests qui n'ont pas besoin de DB n'ouvrent pas de connexion.
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.async_database_url,
            pool_pre_ping=True,  # détecte les connexions mortes avant usage
            echo=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,  # on garde les objets utilisables après commit
            autoflush=False,
        )
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    # Dépendance FastAPI : une session par requête, fermée à la fin.
    # La session ouvre sa transaction en autobegin dès la 1re requête SQL ; c'est le
    # SERVICE qui la commite (un seul commit par opération, audit inclus). En cas
    # d'exception non commitée, la fermeture de la session annule tout (rollback).
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def dispose_engine() -> None:
    # Appelé au shutdown (lifespan) pour libérer proprement le pool.
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
