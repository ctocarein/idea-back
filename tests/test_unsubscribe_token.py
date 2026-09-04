"""Token de désabonnement — signé, sans expiration, à usage cloisonné."""

from __future__ import annotations

from uuid import uuid4

import pytest
from jwt import PyJWTError

from app.core.security import (
    create_email_token,
    create_unsubscribe_token,
    decode_email_token,
    decode_unsubscribe_token,
)


def test_roundtrip() -> None:
    user_id = uuid4()
    assert decode_unsubscribe_token(create_unsubscribe_token(user_id)) == user_id


def test_never_expires() -> None:
    """Un lien de désabonnement doit marcher tant que le mail existe dans la boîte.

    Un lien expiré équivaudrait à ne pas en avoir — et un désabonnement qui échoue se
    transforme en signalement pour spam, ce qui coûte la délivrabilité de TOUS les envois.
    """
    import jwt

    payload = jwt.decode(create_unsubscribe_token(uuid4()), options={"verify_signature": False})
    assert "exp" not in payload


def test_purposes_are_not_interchangeable() -> None:
    # Un token de vérification d'email ne doit jamais désabonner, et réciproquement.
    user_id = uuid4()
    with pytest.raises(ValueError):
        decode_unsubscribe_token(create_email_token(user_id))
    with pytest.raises(ValueError):
        decode_email_token(create_unsubscribe_token(user_id))


def test_tampered_token_is_rejected() -> None:
    token = create_unsubscribe_token(uuid4())
    with pytest.raises(PyJWTError):
        decode_unsubscribe_token(token[:-4] + "aaaa")
    with pytest.raises(PyJWTError):
        decode_unsubscribe_token("pas-un-token")
