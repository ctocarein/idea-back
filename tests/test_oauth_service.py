"""Service OAuth — échange du code à usage unique, résolution de compte, garde redirect.

Tests unitaires purs (fakes) : ni réseau fournisseur, ni Redis, ni DB réels.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.errors import ConflictError, ValidationAppError
from app.iam.models import AccountStatus
from app.iam.oauth_providers import OAuthIdentity
from app.iam.oauth_service import OAuthService
from app.iam.schemas import TokenPair


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def getdel(self, key: str) -> str | None:
        return self.store.pop(key, None)


class FakeUsers:
    def __init__(self, by_email: dict | None = None, by_id: dict | None = None) -> None:
        self._by_email = by_email or {}
        self._by_id = by_id or {}
        self.created: list = []

    async def get_by_email(self, email: str):
        return self._by_email.get(email)

    async def get_by_id(self, uid):
        return self._by_id.get(uid)

    async def create(self, **kwargs):
        user = SimpleNamespace(id=uuid4(), email_verified=False, **kwargs)
        self.created.append(user)
        return user


class FakeAuth:
    def __init__(self) -> None:
        self.issued_for = None

    async def issue_tokens(self, user) -> TokenPair:
        self.issued_for = user
        return TokenPair(access_token="access", refresh_token="refresh")


class FakeAuditor:
    def __init__(self) -> None:
        self.records: list = []

    async def record(self, **kwargs) -> None:
        self.records.append(kwargs)


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


def _service(users: FakeUsers | None = None):
    return OAuthService(
        auth=FakeAuth(),
        users=users or FakeUsers(),
        auditor=FakeAuditor(),
        redis=FakeRedis(),
        session=FakeSession(),
    )


class TestExchange:
    @pytest.mark.asyncio
    async def test_code_valide_emet_un_tokenpair(self) -> None:
        uid = uuid4()
        user = SimpleNamespace(id=uid)
        svc = _service(FakeUsers(by_id={uid: user}))
        svc.redis.store["oauth:code:C1"] = json.dumps({"user_id": str(uid)})

        tokens = await svc.exchange("C1")

        assert tokens.access_token == "access"
        assert svc.auth.issued_for is user
        # Code consommé (usage unique).
        assert "oauth:code:C1" not in svc.redis.store

    @pytest.mark.asyncio
    async def test_code_de_conflit_remonte_409(self) -> None:
        svc = _service()
        svc.redis.store["oauth:code:C2"] = json.dumps({"conflict": True})
        with pytest.raises(ConflictError):
            await svc.exchange("C2")

    @pytest.mark.asyncio
    async def test_code_inconnu_remonte_400(self) -> None:
        svc = _service()
        with pytest.raises(ValidationAppError):
            await svc.exchange("nope")


class TestResolveAccount:
    @pytest.mark.asyncio
    async def test_email_verifie_existant_est_relie(self) -> None:
        existing = SimpleNamespace(id=uuid4(), status=AccountStatus.ACTIVE)
        svc = _service(FakeUsers(by_email={"a@ex.com": existing}))
        kind, uid = await svc._resolve_account(
            "google", OAuthIdentity(email="a@ex.com", full_name="A", email_verified=True)
        )
        assert (kind, uid) == ("user", existing.id)
        assert svc.users.created == []  # relié, pas recréé

    @pytest.mark.asyncio
    async def test_email_non_verifie_sur_compte_existant_est_conflit(self) -> None:
        existing = SimpleNamespace(id=uuid4(), status=AccountStatus.ACTIVE)
        svc = _service(FakeUsers(by_email={"a@ex.com": existing}))
        kind, uid = await svc._resolve_account(
            "google", OAuthIdentity(email="a@ex.com", full_name="A", email_verified=False)
        )
        assert (kind, uid) == ("conflict", None)

    @pytest.mark.asyncio
    async def test_sans_email_est_une_erreur(self) -> None:
        svc = _service()
        kind, uid = await svc._resolve_account(
            "google", OAuthIdentity(email=None, full_name="A", email_verified=True)
        )
        assert (kind, uid) == ("error", None)

    @pytest.mark.asyncio
    async def test_nouvel_email_cree_un_porteur_et_commite(self) -> None:
        svc = _service(FakeUsers())
        kind, uid = await svc._resolve_account(
            "google", OAuthIdentity(email="New@Ex.com", full_name="New", email_verified=True)
        )
        assert kind == "user"
        assert len(svc.users.created) == 1
        created = svc.users.created[0]
        assert created.email == "new@ex.com"  # normalisé en minuscules
        assert created.email_verified is True
        assert svc.session.committed is True


class TestRedirectGuard:
    def test_origine_de_confiance_passe(self) -> None:
        svc = _service()
        # public_base_url par défaut = http://localhost:3000 (cf. conftest).
        svc._assert_allowed_redirect("http://localhost:3000/api/auth/oauth/callback")

    def test_origine_etrangere_est_rejetee(self) -> None:
        svc = _service()
        with pytest.raises(ValidationAppError):
            svc._assert_allowed_redirect("http://evil.example/api/auth/oauth/callback")
