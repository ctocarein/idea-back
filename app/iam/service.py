"""Service IAM — register, login, refresh, logout.

Porte les règles métier et les transactions. Le refresh token est rotatif : chaque
usage en émet un nouveau et révoque l'ancien ; la réutilisation d'un token déjà
consommé révoque toute la chaîne (détection de vol).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.audit.service import AuditService
from app.core.config import get_settings
from app.core.errors import ConflictError, RateLimitError, UnauthenticatedError
from app.core.ratelimit import RateLimiter
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)
from app.iam.models import AccountStatus, Role, User
from app.iam.permissions import permissions_for
from app.iam.repository import RefreshTokenRepository, UserRepository
from app.iam.schemas import MeOut, TokenPair, UserOut


class AuthService:
    def __init__(
        self,
        *,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        auditor: AuditService,
    ) -> None:
        self.users = users
        self.refresh_tokens = refresh_tokens
        self.auditor = auditor
        self.session = users.session  # même AsyncSession pour porter la transaction

    # --- Inscription / connexion ------------------------------------------

    async def register(self, *, email: str, password: str, full_name: str) -> TokenPair:
        # Un porteur s'inscrit librement (rôle founder, actif d'emblée).
        # NB transactions : on s'appuie sur l'autobegin de la session + un commit unique
        # (porté par _issue_tokens). On n'utilise PAS session.begin() car la session de
        # requête a déjà une transaction ouverte (lectures de get_current_user / vérifs).
        existing = await self.users.get_by_email(email)
        if existing is not None:
            raise ConflictError("Cet email est déjà utilisé.")

        # Le consentement RGPD est garanti `true` par RegisterIn ; on l'horodate ici
        # pour en garder une trace opposable (purge/cascade gérées par l'épic RGPD).
        consent_at = datetime.now(UTC)
        user = await self.users.create(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=Role.FOUNDER,
            status=AccountStatus.ACTIVE,
            consent_at=consent_at,
        )
        await self.auditor.record(
            actor_id=user.id,
            action="auth.registered",
            entity="user",
            entity_id=user.id,
            new_value={"consent_at": consent_at.isoformat()},
        )
        # user + audit + refresh token sont commités ensemble (atomique).
        return await self._issue_tokens(user)

    async def login(self, *, email: str, password: str) -> TokenPair:
        # Anti brute-force ciblé : 5 tentatives / 15 min par email (en plus de la limite IP).
        email_limiter = RateLimiter(scope="auth_login_email", limit=5, window_seconds=900)
        if not await email_limiter.allow(email.lower()):
            raise RateLimitError("Trop de tentatives sur ce compte. Réessaie dans 15 minutes.")

        user = await self.users.get_by_email(email)
        # Message volontairement générique : on ne révèle pas si l'email existe.
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthenticatedError("Identifiants invalides.")
        if user.status is not AccountStatus.ACTIVE:
            raise UnauthenticatedError("Compte non actif.")

        # Rehash transparent si les paramètres argon2 ont évolué (persisté au commit final).
        if needs_rehash(user.password_hash):
            await self.users.update_password(user, hash_password(password))

        return await self._issue_tokens(user)

    # --- Rotation du refresh / logout -------------------------------------

    async def refresh(self, *, refresh_token: str) -> TokenPair:
        token_hash = hash_token(refresh_token)
        stored = await self.refresh_tokens.get_by_hash(token_hash)

        if stored is None:
            raise UnauthenticatedError("Refresh token invalide.")

        # Token déjà consommé/révoqué et rejoué → vol probable : on coupe toute la chaîne.
        # La révocation DOIT être persistée AVANT de lever l'erreur (commit explicite).
        if stored.revoked:
            await self.refresh_tokens.revoke_all_for_user(stored.user_id)
            await self.session.commit()
            raise UnauthenticatedError("Refresh token réutilisé : session révoquée.")

        if stored.expires_at < datetime.now(UTC):
            raise UnauthenticatedError("Refresh token expiré.")

        user = await self.users.get_by_id(stored.user_id)
        if user is None or user.status is not AccountStatus.ACTIVE:
            raise UnauthenticatedError("Compte non actif.")

        await self.refresh_tokens.revoke(stored)  # rotation : l'ancien meurt
        # rotation + émission du nouveau token commités ensemble.
        return await self._issue_tokens(user)

    async def logout(self, *, refresh_token: str) -> None:
        token_hash = hash_token(refresh_token)
        stored = await self.refresh_tokens.get_by_hash(token_hash)
        if stored is None or stored.revoked:
            return  # logout idempotent
        await self.refresh_tokens.revoke(stored)
        await self.session.commit()

    # --- /me ---------------------------------------------------------------

    async def me(self, user: User) -> MeOut:
        grants = await self.users.load_grants(user.id)
        perms = permissions_for(user, grants)
        return MeOut(
            user=UserOut.model_validate(user),
            permissions=sorted(p.value for p in perms),
        )

    async def update_me(self, user: User, *, full_name: str | None) -> User:
        if full_name is not None:
            user.full_name = full_name
            await self.session.commit()
        return user

    # --- Helpers internes --------------------------------------------------

    async def _issue_tokens(self, user: User) -> TokenPair:
        # Émet l'access token + un refresh rotatif, et COMMITE la transaction courante
        # (incluant toute écriture en attente : création user, audit, rehash, rotation).
        settings = get_settings()
        access = create_access_token(subject=user.id, role=user.role.value)

        raw_refresh = generate_opaque_token()
        expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)
        await self.refresh_tokens.add(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=expires_at,
        )
        await self.session.commit()
        return TokenPair(access_token=access, refresh_token=raw_refresh)

    async def effective_permissions(self, user_id: UUID) -> set[str]:
        user = await self.users.get_by_id(user_id)
        if user is None:
            return set()
        grants = await self.users.load_grants(user_id)
        return {p.value for p in permissions_for(user, grants)}
