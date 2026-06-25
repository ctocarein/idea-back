"""Durcissement (OPS-02) — 401 (non authentifié) et 403 (permissions) exhaustifs.

Vérifie que toute la surface sensible exige une auth, et que le back-office est interdit au
porteur. Les en-têtes de sécurité (AUTH-04) sont vérifiés même sur une réponse d'erreur.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

# Routes protégées : sans token → 401.
PROTECTED_GET = [
    "/api/v1/admin/projects",
    "/api/v1/admin/audit-logs",
    "/api/v1/admin/learning-dashboard",
    "/api/v1/admin/jobs",
    "/api/v1/admin/jobs/stats",
    "/api/v1/admin/mentor-applications",
    "/api/v1/admin/scoring/grids",
    "/api/v1/reports",
    "/api/v1/mentors",
    "/api/v1/me/export",
]

# Back-office : un porteur (authentifié) → 403.
ADMIN_ONLY_GET = [
    "/api/v1/admin/projects",
    "/api/v1/admin/audit-logs",
    "/api/v1/admin/learning-dashboard",
    "/api/v1/admin/jobs",
    "/api/v1/admin/mentor-applications",
    "/api/v1/admin/scoring/grids",
]


async def _register(client, email: str) -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": "Awa", "email": email, "password": "s3cret-pwd", "consent": True},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_protected_routes_require_authentication(client) -> None:
    for path in PROTECTED_GET:
        r = await client.get(path)
        assert r.status_code == 401, f"{path} devrait exiger une auth (→ {r.status_code})"
        # En-têtes de sécurité présents même sur l'erreur.
        assert r.headers.get("x-content-type-options") == "nosniff"


async def test_back_office_forbidden_for_founder(client) -> None:
    headers = await _register(client, "awa-authz@ideaxion.io")
    for path in ADMIN_ONLY_GET:
        r = await client.get(path, headers=headers)
        assert r.status_code == 403, f"{path} devrait être interdit au porteur (→ {r.status_code})"


async def test_invalid_token_is_rejected(client) -> None:
    r = await client.get("/api/v1/me/export", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401
