"""Parcours critique du porteur, bout en bout (router → service → repo → DB → worker).

Prouve le CÂBLAGE réel que les tests unitaires (purs) ne couvrent pas : DI, transactions,
mappings SQLAlchemy, sérialisation. LLM = mock déterministe ; PDF/MinIO absents → dégradation.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_register_diagnostic_to_bilan(client) -> None:
    # 1) Inscription porteur (alias `name`, consentement RGPD).
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": "Awa", "email": "awa@ideaxion.io", "password": "s3cret-pwd", "consent": True},
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2) Lancer le diagnostic (flow A guidé) — alias camelCase + `terrain`→field.
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
    assert created["diagnostic_status"] == "diagnostic_in_progress"
    assert created["review_status"] == "new_diagnostic"

    # 3) Traitement worker (appel direct du handler) : grille → N passes → consensus → bilan.
    from app.diagnostics.handlers import handle_run_diagnostic

    await handle_run_diagnostic(
        {
            "diagnostic_id": created["diagnostic_id"],
            "project_id": created["project_id"],
            "report_id": created["report_id"],
            "mode": "guided",
        }
    )

    # 4) Le porteur consulte son bilan (émet `bilan_viewed`).
    r = await client.get(f"/api/v1/reports/{created['report_id']}", headers=headers)
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["status"] == "ready"
    assert report["radar_score"] and len(report["radar_score"]["axes"]) == 12  # grille v2
    assert isinstance(report["next_actions"], list)  # routage déterministe
    assert report["report"] is not None  # couche structurée (mock)

    # Le score global est SERVI avec le radar, sur l'échelle unique /100 (SPEC C3) :
    # le client n'a plus rien à réagréger, donc plus rien à faire diverger.
    radar = report["radar_score"]
    assert 0 <= radar["overall"] <= 100
    assert set(radar["pillars"]) == {"sens", "viabilite", "scalabilite", "execution"}
    assert isinstance(radar["sectorCalibrated"], bool)

    # Même nombre en base, dans l'API et à l'écran — c'est le critère d'acceptation.
    assert report["comprehension"]["overall"] == radar["overall"]
    html = await client.get(f"/api/v1/reports/{created['report_id']}/html", headers=headers)
    assert html.status_code == 200, html.text
    assert f"{radar['overall']}/100" in html.text

    # 5) La liste des bilans du porteur contient le sien.
    r = await client.get("/api/v1/reports", headers=headers)
    assert r.status_code == 200
    assert any(item["id"] == created["report_id"] for item in r.json())


async def test_diagnostic_requires_auth(client) -> None:
    r = await client.post(
        "/api/v1/diagnostics",
        json={"projectName": "X", "sector": "finance", "description": "y" * 30, "consent": True},
    )
    assert r.status_code == 401


async def test_health_and_security_headers(client) -> None:
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] is True and body["checks"]["redis"] is True
    assert body["checks"]["minio"] is None  # non configuré en test → n'impacte pas la santé
    # En-têtes de sécurité (AUTH-04) présents sur toute réponse.
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
