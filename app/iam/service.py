"""Service IAM — register, login, refresh, logout.

Porte les règles métier et les transactions. Le refresh token est rotatif : chaque
usage en émet un nouveau et révoque l'ancien ; la réutilisation d'un token déjà
consommé révoque toute la chaîne (détection de vol).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.audit.service import AuditService
from app.core.config import get_settings
from app.core.email import asend_verification_email
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, RateLimitError, UnauthenticatedError
from app.core.ratelimit import RateLimiter
from app.core.security import (
    create_access_token,
    create_email_token,
    decode_email_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)
from app.iam.models import AccountStatus, ProfessionalStatus, ProjectStage, Role, User, WeeklyAvailability
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

    async def register(self, *, email: str, password: str, full_name: str, language: str = "fr") -> TokenPair:
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
            language=language,
        )
        await self.auditor.record(
            actor_id=user.id,
            action="auth.registered",
            entity="user",
            entity_id=user.id,
            new_value={"consent_at": consent_at.isoformat()},
        )
        # user + audit + refresh token sont commités ensemble (atomique).
        tokens = await self._issue_tokens(user)
        # Email de vérification (best-effort, hors transaction ; ne bloque pas l'inscription).
        # `asend_*` : le dialogue SMTP part dans un thread — sinon il gèle la boucle,
        # et donc toutes les autres requêtes, jusqu'à 10 s par inscription.
        await asend_verification_email(
            to=user.email, name=user.full_name, token=create_email_token(user.id), lang=user.language
        )
        return tokens

    async def verify_email(self, token: str) -> None:
        """Consomme un lien de vérification → marque l'email comme vérifié."""
        try:
            user_id = decode_email_token(token)
        except (jwt.PyJWTError, ValueError, KeyError):
            raise BusinessRuleError("Lien de vérification invalide ou expiré.") from None
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("user")
        if not user.email_verified:
            user.email_verified = True
            await self.session.commit()

    async def resend_verification(self, user_id: UUID) -> None:
        """Renvoie un lien de vérification (idempotent : rien si déjà vérifié)."""
        user = await self.users.get_by_id(user_id)
        if user is None or user.email_verified:
            return
        await asend_verification_email(
            to=user.email, name=user.full_name, token=create_email_token(user.id), lang=user.language
        )

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

        # SEC-03 : revocation atomique (UPDATE WHERE revoked=False RETURNING …).
        # Deux requêtes concurrentes ne peuvent pas toutes les deux obtenir une ligne →
        # pas de race condition sur la rotation.
        row = await self.refresh_tokens.consume_if_active(token_hash)
        if row is None:
            # Token inexistant ou déjà révoqué → replay probable.
            user_id = await self.refresh_tokens.find_user_id_by_hash(token_hash)
            if user_id is not None:
                await self.refresh_tokens.revoke_all_for_user(user_id)
                await self.session.commit()
                raise UnauthenticatedError("Refresh token réutilisé : session révoquée.")
            raise UnauthenticatedError("Refresh token invalide.")

        user_id, expires_at = row
        if expires_at < datetime.now(UTC):
            raise UnauthenticatedError("Refresh token expiré.")

        user = await self.users.get_by_id(user_id)
        if user is None or user.status is not AccountStatus.ACTIVE:
            raise UnauthenticatedError("Compte non actif.")

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

    async def update_me(self, user: User, *, full_name: str | None, language: str | None = None) -> User:
        changed = False
        if full_name is not None:
            user.full_name = full_name
            changed = True
        if language is not None:
            user.language = language
            changed = True
        if changed:
            await self.session.commit()
        return user

    async def complete_onboarding(
        self,
        user: User,
        *,
        country: str,
        city: str | None,
        professional_status: ProfessionalStatus,
        project_stage: ProjectStage,
        weekly_availability: WeeklyAvailability | None,
    ) -> User:
        user.country = country
        user.city = city
        user.professional_status = professional_status
        user.project_stage = project_stage
        user.weekly_availability = weekly_availability
        user.onboarding_completed = True
        await self.session.commit()
        return user

    async def update_profile(self, user: User, data) -> User:
        # Mise à jour partielle du profil porteur (sans modifier onboarding_completed).
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await self.session.commit()
        return user

    # --- Helpers internes --------------------------------------------------

    async def issue_tokens(self, user: User) -> TokenPair:
        """Émet un TokenPair pour un compte déjà authentifié (ex. retour OAuth)."""
        return await self._issue_tokens(user)

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
