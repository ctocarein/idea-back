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


async def test_academy_lessons_progress_and_guided_build(client) -> None:
    headers = await _register(client, "academy@ideaxion.io")

    # 1) Catalogue de leçons (seedé) + filtre par topic (résolution d'un next_action).
    r = await client.get("/api/v1/academy/lessons", headers=headers)
    assert r.status_code == 200, r.text
    assert len(r.json()) >= 6
    r = await client.get("/api/v1/academy/lessons?topic=modele_economique", headers=headers)
    assert r.status_code == 200
    lessons = r.json()
    assert len(lessons) == 1 and lessons[0]["topic"] == "modele_economique"
    slug = lessons[0]["slug"]

    # 2) Détail d'une leçon (corps présent).
    r = await client.get(f"/api/v1/academy/lessons/{slug}", headers=headers)
    assert r.status_code == 200 and r.json()["body"]

    # 3) Compléter la leçon → progression persistée (idempotent).
    r = await client.post(f"/api/v1/academy/lessons/{slug}/complete", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["completed_count"] == 1
    await client.post(f"/api/v1/academy/lessons/{slug}/complete", headers=headers)  # rejoue
    r = await client.get("/api/v1/academy/progress", headers=headers)
    assert r.json()["completed_count"] == 1  # pas de doublon

    # 4) Construire guidé : l'IA répond (coach), le porteur écrit le brouillon.
    r = await client.post("/api/v1/academy/build/start", headers=headers, json={"section": "modele_economique"})
    assert r.status_code == 200, r.text
    session_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/academy/build/{session_id}/turn",
        headers=headers,
        json={"message": "Comment formuler mon modèle ?"},
    )
    assert r.status_code == 200, r.text
    turns = r.json()["turns"]
    assert len(turns) == 2 and turns[1]["role"] == "coach"

    r = await client.patch(
        f"/api/v1/academy/build/{session_id}/draft",
        headers=headers,
        json={"draft": "Commission de 2% sur les transactions."},
    )
    assert r.status_code == 200 and "Commission" in r.json()["draft"]


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
