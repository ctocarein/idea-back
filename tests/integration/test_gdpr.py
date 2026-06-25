"""Conformité RGPD (OPS-03) — export des données + effacement (droit à l'oubli)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

EMAIL = "awa-rgpd@ideaxion.io"


async def _register(client, email: str) -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": "Awa", "email": email, "password": "s3cret-pwd", "consent": True},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_export_then_delete_account(client) -> None:
    headers = await _register(client, EMAIL)
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

    # Export : portabilité de toutes les données du porteur.
    r = await client.get("/api/v1/me/export", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["account"]["email"] == EMAIL
    assert data["projects"] and data["reports"]

    # Effacement du compte.
    assert (await client.delete("/api/v1/me", headers=headers)).status_code == 204

    # Le token ne fonctionne plus (compte supprimé).
    assert (await client.get("/api/v1/me/export", headers=headers)).status_code == 401

    # L'email est libéré → preuve de l'effacement (cascade SQL).
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": "Nouvelle", "email": EMAIL, "password": "s3cret-pwd", "consent": True},
    )
    assert r.status_code == 201, r.text
