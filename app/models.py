"""Agrégateur de modèles ORM.

Importer ce module garantit que TOUTES les tables sont enregistrées sur
`Base.metadata` — indispensable à l'autogénération Alembic et au seed.
Quand une feature ajoute des modèles, on l'importe ici.
"""

from __future__ import annotations

# Transverse
from app.academy.models import GuidedSession, NeedFiche  # noqa: F401
from app.audit.models import AuditLog  # noqa: F401

# Métier
from app.diagnostics.models import Diagnostic, DiagnosticDraft  # noqa: F401
from app.documents.models import Document  # noqa: F401

# IAM
from app.iam.invitations import Invitation  # noqa: F401
from app.iam.models import PermissionGrant, RefreshToken, User  # noqa: F401
from app.instrumentation.models import Event  # noqa: F401
from app.jobs.models import Job  # noqa: F401
from app.mentors.models import (  # noqa: F401
    MentorApplication,
    MentorProfile,
    MentorRequest,
)
from app.notifications.models import Notification  # noqa: F401
from app.opportunities.models import Opportunity  # noqa: F401
from app.pitch.models import Pitch  # noqa: F401
from app.pitchsim.models import (  # noqa: F401
    PitchDeck,
    PitchRubric,
    PitchRun,
    PitchSession,
    PitchSlide,
    PitchTurn,
)
from app.project_memory.models import ProjectDimensionState, ProjectMemoryItem  # noqa: F401
from app.projects.models import Project  # noqa: F401
from app.reports.models import Report  # noqa: F401
from app.scoring.models import ScoreRun, ScoringGrid  # noqa: F401
from app.sharing.models import ProjectShare  # noqa: F401
from app.studio.models import Logo  # noqa: F401

__all__ = [
    "AuditLog",
    "Diagnostic",
    "Document",
    "Event",
    "GuidedSession",
    "Invitation",
    "Job",
    "Logo",
    "MentorApplication",
    "MentorProfile",
    "MentorRequest",
    "NeedFiche",
    "Notification",
    "Opportunity",
    "PermissionGrant",
    "PitchDeck",
    "PitchRubric",
    "PitchRun",
    "PitchSession",
    "PitchSlide",
    "PitchTurn",
    "ProjectShare",
    "ProjectDimensionState",
    "ProjectMemoryItem",
    "Project",
    "Report",
    "RefreshToken",
    "ScoreRun",
    "ScoringGrid",
    "User",
]
