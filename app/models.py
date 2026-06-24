"""Agrégateur de modèles ORM.

Importer ce module garantit que TOUTES les tables sont enregistrées sur
`Base.metadata` — indispensable à l'autogénération Alembic et au seed.
Quand une feature ajoute des modèles, on l'importe ici.
"""

from __future__ import annotations

# Transverse
from app.academy.models import GuidedSession, LearningProgress, Lesson  # noqa: F401
from app.audit.models import AuditLog  # noqa: F401

# Métier
from app.diagnostics.models import Diagnostic  # noqa: F401
from app.documents.models import Document  # noqa: F401

# IAM
from app.iam.invitations import Invitation  # noqa: F401
from app.iam.models import PermissionGrant, RefreshToken, User  # noqa: F401
from app.instrumentation.models import Event  # noqa: F401
from app.jobs.models import Job  # noqa: F401
from app.opportunities.models import Opportunity  # noqa: F401
from app.projects.models import Project  # noqa: F401
from app.reports.models import Report  # noqa: F401
from app.scoring.models import ScoreRun, ScoringGrid  # noqa: F401

__all__ = [
    "AuditLog",
    "Diagnostic",
    "Document",
    "Event",
    "GuidedSession",
    "Invitation",
    "Job",
    "LearningProgress",
    "Lesson",
    "Opportunity",
    "PermissionGrant",
    "Project",
    "Report",
    "RefreshToken",
    "ScoreRun",
    "ScoringGrid",
    "User",
]
