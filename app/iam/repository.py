"""Accès données IAM — users, permission_grants, refresh_tokens.

Une méthode = une intention de données. Le repository ne connaît ni le HTTP ni les
règles métier : il lit/écrit, c'est tout. Les transactions sont portées par le service.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.iam.models import AccountStatus, PermissionGrant, RefreshToken, Role, User
from app.iam.permissions import Permission


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str,
        role: Role,
        status: AccountStatus = AccountStatus.ACTIVE,
        consent_at: datetime | None = None,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            status=status,
            consent_at=consent_at,
        )
        self.session.add(user)
        await self.session.flush()  # peuple l'id sans committer (le service commit)
        return user

    async def update_password(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        await self.session.flush()

    async def load_grants(self, user_id: UUID) -> set[Permission]:
        # Charge les permissions explicites de l'utilisateur (en plus de son rôle).
        result = await self.session.execute(
            select(PermissionGrant.permission).where(PermissionGrant.user_id == user_id)
        )
        grants: set[Permission] = set()
        for raw in result.scalars():
            # Ignore silencieusement une permission inconnue (catalogue ayant évolué).
            try:
                grants.add(Permission(raw))
            except ValueError:
                continue
        return grants


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, *, user_id: UUID, token_hash: str, expires_at: datetime) -> RefreshToken:
        token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> None:
        token.revoked = True
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        # Détection de vol : on coupe toute la chaîne de refresh de l'utilisateur.
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        )
        for token in result.scalars():
            token.revoked = True
        await self.session.flush()
