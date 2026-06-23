"""Seed de développement — un compte de démo par rôle.

Idempotent : relançable sans dupliquer (on saute un email déjà présent).
Mot de passe commun aux comptes de démo : "ideaxion" (uniquement en local).

La grille Radar v1 (référentiel d'évaluation) sera seedée au Sprint 2 (épic SCORING),
quand le module scoring existera. Lancement : `python -m app.seed` (ou `make seed`).
"""

from __future__ import annotations

import asyncio

from app.core.database import dispose_engine, get_session_factory
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.iam.models import AccountStatus, Role
from app.iam.repository import UserRepository
from app.scoring import engine
from app.scoring.constants import (
    AXES,
    CATEGORY_WEIGHTS,
    GRID_VERSION_V2,
    PILLARS,
    SCALE_MAX,
)
from app.scoring.repository import ScoringRepository

logger = get_logger("seed")

DEMO_PASSWORD = "ideaxion"  # local uniquement
# Domaine `.dev` (et non `.test`) : `.test` est un TLD réservé que `EmailStr` refuse → les
# comptes de démo ne pourraient pas se logger via l'API. Le front démo doit s'aligner.
DEMO_USERS = [
    ("admin@ideaxion.dev", "Admin Démo", Role.ADMIN),
    ("analyst@ideaxion.dev", "Analyste Démo", Role.ANALYST),
    ("mentor@ideaxion.dev", "Mentor Démo", Role.MENTOR),
    ("founder@ideaxion.dev", "Porteur Démo", Role.FOUNDER),
]


async def _seed_users(repo: UserRepository) -> None:
    for email, full_name, role in DEMO_USERS:
        if await repo.get_by_email(email) is not None:
            logger.info("seed_user_skipped", email=email)
            continue
        await repo.create(
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            full_name=full_name,
            role=role,
            status=AccountStatus.ACTIVE,
        )
        logger.info("seed_user_created", email=email, role=role.value)


async def _seed_grid(repo: ScoringRepository) -> None:
    # Grille Radar v2 (placeholder) — à remplacer par les ancres figées en atelier.
    if await repo.get_by_version(GRID_VERSION_V2) is not None:
        logger.info("seed_grid_skipped", version=GRID_VERSION_V2)
        return
    # Contrôle d'intégrité AVANT activation : les ancres doivent couvrir 0..scale_max.
    engine.validate_grid(AXES, SCALE_MAX)
    await repo.create(
        version=GRID_VERSION_V2,
        pillars=PILLARS,
        axes=AXES,
        category_weights=CATEGORY_WEIGHTS,
        is_active=True,
        scale_max=SCALE_MAX,
    )
    logger.info("seed_grid_created", version=GRID_VERSION_V2)


async def seed() -> None:
    configure_logging()
    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            await _seed_users(UserRepository(session))
            await _seed_grid(ScoringRepository(session))
    await dispose_engine()
    logger.info("seed_done")


if __name__ == "__main__":
    asyncio.run(seed())
