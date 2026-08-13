"""Seed de production minimal — compte admin + données structurelles.

Idempotent : relançable sans dupliquer (on saute un email déjà présent).
Ne crée aucun compte porteur/mentor/analyste de démo : les vrais comptes sont créés via l'UI.

Lancement : `python -m app.seed` (ou `make seed`).
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import dispose_engine, get_session_factory
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.iam.models import AccountStatus, Role
from app.iam.repository import UserRepository
from app.opportunities.models import Opportunity, OpportunityKind
from app.pitchsim.constants import PITCH_AXES, PITCH_RUBRIC_VERSION, PITCH_SCALE_MAX
from app.pitchsim.repository import PitchRubricRepository
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

ADMIN_PASSWORD = "ideaxion"  # à changer en prod via l'UI ou une variable d'env
ADMIN_EMAIL = "admin@ideaxion.dev"
ADMIN_NAME = "Admin Ideaxion"


async def _seed_users(repo: UserRepository) -> None:
    if await repo.get_by_email(ADMIN_EMAIL) is not None:
        logger.info("seed_user_skipped", email=ADMIN_EMAIL)
        return
    await repo.create(
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        full_name=ADMIN_NAME,
        role=Role.ADMIN,
        status=AccountStatus.ACTIVE,
    )
    logger.info("seed_user_created", email=ADMIN_EMAIL, role=Role.ADMIN.value)


async def _seed_grid(repo: ScoringRepository) -> None:
    # Grille Radar v2 de préproduction. Toute évolution crée une nouvelle version :
    # une grille déjà utilisée pour un score n'est jamais modifiée en place.
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


DEMO_OPPORTUNITIES = [
    (
        "Programme Mentorat Ideaxion",
        OpportunityKind.MENTORAT,
        "Accompagnement par un mentor pour structurer ton projet.",
        None,
        0,
        None,
    ),
    (
        "Hackathon AgriTech",
        OpportunityKind.HACKATHON,
        "48h pour prototyper une solution agricole.",
        "agritech",
        4,
        None,
    ),
    ("Concours Jeune Pousse", OpportunityKind.CONCOURS, "Concours national pour projets early-stage.", None, 5, None),
    (
        "Incubateur Seed — Cohorte 1",
        OpportunityKind.INCUBATEUR,
        "Incubation de 6 mois pour projets avec premières preuves.",
        None,
        6,
        5,
    ),
]


async def _seed_pitch_rubric(repo: PitchRubricRepository) -> None:
    # Rubrique de pitch v1 (placeholder) — ancres validées avant activation, comme la grille Radar.
    if await repo.get_by_version(PITCH_RUBRIC_VERSION) is not None:
        logger.info("seed_pitch_rubric_skipped", version=PITCH_RUBRIC_VERSION)
        return
    engine.validate_grid(PITCH_AXES, PITCH_SCALE_MAX)  # les 8 axes Fond couvrent 0..10
    await repo.create(
        version=PITCH_RUBRIC_VERSION,
        axes=PITCH_AXES,
        is_active=True,
        scale_max=PITCH_SCALE_MAX,
    )
    logger.info("seed_pitch_rubric_created", version=PITCH_RUBRIC_VERSION)


async def _seed_opportunities(session: AsyncSession) -> None:
    for title, kind, desc, sector, min_overall, min_maturity in DEMO_OPPORTUNITIES:
        exists = (await session.execute(select(Opportunity.id).where(Opportunity.title == title))).first()
        if exists is not None:
            continue
        session.add(
            Opportunity(
                title=title,
                kind=kind,
                description=desc,
                sector=sector,
                min_overall=min_overall,
                min_maturity=min_maturity,
            )
        )
        logger.info("seed_opportunity_created", title=title)


async def seed() -> None:
    configure_logging()
    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            await _seed_users(UserRepository(session))
            await _seed_grid(ScoringRepository(session))
            await _seed_opportunities(session)
            await _seed_pitch_rubric(PitchRubricRepository(session))
    await dispose_engine()
    logger.info("seed_done")


if __name__ == "__main__":
    asyncio.run(seed())
