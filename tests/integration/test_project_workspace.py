"""Espace projet propriétaire : agrégation et mémoire immuable."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_owner_workspace_and_versioned_memory(client) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Aminata",
            "email": "aminata.workspace@ideaxion.io",
            "password": "s3cret-pwd",
            "consent": True,
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.post(
        "/api/v1/diagnostics",
        headers=headers,
        json={
            "projectName": "Marché Frais",
            "sector": "agritech",
            "description": "Une place de marché locale qui relie les maraîchers aux restaurants urbains.",
            "consent": True,
        },
    )
    assert response.status_code == 202, response.text
    project_id = response.json()["project_id"]

    response = await client.get("/api/v1/projects", headers=headers)
    assert response.status_code == 200
    assert response.json()[0]["id"] == project_id

    payload = {
        "dimension": "d1",
        "item_type": "declaration",
        "statement": "Les restaurateurs perdent du temps à appeler plusieurs fournisseurs.",
        "deduplication_key": "problem-v1",
    }
    response = await client.post(f"/api/v1/projects/{project_id}/memory", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    first = response.json()
    assert first["evidence_state"] == "declared"
    assert first["provenance_type"] == "user_answer"

    response = await client.post(f"/api/v1/projects/{project_id}/memory", headers=headers, json=payload)
    assert response.status_code == 201
    assert response.json()["id"] == first["id"]

    response = await client.post(
        f"/api/v1/projects/{project_id}/memory",
        headers=headers,
        json={
            "dimension": "d1",
            "item_type": "fact",
            "statement": "Huit restaurateurs interrogés décrivent ce problème chaque semaine.",
            "supersedes_id": first["id"],
        },
    )
    assert response.status_code == 201, response.text
    second = response.json()
    assert second["supersedes_id"] == first["id"]

    response = await client.get(f"/api/v1/projects/{project_id}/memory", headers=headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [second["id"]]

    response = await client.get(f"/api/v1/projects/{project_id}/workspace", headers=headers)
    assert response.status_code == 200, response.text
    workspace = response.json()
    assert workspace["project"]["id"] == project_id
    assert workspace["memory"]["total_active"] == 1
    assert workspace["memory"]["by_dimension"] == {"d1": 1}

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Moussa",
            "email": "moussa.workspace@ideaxion.io",
            "password": "s3cret-pwd",
            "consent": True,
        },
    )
    assert response.status_code == 201
    other_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.get(f"/api/v1/projects/{project_id}/workspace", headers=other_headers)
    assert response.status_code == 403
    response = await client.post(
        f"/api/v1/projects/{project_id}/memory",
        headers=other_headers,
        json={"dimension": "d1", "statement": "Je ne dois pas pouvoir écrire ici."},
    )
    assert response.status_code == 403


async def test_owner_evaluation_separates_score_confidence_evidence_and_questions(client) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Fatou",
            "email": "fatou.evaluation@ideaxion.io",
            "password": "s3cret-pwd",
            "consent": True,
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.post(
        "/api/v1/diagnostics",
        headers=headers,
        json={
            "projectName": "Solaire Quartier",
            "sector": "cleantech",
            "description": "Des kits solaires partagés pour les petits commerces de quartier.",
            "consent": True,
        },
    )
    assert response.status_code == 202, response.text
    created = response.json()

    from app.diagnostics.handlers import handle_run_diagnostic

    await handle_run_diagnostic(
        {
            "diagnostic_id": created["diagnostic_id"],
            "project_id": created["project_id"],
            "report_id": created["report_id"],
            "mode": "guided",
        }
    )

    from app.core.database import get_session_factory
    from app.project_memory.repository import ProjectMemoryRepository

    async with get_session_factory()() as session:
        states = await ProjectMemoryRepository(session).list_dimension_states(created["project_id"])
    assert len(states) == 12
    assert all(state.last_score_run_id is not None for state in states)

    response = await client.post(
        f"/api/v1/projects/{created['project_id']}/memory",
        headers=headers,
        json={
            "dimension": "d1",
            "item_type": "declaration",
            "statement": "Les commerçants disent subir des coupures chaque semaine.",
        },
    )
    assert response.status_code == 201, response.text

    response = await client.get(f"/api/v1/projects/{created['project_id']}/evaluation", headers=headers)
    assert response.status_code == 200, response.text
    evaluation = response.json()
    assert evaluation["grid_version"]
    assert len(evaluation["dimensions"]) == 12
    assert len(evaluation["questions"]) <= 3
    d1 = next(dimension for dimension in evaluation["dimensions"] if dimension["dimension"] == "d1")
    assert isinstance(d1["score"], int)
    assert 0 <= d1["confidence"] <= 1
    assert d1["evidence_state"] == "declared"
