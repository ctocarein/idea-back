"""Orchestration OAuth — authorize → callback → exchange.

Design « code à usage unique » (le front n'échange qu'un `code`, jamais de jeton en clair
dans l'URL) :

1. `authorize` : on stocke le `redirect_uri` FRONT dans un `state` (Redis, opaque, à usage
   unique → anti-CSRF) et on renvoie vers le fournisseur avec le callback BACKEND.
2. `callback` (backend) : on valide le `state`, on parle au fournisseur, on crée/relie le
   compte, on émet un CODE À USAGE UNIQUE (Redis) puis on renvoie le navigateur vers le
   callback FRONT avec `?code=…` (ou `?error=…`).
3. `exchange` : le front échange ce code côté serveur → `TokenPair`. Un code « conflit »
   fait remonter un 409 (email déjà pris, non reliable automatiquement).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.core.security import generate_opaque_token, hash_password
from app.iam.models import AccountStatus, Role
from app.iam.oauth_providers import (
    OAuthIdentity,
    build_authorize_url,
    fetch_identity,
    is_configured,
)
from app.iam.repository import UserRepository
from app.iam.schemas import TokenPair
from app.iam.service import AuthService

_STATE_TTL = 600  # 10 min : le temps d'un aller-retour de consentement
_CODE_TTL = 300  # 5 min : le front échange le code juste après le retour


class OAuthService:
    def __init__(
        self,
        *,
        auth: AuthService,
        users: UserRepository,
        auditor: AuditService,
        redis: Redis,
        session: AsyncSession,
    ) -> None:
        self.auth = auth
        self.users = users
        self.auditor = auditor
        self.redis = redis
        self.session = session

    # --- 1. Entrée : URL de consentement du fournisseur -------------------

    async def build_authorize_redirect(self, provider: str, *, front_redirect_uri: str) -> str:
        if not is_configured(provider):
            raise NotFoundError("oauth_provider")
        self._assert_allowed_redirect(front_redirect_uri)

        state = generate_opaque_token()
        await self.redis.set(
            f"oauth:state:{state}",
            json.dumps({"provider": provider, "redirect_uri": front_redirect_uri}),
            ex=_STATE_TTL,
        )
        return build_authorize_url(provider, redirect_uri=self._backend_callback(provider), state=state)

    # --- 2. Retour fournisseur : renvoie l'URL FRONT à charger ------------

    async def handle_callback(
        self, provider: str, *, code: str | None, state: str | None, error: str | None
    ) -> str:
        raw_state = await self.redis.getdel(f"oauth:state:{state}") if state else None
        if raw_state is None:
            # `state` inconnu/expiré → on ne connaît pas la destination front : repli sur l'origine publique.
            return self._front_error(self._public_front_callback(), "oauth_failed")

        data = json.loads(raw_state)
        front_redirect = data["redirect_uri"]
        if data.get("provider") != provider:
            return self._front_error(front_redirect, "oauth_failed")
        if error:
            return self._front_error(front_redirect, "oauth_denied")
        if not code:
            return self._front_error(front_redirect, "oauth_failed")

        try:
            identity = await fetch_identity(
                provider, code=code, redirect_uri=self._backend_callback(provider)
            )
        except Exception:
            return self._front_error(front_redirect, "oauth_failed")

        kind, user_id = await self._resolve_account(provider, identity)
        one_time = generate_opaque_token()
        payload: dict[str, object]
        if kind == "user":
            payload = {"user_id": str(user_id)}
        elif kind == "conflict":
            payload = {"conflict": True}
        else:
            return self._front_error(front_redirect, "oauth_failed")

        await self.redis.set(f"oauth:code:{one_time}", json.dumps(payload), ex=_CODE_TTL)
        sep = "&" if "?" in front_redirect else "?"
        return f"{front_redirect}{sep}code={one_time}"

    # --- 3. Échange du code à usage unique contre un TokenPair ------------

    async def exchange(self, code: str) -> TokenPair:
        raw = await self.redis.getdel(f"oauth:code:{code}")
        if raw is None:
            raise ValidationAppError("Code OAuth invalide ou expiré.")
        payload = json.loads(raw)
        if payload.get("conflict"):
            raise ConflictError("Cet email est déjà associé à un compte existant.")
        user = await self.users.get_by_id(UUID(payload["user_id"]))
        if user is None:
            raise NotFoundError("user")
        return await self.auth.issue_tokens(user)

    # --- Résolution du compte (créer / relier / conflit) ------------------

    async def _resolve_account(
        self, provider: str, identity: OAuthIdentity
    ) -> tuple[str, UUID | None]:
        if not identity.email:
            return ("error", None)
        email = identity.email.lower()
        existing = await self.users.get_by_email(email)
        if existing is not None:
            # Liaison automatique uniquement si l'email est prouvé côté fournisseur ET le
            # compte est actif — sinon risque de détournement → on remonte un conflit.
            if not identity.email_verified or existing.status is not AccountStatus.ACTIVE:
                return ("conflict", None)
            return ("user", existing.id)

        # Création d'un porteur. Mot de passe aléatoire inutilisable (le compte se connecte
        # par OAuth) ; il pourra définir un mot de passe via « mot de passe oublié ».
        user = await self.users.create(
            email=email,
            password_hash=hash_password(generate_opaque_token()),
            full_name=identity.full_name,
            role=Role.FOUNDER,
            status=AccountStatus.ACTIVE,
            consent_at=datetime.now(UTC),
        )
        user.email_verified = identity.email_verified
        await self.auditor.record(
            actor_id=user.id,
            action="auth.oauth_registered",
            entity="user",
            entity_id=user.id,
            new_value={"provider": provider},
        )
        await self.session.commit()  # requête distincte de l'exchange → il faut persister ici
        return ("user", user.id)

    # --- Helpers ----------------------------------------------------------

    def _backend_callback(self, provider: str) -> str:
        base = get_settings().backend_base_url.rstrip("/")
        return f"{base}/api/v1/auth/oauth/{provider}/callback"

    def _public_front_callback(self) -> str:
        base = get_settings().public_base_url.rstrip("/")
        return f"{base}/api/auth/oauth/callback"

    def public_login_error(self, reason: str) -> str:
        """URL de login front porteuse d'une erreur — repli quand `authorize` échoue."""
        base = get_settings().public_base_url.rstrip("/")
        return f"{base}/login?error={reason}"

    def _front_error(self, front_url: str, reason: str) -> str:
        sep = "&" if "?" in front_url else "?"
        return f"{front_url}{sep}error={reason}"

    def _assert_allowed_redirect(self, redirect_uri: str) -> None:
        """Le redirect_uri front doit pointer vers une origine de confiance (anti open-redirect)."""
        settings = get_settings()
        allowed = {self._origin(o) for o in settings.cors_origins}
        allowed.add(self._origin(settings.public_base_url))
        if self._origin(redirect_uri) not in allowed:
            raise ValidationAppError("redirect_uri non autorisé.")

    @staticmethod
    def _origin(url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}"
