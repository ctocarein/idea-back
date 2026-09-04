"""Purge des brouillons de diagnostic abandonnés.

Un brouillon est une donnée personnelle persistée AVANT soumission : sa durée de
conservation doit être bornée, et la purge est une suppression, pas un archivage.

Le job se replanifie lui-même à la fin de son exécution — il n'y a pas de planificateur
cron dans la stack, et en ajouter un pour une tâche quotidienne serait disproportionné.
La replanification est faite AVANT le traitement : si la suppression échoue, le prochain
tour est déjà programmé et le retard se rattrape tout seul.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.diagnostics.draft_repository import DiagnosticDraftRepository
from app.jobs.repository import JobRepository
from app.jobs.service import JobService

logger = get_logger("diagnostics.drafts")

PURGE_DRAFTS_JOB = "purge_drafts"


async def handle_purge_drafts(payload: dict[str, Any]) -> None:
    settings = get_settings()
    ttl_days = int(payload.get("ttl_days") or settings.draft_ttl_days)

    async with get_session_factory()() as session:
        jobs = JobService(JobRepository(session))
        # Replanification d'abord : le prochain tour ne dépend pas du succès de celui-ci.
        # `idempotency_key` datée → deux workers qui traitent le même job ne créent qu'une
        # seule occurrence pour demain.
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        await jobs.enqueue(
            job_type=PURGE_DRAFTS_JOB,
            payload={"ttl_days": ttl_days},
            priority=900,  # tâche de fond : ne passe jamais devant un diagnostic
            scheduled_at=tomorrow,
            idempotency_key=f"{PURGE_DRAFTS_JOB}:{tomorrow.date().isoformat()}",
        )
        deleted = await DiagnosticDraftRepository(session).purge_stale(ttl_days=ttl_days)
        await session.commit()

    logger.info("drafts_purged", deleted=deleted, ttl_days=ttl_days)
