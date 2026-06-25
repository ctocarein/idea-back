"""Back-office projets (ADMIN-01) — liste, détail, curation (machine + audit), assignation."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register_founder(client, email: str) -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": "Awa", "email": email, "password": "s3cret-pwd", "consent": True},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _staff(email: str, role) -> tuple:
    # Crée un compte staff directement en base + mint un token (perms rechargées depuis le rôle).
    from app.core.database import get_session_factory
    from app.core.security import create_access_token, hash_password
    from app.iam.models import AccountStatus
    from app.iam.repository import UserRepository

    async with get_session_factory()() as s:
        async with s.begin():
            u = await UserRepository(s).create(
                email=email,
                password_hash=hash_password("pw-123456"),
                full_name="Staff",
                role=role,
                status=AccountStatus.ACTIVE,
            )
            uid = u.id
    return uid, {"Authorization": f"Bearer {create_access_token(subject=uid, role=role.value)}"}


async def _make_project(client, headers) -> str:
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
    return r.json()["project_id"]


async def test_back_office_list_detail_transition_assign(client) -> None:
    from app.iam.models import Role

    founder = await _register_founder(client, "awa-admin@ideaxion.io")
    pid = await _make_project(client, founder)
    _, admin = await _staff("admin1@ideaxion.io", Role.ADMIN)
    analyst_id, _ = await _staff("analyst1@ideaxion.io", Role.ANALYST)

    # Le porteur n'a pas accès au back-office.
    assert (await client.get("/api/v1/admin/projects", headers=founder)).status_code == 403

    # L'admin liste (filtre review_status) et voit le projet.
    r = await client.get("/api/v1/admin/projects?review_status=new_diagnostic", headers=admin)
    assert r.status_code == 200, r.text
    assert any(p["id"] == pid for p in r.json())

    # Détail.
    r = await client.get(f"/api/v1/admin/projects/{pid}", headers=admin)
    assert r.status_code == 200 and r.json()["review_status"] == "new_diagnostic"

    # Curation : transition légale new_diagnostic → in_review.
    r = await client.patch(f"/api/v1/admin/projects/{pid}/review-status", headers=admin, json={"target": "in_review"})
    assert r.status_code == 200 and r.json()["review_status"] == "in_review"

    # Transition illégale (saut) → 422.
    r = await client.patch(f"/api/v1/admin/projects/{pid}/review-status", headers=admin, json={"target": "excellence"})
    assert r.status_code == 422, r.text

    # Assignation à un analyste → 200.
    r = await client.patch(
        f"/api/v1/admin/projects/{pid}/assignee", headers=admin, json={"assignee_id": str(analyst_id)}
    )
    assert r.status_code == 200 and r.json()["assignee_id"] == str(analyst_id)

    # On ne peut pas assigner un porteur.
    founder_id, _ = await _staff("porteur-assign@ideaxion.io", Role.FOUNDER)
    r = await client.patch(
        f"/api/v1/admin/projects/{pid}/assignee", headers=admin, json={"assignee_id": str(founder_id)}
    )
    assert r.status_code == 422, r.text


async def test_grid_governance(client) -> None:
    # ADMIN-02 (gouvernance grille) : lister les versions + activer.
    from app.iam.models import Role

    _, admin = await _staff("admin-grid@ideaxion.io", Role.ADMIN)

    r = await client.get("/api/v1/admin/scoring/grids", headers=admin)
    assert r.status_code == 200, r.text
    grids = r.json()
    assert grids and any(g["is_active"] for g in grids)
    version = next(g["version"] for g in grids if g["is_active"])

    # (Ré)activer une version → 200.
    r = await client.post(f"/api/v1/admin/scoring/grids/{version}/activate", headers=admin)
    assert r.status_code == 200 and r.json()["is_active"]

    # Version inconnue → 404.
    assert (await client.post("/api/v1/admin/scoring/grids/inconnue/activate", headers=admin)).status_code == 404

    # Un porteur n'a pas accès à la gouvernance.
    founder = await _register_founder(client, "awa-grid@ideaxion.io")
    assert (await client.get("/api/v1/admin/scoring/grids", headers=founder)).status_code == 403


async def test_audit_timeline_and_logs(client) -> None:
    # ADMIN-03 : chaque action de curation laisse une trace lisible (timeline + journal).
    from app.iam.models import Role

    founder = await _register_founder(client, "awa-audit@ideaxion.io")
    pid = await _make_project(client, founder)
    _, admin = await _staff("admin-audit@ideaxion.io", Role.ADMIN)

    r = await client.patch(f"/api/v1/admin/projects/{pid}/review-status", headers=admin, json={"target": "in_review"})
    assert r.status_code == 200, r.text

    # Timeline du projet : contient l'action de curation auditée.
    r = await client.get(f"/api/v1/admin/projects/{pid}/timeline", headers=admin)
    assert r.status_code == 200, r.text
    assert "project.review_status" in [e["action"] for e in r.json()]

    # Journal global filtré par entité.
    r = await client.get("/api/v1/admin/audit-logs?entity=project", headers=admin)
    assert r.status_code == 200 and any(e["entity"] == "project" for e in r.json())

    # Le porteur n'a pas AUDIT_READ.
    assert (await client.get("/api/v1/admin/audit-logs", headers=founder)).status_code == 403
