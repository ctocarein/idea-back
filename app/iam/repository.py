"""Accès données IAM — users, permission_grants, refresh_tokens.

Une méthode = une intention de données. Le repository ne connaît ni le HTTP ni les
règles métier : il lit/écrit, c'est tout. Les transactions sont portées par le service.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
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
        language: str = "fr",
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            status=status,
            consent_at=consent_at,
            language=language,
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

    async def consume_if_active(self, token_hash: str) -> tuple[UUID, datetime] | None:
        """Révoque atomiquement le token si non-révoqué et retourne (user_id, expires_at).

        SEC-03 : l'UPDATE conditionnel (WHERE revoked=False) est atomique — deux requêtes
        concurrentes ne peuvent pas obtenir toutes les deux une ligne. Retourne None si le
        token est inconnu ou déjà révoqué (rejoué).
        """
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .where(RefreshToken.revoked.is_(False))
            .values(revoked=True)
            .returning(RefreshToken.user_id, RefreshToken.expires_at)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return (row.user_id, row.expires_at)

    async def find_user_id_by_hash(self, token_hash: str) -> UUID | None:
        """Retrouve le user_id d'un token même révoqué — pour détecter les replays."""
        result = await self.session.execute(
            select(RefreshToken.user_id).where(RefreshToken.token_hash == token_hash)
        )
        row = result.one_or_none()
        return row.user_id if row else None

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
