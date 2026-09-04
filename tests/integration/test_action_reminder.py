"""Rappel J+7 — planification, annulations et désabonnement, sur DB réelle.

Ce qui se joue ici n'est pas l'envoi mais l'ABSTENTION : ne pas écrire à quelqu'un qui est
déjà revenu, qui s'est désabonné, ou dont l'adresse n'est pas prouvée. Un mail de trop
coûte la délivrabilité de tous les autres, vérification de compte comprise.

Le LLM mock dérive ses scores d'un hash : impossible de viser une dimension précise. Les
tests d'annulation passent donc par l'ajustement analyste (`PATCH /reports/{id}/scores`),
qui recalcule `next_actions` par la vraie chaîne — et exerce au passage le chemin humain,
pas seulement le chemin worker.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

pytestmark = pytest.mark.integration


async def _register(client, email: str) -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": "Awa Diallo", "email": email, "password": "s3cret-pwd", "consent": True},
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
            user = await UserRepository(s).create(
                email=email,
                password_hash=hash_password("pw-123456"),
                full_name="Admin",
                role=Role.ADMIN,
                status=AccountStatus.ACTIVE,
            )
            uid = user.id
    return {"Authorization": f"Bearer {create_access_token(subject=uid, role='admin')}"}


async def _run_diagnostic(created: dict) -> None:
    from app.diagnostics.handlers import handle_run_diagnostic

    await handle_run_diagnostic(
        {
            "diagnostic_id": created["diagnostic_id"],
            "project_id": created["project_id"],
            "report_id": created["report_id"],
            "mode": "guided",
        }
    )


async def _diagnose(client, headers: dict, title: str = "Tontine+") -> dict:
    r = await client.post(
        "/api/v1/diagnostics",
        headers=headers,
        json={
            "projectName": title,
            "sector": "finance",
            "description": "Appli de tontine via mobile money, tracabilite et confiance des membres.",
            "consent": True,
        },
    )
    assert r.status_code == 202, r.text
    created = r.json()
    await _run_diagnostic(created)
    return created


async def _next_actions(report_id: str) -> list[dict]:
    from app.core.database import get_session_factory
    from app.reports.models import Report

    async with get_session_factory()() as session:
        report = (await session.execute(select(Report).where(Report.id == report_id))).scalar_one()
        return list(report.next_actions or [])


async def _jobs_for(report_id: str) -> list[dict]:
    from app.core.database import get_session_factory

    async with get_session_factory()() as session:
        rows = await session.execute(
            text("SELECT id, payload, scheduled_at, status FROM jobs WHERE type = 'action_reminder'")
        )
        return [dict(r) for r in rows.mappings() if r["payload"]["report_id"] == report_id]


async def _force_weak_traction(client, report_id: str, admin: dict) -> None:
    """Rend D7 (Traction, levier `document`) la priorité n°1 du bilan."""
    from app.scoring.constants import AXIS_KEYS

    axes = dict.fromkeys(AXIS_KEYS, 9)
    axes["d7"] = 0  # seule dimension faible → première action, et elle est routable
    r = await client.patch(f"/api/v1/reports/{report_id}/scores", headers=admin, json={"axes": axes})
    assert r.status_code == 200, r.text


async def _schedule_for(created: dict) -> None:
    """Planifie le rappel sur l'état COURANT du bilan (après ajustement analyste).

    Appelle la même fonction que le handler worker : on contrôle l'entrée, pas le chemin.
    """
    from app.core.database import get_session_factory
    from app.diagnostics.handlers import _schedule_action_reminder
    from app.projects.models import Project
    from app.reports.models import Report

    async with get_session_factory()() as session:
        report = (await session.execute(select(Report).where(Report.id == created["report_id"]))).scalar_one()
        project = (await session.execute(select(Project).where(Project.id == created["project_id"]))).scalar_one()
        await _schedule_action_reminder(
            session, project=project, report=report, next_actions=list(report.next_actions or [])
        )
        await session.commit()


async def _run_reminder(created: dict) -> None:
    from app.notifications.handlers import handle_action_reminder

    jobs = await _jobs_for(created["report_id"])
    assert jobs, "aucun rappel planifié — le test ne prouverait rien"
    await handle_action_reminder(jobs[0]["payload"])


async def _notifications_of(email: str, kind: str) -> int:
    from app.core.database import get_session_factory

    async with get_session_factory()() as session:
        row = await session.execute(
            text(
                "SELECT count(*) FROM notifications n JOIN users u ON u.id = n.user_id "
                "WHERE u.email = :e AND n.type = :t"
            ),
            {"e": email, "t": kind},
        )
        return int(row.scalar_one())


async def _verify_email(email: str) -> None:
    from app.core.database import get_session_factory

    async with get_session_factory()() as session:
        await session.execute(text("UPDATE users SET email_verified = true WHERE email = :e"), {"e": email})
        await session.commit()


async def _ready(client, email: str) -> tuple[dict, dict]:
    """Porteur vérifié + bilan dont l'action n°1 est routable + rappel planifié."""
    headers = await _register(client, email)
    admin = await _admin(f"admin-{email}")
    created = await _diagnose(client, headers)
    await _force_weak_traction(client, created["report_id"], admin)
    await _schedule_for(created)
    await _verify_email(email)
    return headers, created


