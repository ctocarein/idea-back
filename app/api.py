"""Montage des routers sous le préfixe /api/v1.

Centralise l'assemblage du routeur principal. Les features MVP sont montées au fur
et à mesure des sprints ; les features _v2 ne sont PAS montées en phase freemium.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.academy.router import router as academy_router
from app.audit.router import router as audit_router
from app.diagnostics.router import router as diagnostics_router
from app.documents.router import router as documents_router
from app.gdpr.router import router as gdpr_router
from app.iam.router import router as iam_router
from app.instrumentation.router import router as analytics_router
from app.jobs.router import router as jobs_admin_router
from app.mentors.router import router as mentors_router
from app.notifications.router import router as notifications_router
from app.opportunities.admin_router import router as opportunities_admin_router
from app.opportunities.router import router as opportunities_router
from app.pitch.router import router as pitch_router
from app.pitchsim.router import router as pitchsim_router
from app.platform.router import router as platform_router
from app.projects.owner_router import router as projects_owner_router
from app.projects.router import router as projects_admin_router
from app.reports.router import router as reports_router
from app.scoring.governance import router as scoring_admin_router
from app.scoring.router import router as scoring_router
from app.sharing.router import router as sharing_router
from app.studio.router import router as studio_router

# Routeur racine de l'API versionnée.
api_router = APIRouter(prefix="/api/v1")

# --- Plateforme / santé ---
api_router.include_router(platform_router)

# --- Features MVP ---
api_router.include_router(iam_router)  # /auth/*, /me        (Sprint 1)
api_router.include_router(scoring_router)  # /scoring/grid    (Sprint 2)
api_router.include_router(diagnostics_router)  # /diagnostics (Sprint 2)
api_router.include_router(reports_router)  # /reports         (Sprint 2)
api_router.include_router(academy_router)  # /academy/*       (Sprint 3)
api_router.include_router(documents_router)  # /documents/*   (Sprint 3)
api_router.include_router(opportunities_router)  # /opportunities/* (Sprint 3)
api_router.include_router(pitchsim_router)  # /pitchsim/*       (Sprint 4)
api_router.include_router(projects_owner_router)  # /projects/* — espace porteur unifié
api_router.include_router(projects_admin_router)  # /admin/projects/* (Sprint 5)
api_router.include_router(audit_router)  # /admin/audit-logs   (Sprint 5)
api_router.include_router(mentors_router)  # /mentors/*, /admin/mentor-applications/* (Sprint 5)
api_router.include_router(scoring_admin_router)  # /admin/scoring/grids/* (Sprint 5)
api_router.include_router(sharing_router)  # /projects/{id}/share, /shared/{token} (Sprint 5)
api_router.include_router(analytics_router)  # /admin/learning-dashboard (Sprint 6)
api_router.include_router(gdpr_router)  # /me/export, DELETE /me (Sprint 6)
api_router.include_router(jobs_admin_router)  # /admin/jobs/* (Sprint 6)
api_router.include_router(notifications_router)  # /notifications/* (V1-05)
api_router.include_router(opportunities_admin_router)  # /admin/opportunities/* (V1-06)
api_router.include_router(pitch_router)  # /pitch/* — éditeur (V1.2)
api_router.include_router(studio_router)  # /studio/* — logo & marque (V1.3)

# Sprints suivants (à monter quand prêts) :
#   from app.mentors.router import router as mentors_router          # Sprint 5
#   ...
