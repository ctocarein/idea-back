"""Montage des routers sous le préfixe /api/v1.

Centralise l'assemblage du routeur principal. Les features MVP sont montées au fur
et à mesure des sprints ; les features _v2 ne sont PAS montées en phase freemium.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.diagnostics.router import router as diagnostics_router
from app.iam.router import router as iam_router
from app.platform.router import router as platform_router
from app.reports.router import router as reports_router
from app.scoring.router import router as scoring_router

# Routeur racine de l'API versionnée.
api_router = APIRouter(prefix="/api/v1")

# --- Plateforme / santé ---
api_router.include_router(platform_router)

# --- Features MVP ---
api_router.include_router(iam_router)  # /auth/*, /me        (Sprint 1)
api_router.include_router(scoring_router)  # /scoring/grid    (Sprint 2)
api_router.include_router(diagnostics_router)  # /diagnostics (Sprint 2)
api_router.include_router(reports_router)  # /reports         (Sprint 2)

# Sprints suivants (à monter quand prêts) :
#   from app.academy.router import router as academy_router          # Sprint 3
#   from app.pitchsim.router import router as pitchsim_router        # Sprint 4
#   from app.mentors.router import router as mentors_router          # Sprint 5
#   ...
