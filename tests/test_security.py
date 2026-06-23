"""Tests des primitives de sécurité — hash mot de passe, round-trip JWT, hash de token."""

from __future__ import annotations

from uuid import uuid4

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("s3cret-passw0rd")
    assert hashed != "s3cret-passw0rd"  # jamais en clair
    assert verify_password("s3cret-passw0rd", hashed)
    assert not verify_password("mauvais", hashed)


def test_access_token_roundtrip() -> None:
    user_id = uuid4()
    token = create_access_token(subject=user_id, role="founder")
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "founder"


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(subject=uuid4(), role="admin")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token + "tampered")


def test_token_hash_is_deterministic_and_opaque() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != "abc"
