"""Supervision des jobs (OPS-04) — liste, compteurs, relance (admin)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email: str) -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": "Awa", "email": email, "password": "s3cret-pwd", "consent": True},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _admin(email: str) -> dict:
    from app.core.database import get_session_factory
    from app.core.security import create_access_token, hash_password
    from app.iam.models import AccountStatus, Role
    from app.iam.repository import UserRepository

    async with get_session_factory()() as s:
        async with s.begin():
            u = await UserRepository(s).create(
                email=email,
                password_hash=hash_password("pw-123456"),
                full_name="Admin",
                role=Role.ADMIN,
                status=AccountStatus.ACTIVE,
            )
            uid = u.id
    return {"Authorization": f"Bearer {create_access_token(subject=uid, role='admin')}"}


async def test_jobs_supervision(client) -> None:
    founder = await _register(client, "awa-jobs@ideaxion.io")
    # Lancer un diagnostic enfile un job run_diagnostic.
    r = await client.post(
        "/api/v1/diagnostics",
        headers=founder,
        json={
            "projectName": "Tontine+",
            "sector": "fintech",
            "description": "Appli de tontine via mobile money, traçabilité et confiance.",
            "consent": True,
            "archetype": "terrain",
        },
    )
    assert r.status_code == 202, r.text

    admin = await _admin("admin-jobs@ideaxion.io")

    # Liste : le job du diagnostic est là.
    r = await client.get("/api/v1/admin/jobs", headers=admin)
    assert r.status_code == 200, r.text
    jobs = r.json()
    job = next(j for j in jobs if j["type"] == "run_diagnostic")

    # Compteurs par statut.
    r = await client.get("/api/v1/admin/jobs/stats", headers=admin)
    assert r.status_code == 200 and sum(r.json().values()) >= 1

    # Relance d'un job → repassé en file (pending).
    r = await client.post(f"/api/v1/admin/jobs/{job['id']}/retry", headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "pending"

    # Job inexistant → 404 ; un porteur n'a pas JOBS_MANAGE → 403.
    import uuid

    assert (await client.post(f"/api/v1/admin/jobs/{uuid.uuid4()}/retry", headers=admin)).status_code == 404
    assert (await client.get("/api/v1/admin/jobs", headers=founder)).status_code == 403
