"""Purge des brouillons abandonnés — la borne de conservation RGPD.

Un brouillon est une donnée personnelle persistée AVANT soumission : sa durée de vie doit
être bornée, et la purge est une suppression, pas un archivage. Les brouillons SOUMIS sont
conservés : ils portent la trajectoire de saisie, qui est la donnée qu'on cherchait.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

pytestmark = pytest.mark.integration


async def _register(client, email: str) -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": "Awa", "email": email, "password": "s3cret-pwd", "consent": True},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _age_draft(email: str, *, days: int, submitted: bool = False) -> None:
    """Vieillit le brouillon d'un porteur. `updated_at` est piloté par le serveur : on le
    force en SQL, sinon il faudrait attendre 90 jours pour tester la purge."""
    from app.core.database import get_session_factory

    async with get_session_factory()() as session:
        await session.execute(
            text(
                "UPDATE diagnostic_drafts SET updated_at = :ts, submitted_at = :sub "
                "WHERE owner_id = (SELECT id FROM users WHERE email = :e)"
            ),
            {
                "ts": datetime.now(UTC) - timedelta(days=days),
                "sub": datetime.now(UTC) if submitted else None,
                "e": email,
            },
        )
        await session.commit()


async def _count_drafts() -> int:
    from app.core.database import get_session_factory
    from app.diagnostics.models import DiagnosticDraft

    async with get_session_factory()() as session:
        rows = await session.execute(select(DiagnosticDraft))
        return len(list(rows.scalars()))


async def _save_draft(client, headers: dict) -> None:
    r = await client.put(
        "/api/v1/diagnostics/draft",
        headers=headers,
        json={"answers": {"d1": "saisie"}, "payload": {}, "lastDimension": "d1"},
    )
    assert r.status_code == 200, r.text


async def test_purge_removes_only_stale_abandoned_drafts(client) -> None:
    from app.diagnostics.draft_handlers import handle_purge_drafts

    stale = await _register(client, "purge-vieux@ideaxion.io")
    fresh = await _register(client, "purge-recent@ideaxion.io")
    done = await _register(client, "purge-soumis@ideaxion.io")

    for headers in (stale, fresh, done):
        await _save_draft(client, headers)

    await _age_draft("purge-vieux@ideaxion.io", days=91)  # au-delà du TTL → supprimé
    await _age_draft("purge-recent@ideaxion.io", days=89)  # en deçà → conservé
    await _age_draft("purge-soumis@ideaxion.io", days=200, submitted=True)  # soumis → conservé

    before = await _count_drafts()
    await handle_purge_drafts({"ttl_days": 90})
    assert await _count_drafts() == before - 1

    assert (await client.get("/api/v1/diagnostics/draft", headers=stale)).status_code == 404
    assert (await client.get("/api/v1/diagnostics/draft", headers=fresh)).status_code == 200


async def test_purge_reschedules_itself_for_tomorrow(client) -> None:
    """Pas de planificateur cron dans la stack : le job se replanifie lui-même.

    La replanification est faite AVANT le traitement — si la suppression échoue, le
    prochain tour est déjà programmé et le retard se rattrape tout seul.
    """
    from app.core.database import get_session_factory
    from app.diagnostics.draft_handlers import handle_purge_drafts

    await handle_purge_drafts({"ttl_days": 90})

    async with get_session_factory()() as session:
        rows = await session.execute(
            text("SELECT scheduled_at, payload FROM jobs WHERE type = 'purge_drafts' ORDER BY created_at DESC")
        )
        jobs = [dict(r) for r in rows.mappings()]

    assert jobs, "aucune replanification"
    assert jobs[0]["scheduled_at"] > datetime.now(UTC) + timedelta(hours=20)
    assert jobs[0]["payload"]["ttl_days"] == 90


async def test_purge_is_idempotent_within_a_day(client) -> None:
    # `idempotency_key` datée : deux exécutions le même jour ne créent qu'une occurrence
    # pour demain, même si plusieurs workers traitent le job.
    from app.core.database import get_session_factory
    from app.diagnostics.draft_handlers import handle_purge_drafts

    await handle_purge_drafts({"ttl_days": 90})
    await handle_purge_drafts({"ttl_days": 90})

    async with get_session_factory()() as session:
        row = await session.execute(text("SELECT count(*) FROM jobs WHERE type = 'purge_drafts'"))
        assert int(row.scalar_one()) == 1