# --- Planification --------------------------------------------------------


async def test_reminder_is_scheduled_only_when_the_priority_is_routable(client) -> None:
    """Un rappel existe si et seulement si l'action n°1 routable existe dans le bilan.

    L'attendu est calculé sur les actions RÉELLEMENT produites, pas supposé : le filtre
    `document`/`mentor` s'applique aux 3 actions affichées au porteur, et un bilan dont
    les trois priorités pointent vers `academy` ne doit produire AUCUN rappel — silence
    assumé plutôt qu'un renvoi vers un module retiré.
    """
    from app.notifications.handlers import ROUTABLE_LEVERS

    headers = await _register(client, "rappel-plan@ideaxion.io")
    created = await _diagnose(client, headers)

    actions = await _next_actions(created["report_id"])
    routable = next((a for a in actions if a["lever_type"] in ROUTABLE_LEVERS), None)
    jobs = await _jobs_for(created["report_id"])

    if routable is None:
        assert jobs == []
        return

    assert len(jobs) == 1, "un seul rappel par bilan"
    job = jobs[0]
    assert job["payload"]["axis_key"] == routable["key"]
    # Un simple `enqueue` daté : la boucle de claim filtre déjà sur `scheduled_at <= now()`.
    assert job["scheduled_at"] > datetime.now(UTC) + timedelta(days=6)
    assert job["payload"]["project_id"] == created["project_id"]


async def test_replaying_the_diagnostic_does_not_schedule_a_second_reminder(client) -> None:
    headers = await _register(client, "rappel-rejeu@ideaxion.io")
    created = await _diagnose(client, headers)
    before = len(await _jobs_for(created["report_id"]))

    # Rejeu (retry de la file, reprise après incident) : l'idempotency_key doit tenir.
    await _run_diagnostic(created)
    assert len(await _jobs_for(created["report_id"])) == before


async def test_scheduling_is_idempotent_per_report(client) -> None:
    headers = await _register(client, "rappel-idem@ideaxion.io")
    admin = await _admin("admin-idem@ideaxion.io")
    created = await _diagnose(client, headers)
    await _force_weak_traction(client, created["report_id"], admin)

    await _schedule_for(created)
    await _schedule_for(created)
    assert len(await _jobs_for(created["report_id"])) == 1


# --- Exécution : le cas nominal, puis les cinq abstentions ----------------


async def test_nominal_run_sends_one_reminder_and_traces_it(client) -> None:
    email = "rappel-nominal@ideaxion.io"
    _, created = await _ready(client, email)

    await _run_reminder(created)

    # Trace in-app créée À L'ENVOI : elle doit refléter un mail réellement parti.
    assert await _notifications_of(email, "action_reminder") == 1


