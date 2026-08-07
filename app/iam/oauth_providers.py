"""Fournisseurs d'identité OAuth/OIDC (Google, LinkedIn).

Le backend mène la danse : il détient les secrets, parle au fournisseur (échange du
code contre un jeton, puis lecture du `userinfo` OIDC) et normalise le résultat en une
`OAuthIdentity`. Aucun jeton fournisseur ne quitte cette couche.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings


@dataclass(frozen=True)
class ProviderMeta:
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str


# Endpoints OIDC. Google et LinkedIn exposent tous deux un `userinfo` standard
# (email + email_verified + name) — on s'appuie dessus plutôt que sur des API maison.
SUPPORTED: dict[str, ProviderMeta] = {
    "google": ProviderMeta(
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scope="openid email profile",
    ),
    "linkedin": ProviderMeta(
        authorize_url="https://www.linkedin.com/oauth/v2/authorization",
        token_url="https://www.linkedin.com/oauth/v2/accessToken",
        userinfo_url="https://api.linkedin.com/v2/userinfo",
        scope="openid profile email",
    ),
}


@dataclass(frozen=True)
class OAuthIdentity:
    email: str | None
    full_name: str
    email_verified: bool


def is_supported(provider: str) -> bool:
    return provider in SUPPORTED


def credentials(provider: str) -> tuple[str, str] | None:
    """(client_id, client_secret) si le fournisseur est configuré, sinon None."""
    settings = get_settings()
    pairs = {
        "google": (settings.google_client_id, settings.google_client_secret),
        "linkedin": (settings.linkedin_client_id, settings.linkedin_client_secret),
    }
    client_id, secret = pairs.get(provider, (None, None))
    if not client_id or secret is None:
        return None
    return client_id, secret.get_secret_value()


def is_configured(provider: str) -> bool:
    return is_supported(provider) and credentials(provider) is not None


def build_authorize_url(provider: str, *, redirect_uri: str, state: str) -> str:
    """URL de consentement du fournisseur (le `redirect_uri` est le callback BACKEND)."""
    meta = SUPPORTED[provider]
    creds = credentials(provider)
    assert creds is not None  # garanti par is_configured en amont
    client_id, _ = creds
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": meta.scope,
        "state": state,
    }
    return f"{meta.authorize_url}?{urlencode(params)}"


async def fetch_identity(provider: str, *, code: str, redirect_uri: str) -> OAuthIdentity:
    """Échange le code fournisseur contre un jeton, puis lit le `userinfo` OIDC."""
    meta = SUPPORTED[provider]
    creds = credentials(provider)
    assert creds is not None
    client_id, client_secret = creds

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_res = await client.post(
            meta.token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Accept": "application/json"},
        )
        token_res.raise_for_status()
        access_token = token_res.json().get("access_token")
        if not access_token:
            raise ValueError("no access_token in provider response")

        info_res = await client.get(
            meta.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        info_res.raise_for_status()
        info = info_res.json()

    email = info.get("email")
    # `email_verified` peut arriver en bool ou en chaîne "true" selon le fournisseur.
    raw_verified = info.get("email_verified", False)
    email_verified = raw_verified is True or str(raw_verified).lower() == "true"
    full_name = info.get("name") or (email.split("@")[0] if email else "Nouveau porteur")
    return OAuthIdentity(email=email, full_name=full_name, email_verified=email_verified)
