"""Catalogue de permissions + matrice rôle → permissions par défaut.

Une permission est une chaîne `resource:action[:scope]`. Le catalogue est statique,
centralisé, exhaustif : aucune permission n'existe hors de cette liste.
Les permissions marquées [v2] sont définies mais non utilisées au MVP.
"""

from __future__ import annotations

from enum import Enum

from app.iam.models import Role, User


class Permission(str, Enum):
    # --- Projets & diagnostic (MVP) ---
    PROJECT_READ_OWN = "project:read:own"
    PROJECT_READ_ASSIGNED = "project:read:assigned"  # mentor : projets assignés
    PROJECT_READ_ANY = "project:read:any"  # admin
    PROJECT_WRITE_OWN = "project:write:own"
    PROJECT_TRANSITION = "project:transition"  # déclencher une transition de statut
    DIAGNOSTIC_RUN = "diagnostic:run"  # lancer un Radar de Collision
    REPORT_READ_OWN = "report:read:own"

    # --- Academy & simulateur (MVP) ---
    ACADEMY_READ = "academy:read"  # lire les modules
    ACADEMY_PROGRESS = "academy:progress"  # enregistrer sa progression
    PITCHSIM_RUN = "pitchsim:run"  # lancer / rejouer une session de pitch
    PITCH_EDIT = "pitch:edit"  # éditer son pitch (éditeur V1.2)
    STUDIO_EDIT = "studio:edit"  # générer / éditer ses assets de marque (Studio, V1.3)

    # --- Mentorat / certification ---
    MENTOR_REVIEW = "mentor:review"  # coacher / commenter un projet assigné
    CERTIFICATION_SIGN = "certification:sign"  # [v2] signature du mentor-certificateur

    # --- Investisseur (Club) ---
    DEALFLOW_READ = "dealflow:read"  # [v2] consulter les projets certifiés
    INTRO_REQUEST = "intro:request"  # [v2] demander une mise en relation

    # --- Administration ---
    USER_MANAGE = "user:manage"
    INVITATION_SEND = "invitation:send"  # inviter mentor / admin
    INVESTOR_APPROVE = "investor:approve"  # valider une candidature au Club
    MENTOR_APPROVE = "mentor:approve"  # valider un mentor auto-inscrit
    PERMISSION_GRANT = "permission:grant"  # accorder certification:sign, etc.
    AUDIT_READ = "audit:read"
    JOBS_MANAGE = "jobs:manage"
    OPPORTUNITY_MANAGE = "opportunity:manage"  # CRUD catalogue opportunités


# Permissions accordées d'office à chaque rôle. Tout le reste passe par PermissionGrant.
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.FOUNDER: {
        Permission.PROJECT_READ_OWN,
        Permission.PROJECT_WRITE_OWN,
        Permission.PROJECT_TRANSITION,
        Permission.DIAGNOSTIC_RUN,
        Permission.REPORT_READ_OWN,
        Permission.ACADEMY_READ,
        Permission.ACADEMY_PROGRESS,
        Permission.PITCHSIM_RUN,
        Permission.PITCH_EDIT,
        Permission.STUDIO_EDIT,
    },
    Role.MENTOR: {
        Permission.PROJECT_READ_ASSIGNED,
        Permission.MENTOR_REVIEW,
        # CERTIFICATION_SIGN n'est PAS ici : c'est un grant explicite (mentor-certificateur).
    },
    Role.ANALYST: {
        # Regard humain interne : lecture des projets ASSIGNÉS à l'analyste (pas de passe-droit global).
        Permission.PROJECT_READ_ASSIGNED,
        Permission.MENTOR_REVIEW,
    },
    Role.INVESTOR: {
        Permission.DEALFLOW_READ,  # [v2] effectif en v2
        Permission.INTRO_REQUEST,  # [v2]
    },
    Role.ADMIN: {
        # L'admin a tout. On l'exprime explicitement plutôt que par un wildcard,
        # pour que la matrice reste lisible et auditable.
        Permission.PROJECT_READ_ANY,
        Permission.USER_MANAGE,
        Permission.INVITATION_SEND,
        Permission.INVESTOR_APPROVE,
        Permission.MENTOR_APPROVE,
        Permission.PERMISSION_GRANT,
        Permission.AUDIT_READ,
        Permission.JOBS_MANAGE,
        Permission.OPPORTUNITY_MANAGE,
    },
}


def permissions_for(user: User, grants: set[Permission]) -> set[Permission]:
    # Permissions effectives = défauts du rôle UNION grants explicites.
    return ROLE_PERMISSIONS.get(user.role, set()) | grants
