"""Fiche projet partageable B2B (OPP-02) — consentement, fiche publique, révocation."""

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


async def _project_with_report(client, headers) -> str:
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
    return created["project_id"]


async def test_share_consent_public_fiche_and_revoke(client) -> None:
    headers = await _register(client, "awa-share@ideaxion.io")
    pid = await _project_with_report(client, headers)

    # Sans consentement → refusé.
    r = await client.post(f"/api/v1/projects/{pid}/share", headers=headers, json={"consent": False})
    assert r.status_code == 422, r.text

    # Avec consentement → lien créé.
    r = await client.post(f"/api/v1/projects/{pid}/share", headers=headers, json={"consent": True})
    assert r.status_code == 201, r.text
    token = r.json()["token"]

    # Fiche publique (SANS authentification) = lecture jury/incubateur.
    r = await client.get(f"/api/v1/shared/{token}")
    assert r.status_code == 200, r.text
    fiche = r.json()
    assert fiche["project_title"] == "Tontine+"
    assert fiche["scored_by"] == "Ideaxion"
    assert isinstance(fiche["overall_100"], int)
    assert "summary" in fiche

    # Un autre utilisateur ne peut pas partager mon projet.
    other = await _register(client, "intrus-share@ideaxion.io")
    r = await client.post(f"/api/v1/projects/{pid}/share", headers=other, json={"consent": True})
    assert r.status_code == 403

    # Révocation par le porteur → la fiche n'est plus accessible.
    r = await client.delete(f"/api/v1/projects/{pid}/share", headers=headers)
    assert r.status_code == 204
    assert (await client.get(f"/api/v1/shared/{token}")).status_code == 404
