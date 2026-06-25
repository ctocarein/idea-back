"""Tableau de bord d'apprentissage (INSTRUM-01) — funnel de transformation agrégé."""

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


async def test_learning_dashboard_aggregates_funnel(client) -> None:
    headers = await _register(client, "awa-instr@ideaxion.io")
    r = await client.post(
        "/api/v1/diagnostics",
        headers=headers,
        json={
            "projectName": "Tontine+",
            "sector": "fintech",
            "description": "Appli de tontine via mobile money, traçabilité et confiance.",
            "consent": True,
            "archetype": "terrain",
        },
    )
    created = r.json()
    from app.diagnostics.handlers import handle_run_diagnostic

    await handle_run_diagnostic(
        {
            "diagnostic_id": created["diagnostic_id"],
            "project_id": created["project_id"],
            "report_id": created["report_id"],
            "mode": "guided",
        }
    )
    pid = created["project_id"]

    # 1) Le porteur consulte son bilan → événement bilan_viewed.
    assert (await client.get(f"/api/v1/reports/{created['report_id']}", headers=headers)).status_code == 200

    # 2) Il exprime un intérêt pour une opportunité → opportunity_interest.
    opps = (await client.get(f"/api/v1/opportunities?project_id={pid}", headers=headers)).json()
    mentorat = next(o for o in opps if o["title"] == "Programme Mentorat Ideaxion")
    r = await client.post(f"/api/v1/opportunities/{mentorat['id']}/interest", headers=headers, json={"project_id": pid})
    assert r.status_code == 204

    # 3) L'admin lit le tableau de bord d'apprentissage.
    r = await client.get("/api/v1/admin/learning-dashboard", headers=await _admin("admin-instr@ideaxion.io"))
    assert r.status_code == 200, r.text
    dash = r.json()
    assert dash["total_events"] >= 2
    assert dash["event_counts"].get("bilan_viewed", 0) >= 1
    assert dash["event_counts"].get("opportunity_interest", 0) >= 1
    stages = [s["stage"] for s in dash["funnel"]]
    assert stages == ["bilan_viewed", "action_started", "opportunity_interest"]
    assert dash["funnel"][0]["conversion"] == 1.0  # base du funnel

    # Un porteur n'a pas accès au tableau de bord.
    assert (await client.get("/api/v1/admin/learning-dashboard", headers=headers)).status_code == 403