async def test_unverified_account_cancels_the_reminder(client) -> None:
    # On n'écrit pas à une adresse non prouvée : c'est la délivrabilité de TOUS les envois
    # qui est en jeu, y compris celle de la vérification de compte.
    email = "rappel-nonverifie@ideaxion.io"
    headers = await _register(client, email)
    admin = await _admin("admin-nonverif@ideaxion.io")
    created = await _diagnose(client, headers)
    await _force_weak_traction(client, created["report_id"], admin)
    await _schedule_for(created)  # email_verified reste faux

    await _run_reminder(created)
    assert await _notifications_of(email, "action_reminder") == 0


async def test_opted_out_owner_receives_nothing(client) -> None:
    email = "rappel-desabonne@ideaxion.io"
    _, created = await _ready(client, email)

    from app.core.database import get_session_factory
    from app.core.security import create_unsubscribe_token
    from app.iam.models import User

    async with get_session_factory()() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        token = create_unsubscribe_token(user.id)

    # Route PUBLIQUE : le lien est cliqué depuis une boîte mail, sans session.
    r = await client.get(f"/api/v1/notifications/unsubscribe?token={token}")
    assert r.status_code == 200
    assert "plus de rappels" in r.text

    await _run_reminder(created)
    assert await _notifications_of(email, "action_reminder") == 0


async def test_action_already_done_cancels_the_reminder(client) -> None:
    # D7 remonté au-dessus du seuil fort : l'action est faite, le rappel n'a plus d'objet.
    email = "rappel-fait@ideaxion.io"
    _, created = await _ready(client, email)

    from app.scoring.constants import AXIS_KEYS

    admin = await _admin("admin-fait2@ideaxion.io")
    axes = dict.fromkeys(AXIS_KEYS, 9)  # d7 inclus → au-dessus de STRONG_THRESHOLD
    r = await client.patch(f"/api/v1/reports/{created['report_id']}/scores", headers=admin, json={"axes": axes})
    assert r.status_code == 200, r.text

    await _run_reminder(created)
    assert await _notifications_of(email, "action_reminder") == 0


async def test_archived_project_cancels_the_reminder(client) -> None:
    email = "rappel-archive@ideaxion.io"
    _, created = await _ready(client, email)

    from app.core.database import get_session_factory

    async with get_session_factory()() as session:
        await session.execute(
            text("UPDATE projects SET diagnostic_status = 'ARCHIVED' WHERE id = :p"),
            {"p": created["project_id"]},
        )
        await session.commit()

    await _run_reminder(created)
    assert await _notifications_of(email, "action_reminder") == 0


async def test_returning_before_the_reminder_cancels_it(client) -> None:
    email = "rappel-revenu@ideaxion.io"
    headers, created = await _ready(client, email)

    # Le porteur refait un diagnostic → nouveau bilan, nouveau ScoreRun : il est revenu.
    await _diagnose(client, headers, title="Tontine+ v2")

    await _run_reminder(created)  # le rappel du PREMIER bilan
    assert await _notifications_of(email, "action_reminder") == 0


# --- Désabonnement --------------------------------------------------------


async def test_invalid_unsubscribe_token_is_rejected(client) -> None:
    r = await client.get("/api/v1/notifications/unsubscribe?token=nimportequoi")
    assert r.status_code == 422


async def test_unsubscribe_is_public_and_idempotent(client) -> None:
    # Le lien doit marcher sans session — sinon un désabonnement qui échoue se transforme
    # en signalement pour spam.
    email = "rappel-desabo2@ideaxion.io"
    await _register(client, email)

    from app.core.database import get_session_factory
    from app.core.security import create_unsubscribe_token
    from app.iam.models import User

    async with get_session_factory()() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        token = create_unsubscribe_token(user.id)

    assert (await client.get(f"/api/v1/notifications/unsubscribe?token={token}")).status_code == 200
    assert (await client.get(f"/api/v1/notifications/unsubscribe?token={token}")).status_code == 200
