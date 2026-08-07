"""Primitives de sécurité — hash de mot de passe (argon2id), JWT, tokens d'invitation.

Aucune logique métier ici : seulement de la cryptographie et de l'encodage.
Jamais de mot de passe ni de token en clair en log ou en base.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

# Argon2id par défaut (paramètres recommandés de la lib). Instance unique réutilisée.
_password_hasher = PasswordHasher()

_JWT_ALGORITHM = "HS256"


# --- Mots de passe ---------------------------------------------------------


def hash_password(plain: str) -> str:
    # argon2id. Le sel est intégré au hash retourné.
    return _password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _password_hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def needs_rehash(hashed: str) -> bool:
    # Vrai si les paramètres argon2 ont évolué : on rehashe au prochain login réussi.
    return _password_hasher.check_needs_rehash(hashed)


# --- JWT (access token) ----------------------------------------------------


def create_access_token(*, subject: UUID, role: str) -> str:
    # Access token court (15 min). Porte uniquement `sub` et `role` ;
    # les permissions fines sont rechargées côté serveur (révocation immédiate possible).
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    # Lève jwt.PyJWTError si invalide/expiré ; le service traduit en UnauthenticatedError.
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[_JWT_ALGORITHM],
    )


# --- Token de vérification d'email (JWT dédié, stateless) ------------------


def create_email_token(subject: UUID) -> str:
    # Token de vérification (24 h). Purpose distinct de l'access → pas d'usage croisé.
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "purpose": "email_verify",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=24)).timestamp()),
    }
    return jwt.encode(payload, get_settings().jwt_secret.get_secret_value(), algorithm=_JWT_ALGORITHM)


def decode_email_token(token: str) -> UUID:
    # Lève jwt.PyJWTError si invalide/expiré, ValueError si mauvais purpose.
    payload = jwt.decode(token, get_settings().jwt_secret.get_secret_value(), algorithms=[_JWT_ALGORITHM])
    if payload.get("purpose") != "email_verify":
        raise ValueError("token de mauvais type")
    return UUID(payload["sub"])


# --- Tokens opaques (refresh, invitations) ---------------------------------


def generate_opaque_token() -> str:
    # Token aléatoire URL-safe. Sa version EN CLAIR n'existe que le temps de l'envoi.
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    # On ne stocke jamais un token en clair : seulement son hash SHA-256.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
