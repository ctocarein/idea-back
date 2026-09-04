"""Entrypoint worker — boucle de polling de la table jobs.

Second point d'entrée du MÊME code base : il réutilise les services des features.
Au socle, le registry de handlers est vide ; les handlers concrets (run_diagnostic,
send_email, cleanup_expired) sont ajoutés au fil des sprints (2+).

Lancement : `python -m app.worker` (ou `make worker`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import app.models  # noqa: F401 — enregistre TOUTES les tables sur Base.metadata (FK cross-features)
from app.core.database import get_session_factory
from app.core.logging import configure_logging, get_logger
from app.diagnostics.draft_handlers import PURGE_DRAFTS_JOB, handle_purge_drafts
from app.diagnostics.handlers import handle_run_diagnostic, handle_run_diagnostic_failed
from app.jobs.models import Job
from app.jobs.repository import JobRepository
from app.jobs.service import JobService
from app.notifications.handlers import (
    ACTION_REMINDER_JOB,
    SEND_EMAIL_JOB,
    handle_action_reminder,
    handle_send_email,
)

logger = get_logger("worker")

POLL_INTERVAL = 2.0  # secondes entre deux sondages quand la file est vide
HEARTBEAT_INTERVAL = 30.0

# Registry type → handler. Rempli au fil des sprints.
HandlerFn = Callable[[dict[str, Any]], Awaitable[None]]
REGISTRY: dict[str, HandlerFn] = {
    "run_diagnostic": handle_run_diagnostic,  # Sprint 2 (diagnostic → bilan)
    SEND_EMAIL_JOB: handle_send_email,  # envoi différé (SMTP bloquant → thread)
    ACTION_REMINDER_JOB: handle_action_reminder,  # rappel J+7 sur l'action prioritaire
    PURGE_DRAFTS_JOB: handle_purge_drafts,  # purge quotidienne des brouillons abandonnés
}

# Nettoyage sur échec DÉFINITIF (retries épuisés). Optionnel par type : permet de
# sortir proprement d'un état d'attente (ex. bilan `pending` → `failed`).
TERMINAL_REGISTRY: dict[str, HandlerFn] = {
    "run_diagnostic": handle_run_diagnostic_failed,
}


async def _process(job: Job, jobs: JobService) -> None:
    handler = REGISTRY.get(job.type)
    if handler is None:
        # Type inconnu : on échoue proprement plutôt que de boucler dessus.
        await jobs.fail(job, RuntimeError(f"handler manquant pour le type '{job.type}'"))
        return
    heartbeat = asyncio.create_task(_heartbeat(job.id))
    error: Exception | None = None
    try:
        await handler(job.payload)
    except Exception as exc:  # noqa: BLE001 — on capture tout pour décider du retry
        error = exc
    finally:
        heartbeat.cancel()
        try:
            await heartbeat
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001 — le heartbeat ne masque pas le résultat métier
            logger.warning("job_heartbeat_failed", job_id=str(job.id), error=str(exc))
    if error is not None:
        terminal = await jobs.fail(job, error)
        if terminal:
            await _cleanup_terminal(job)
        return
    await jobs.complete(job)


async def _heartbeat(job_id: UUID) -> None:
    factory = get_session_factory()
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        async with factory() as session:
            await JobService(JobRepository(session)).heartbeat(job_id)


async def _cleanup_terminal(job: Job) -> None:
    # Échec définitif : déclenche le nettoyage propre au type, s'il existe.
    cleanup = TERMINAL_REGISTRY.get(job.type)
    if cleanup is None:
        return
    try:
        await cleanup(job.payload)
    except Exception as exc:  # noqa: BLE001 — le nettoyage ne doit jamais masquer l'échec initial
        logger.error("terminal_cleanup_failed", job_id=str(job.id), type=job.type, error=str(exc))


async def _ensure_daily_jobs() -> None:
    """Amorce les tâches récurrentes. Chacune se replanifie ensuite elle-même.

    Il n'y a pas de planificateur externe dans la stack, et en ajouter un pour une purge
    quotidienne serait disproportionné. L'`idempotency_key` datée rend l'amorçage sûr :
    redémarrer le worker dix fois dans la journée ne crée pas dix jobs.
    """
    async with get_session_factory()() as session:
        jobs = JobService(JobRepository(session))
        today = datetime.now(UTC).date().isoformat()
        await jobs.enqueue(
            job_type=PURGE_DRAFTS_JOB,
            payload={},
            priority=900,
            idempotency_key=f"{PURGE_DRAFTS_JOB}:{today}",
        )
        await session.commit()


async def run() -> None:
    configure_logging()
    logger.info("worker_starting", handlers=sorted(REGISTRY))
    factory = get_session_factory()
    try:
        await _ensure_daily_jobs()
    except Exception as exc:  # noqa: BLE001 — une tâche de fond ne bloque pas le worker
        logger.warning("daily_jobs_bootstrap_failed", error=str(exc))

    while True:
        async with factory() as session:
            jobs = JobService(JobRepository(session))
            for stale_job in await jobs.recover_stale():
                logger.error("stale_job_failed", job_id=str(stale_job.id), type=stale_job.type)
                await _cleanup_terminal(stale_job)
            job = await jobs.claim()
            if job is None:
                await asyncio.sleep(POLL_INTERVAL)
                continue
            logger.info("job_claimed", job_id=str(job.id), type=job.type)
            await _process(job, jobs)


if __name__ == "__main__":
    asyncio.run(run())
