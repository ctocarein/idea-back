"""Sprint 3 bout en bout : Academy, Opportunités, et garde-fou Documents.

Prouve le câblage réel (router → service → repo → DB) des modules du Sprint 3 sur le
Postgres de test, leçons + opportunités seedées par le conftest. LLM = mock déterministe.
"""

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


async def test_opportunities_eligibility_for_project(client) -> None:
    headers = await _register(client, "oppo@ideaxion.io")

    # Crée un projet + bilan READY via le flow diagnostic (donne un score au projet).
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
    assert r.status_code == 202, r.text
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

    # Liste des opportunités pour ce projet : éligibilité déterministe calculée.
    r = await client.get(f"/api/v1/opportunities?project_id={created['project_id']}", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()
    assert items, "le catalogue seedé doit renvoyer des opportunités"
    by_title = {o["title"]: o for o in items}
    # Opportunité ouverte (aucun critère) → toujours éligible.
    assert by_title["Programme Mentorat Ideaxion"]["eligible"] is True
    # Secteur agritech vs projet fintech → bloqué, raison explicite.
    agritech = by_title["Hackathon AgriTech"]
    assert agritech["eligible"] is False
    assert any("secteur" in m for m in agritech["missing"])
    # Les éligibles sont en tête de liste (orientation).
    assert items[0]["eligible"] is True

    # Expression d'intérêt → 204 (émet l'événement opportunity_interest).
    mentorat_id = by_title["Programme Mentorat Ideaxion"]["id"]
    r = await client.post(
        f"/api/v1/opportunities/{mentorat_id}/interest",
        headers=headers,
        json={"project_id": created["project_id"]},
    )
    assert r.status_code == 204, r.text


async def test_documents_upload_url_requires_storage(client) -> None:
    # MinIO désactivé en test → l'endpoint répond proprement (422) au lieu de planter.
    headers = await _register(client, "docs@ideaxion.io")
    r = await client.post(
        "/api/v1/documents/upload-url",
        headers=headers,
        json={"filename": "bp.pdf", "content_type": "application/pdf", "size": 2048},
    )
    assert r.status_code == 422, r.text
