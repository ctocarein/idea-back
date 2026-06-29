"""Dépendances FastAPI — câblage déclaratif de l'auth et des permissions.

Le router reste propre : toute la logique d'autorisation vit ici. Un check n'est jamais
juste « quel rôle ? » mais « quelle permission ET sur quelle ressource » (cf. guards).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.core.database import get_session
from app.core.errors import ForbiddenError, UnauthenticatedError
from app.core.security import decode_access_token
from app.iam.models import AccountStatus, Role, User
from app.iam.permissions import Permission, permissions_for
from app.iam.repository import RefreshTokenRepository, UserRepository
from app.iam.service import AuthService

# tokenUrl pointe vers la route de login (sert surtout à la doc OpenAPI/Swagger).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


@dataclass
class AuthContext:
    # Contexte d'authentification injecté dans les routes protégées.
    user: User
    permissions: set[Permission]


# --- Assemblage des services ----------------------------------------------


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    # Le service ne sait pas d'où viennent ses repos : on les assemble ici (testabilité).
    return AuthService(
        users=UserRepository(session),
        refresh_tokens=RefreshTokenRepository(session),
        auditor=AuditService(session),
    )


# --- Authentification ------------------------------------------------------


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> AuthContext:
    # Décode le JWT, charge l'utilisateur et ses permissions effectives (rechargées
    # côté serveur, pas figées dans le token → révocation immédiate possible).
    if not token:
        raise UnauthenticatedError()
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise UnauthenticatedError("Token invalide ou expiré.") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthenticatedError()

    users = UserRepository(session)
    user = await users.get_by_id(UUID(user_id))
    if user is None or user.status is not AccountStatus.ACTIVE:
        raise UnauthenticatedError()

    grants = await users.load_grants(user.id)
    return AuthContext(user=user, permissions=permissions_for(user, grants))


def require(*needed: Permission):
    # Fabrique une dépendance qui exige une ou plusieurs permissions.
    async def _checker(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        missing = set(needed) - ctx.permissions
        if missing:
            raise ForbiddenError(
                "Permissions insuffisantes.",
                details=[p.value for p in missing],
            )
        return ctx

    return _checker


# --- Garde-fous au niveau ressource (propriété) ---------------------------
#
# La permission dit *quel type d'action* ; le garde-fou dit *sur quelle instance*.
# Ces helpers sont appelés par les services des features (projects, reports…) une
# fois la ressource chargée. Exemple de référence pour les projets ci-dessous.


def guard_owner_access(*, owner_id: UUID, ctx: AuthContext) -> None:
    # Seul l'admin a un passe-droit global ; sinon il faut être le propriétaire.
    # SEC-02 : on teste le rôle explicitement — pas la permission PROJECT_READ_ANY
    # qui était accordée aux analystes et leur donnait un accès non voulu.
    if ctx.user.role is Role.ADMIN:
        return
    if owner_id == ctx.user.id:
        return
    raise ForbiddenError()


def guard_assigned_or_admin(*, assignee_id: UUID | None, ctx: AuthContext) -> None:
    # L'admin peut tout ; le mentor/analyste UNIQUEMENT le projet qui lui est assigné.
    # SEC-02 : même logique — rôle explicite, pas permission.
    if ctx.user.role is Role.ADMIN:
        return
    if Permission.MENTOR_REVIEW in ctx.permissions and assignee_id == ctx.user.id:
        return
    raise ForbiddenError("project")
