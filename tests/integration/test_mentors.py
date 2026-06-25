"""Onboarding mentor (MENTOR-01) : candidature → approbation admin → activation → login."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _staff_headers(email: str, role) -> dict:
    from app.core.database import get_session_factory
    from app.core.security import create_access_token, hash_password
    from app.iam.models import AccountStatus
    from app.iam.repository import UserRepository

    async with get_session_factory()() as s:
        async with s.begin():
            u = await UserRepository(s).create(
                email=email,
                password_hash=hash_password("pw-123456"),
                full_name="Admin",
                role=role,
                status=AccountStatus.ACTIVE,
            )
            uid = u.id
    return {"Authorization": f"Bearer {create_access_token(subject=uid, role=role.value)}"}


async def test_mentor_onboarding_end_to_end(client) -> None:
    from app.iam.models import Role

    # 1) Candidature publique.
    r = await client.post(
        "/api/v1/mentors/apply",
        json={
            "full_name": "Koffi Mentor",
            "email": "koffi@ideaxion.io",
            "sectors": ["fintech"],
            "bio": "10 ans d'expérience en fintech.",
        },
    )
    assert r.status_code == 201, r.text
    app_id = r.json()["id"]
    assert r.json()["status"] == "pending"

    # 2) Admin : liste + approbation (crée le compte INVITED + invitation à token).
    admin = await _staff_headers("admin-mentor@ideaxion.io", Role.ADMIN)
    r = await client.get("/api/v1/admin/mentor-applications?status=pending", headers=admin)
    assert r.status_code == 200 and any(a["id"] == app_id for a in r.json())

    r = await client.post(f"/api/v1/admin/mentor-applications/{app_id}/approve", headers=admin)
    assert r.status_code == 200, r.text
    token = r.json()["invitation_token"]

    # Double approbation interdite.
    r = await client.post(f"/api/v1/admin/mentor-applications/{app_id}/approve", headers=admin)
    assert r.status_code == 422

    # 3) Le mentor active son compte (pose son mot de passe).
    r = await client.post(
        "/api/v1/mentors/accept-invitation",
        json={"token": token, "password": "mentor-pass-1"},
    )
    assert r.status_code == 204, r.text

    # 4) Il peut se connecter.
    r = await client.post("/api/v1/auth/login", json={"email": "koffi@ideaxion.io", "password": "mentor-pass-1"})
    assert r.status_code == 200, r.text
    assert r.json().get("access_token")

    # Un token d'invitation déjà utilisé est refusé.
    r = await client.post("/api/v1/mentors/accept-invitation", json={"token": token, "password": "autre-pass-9"})
    assert r.status_code == 422


async def test_mentor_applications_require_permission(client) -> None:
    # Un porteur n'a pas accès à la revue des candidatures.
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": "Awa", "email": "awa-mentor@ideaxion.io", "password": "s3cret-pwd", "consent": True},
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert (await client.get("/api/v1/admin/mentor-applications", headers=headers)).status_code == 403
