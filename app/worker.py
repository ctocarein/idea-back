"""Entrypoint worker — boucle de polling de la table jobs.

Second point d'entrée du MÊME code base : il réutilise les services des features.
Au socle, le registry de handlers est vide ; les handlers concrets (run_diagnostic,
send_email, cleanup_expired) sont ajoutés au fil des sprints (2+).

Lancement : `python -m app.worker` (ou `make worker`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.database import get_session_factory
from app.core.logging import configure_logging, get_logger
from app.diagnostics.handlers import handle_run_diagnostic
from app.jobs.models import Job
from app.jobs.repository import JobRepository
from app.jobs.service import JobService

logger = get_logger("worker")

POLL_INTERVAL = 2.0  # secondes entre deux sondages quand la file est vide

# Registry type → handler. Rempli au fil des sprints.
HandlerFn = Callable[[dict[str, Any]], Awaitable[None]]
REGISTRY: dict[str, HandlerFn] = {
    "run_diagnostic": handle_run_diagnostic,  # Sprint 2 (diagnostic → bilan)
    # "send_email": handle_send_email,           # Sprint 2
    # "cleanup_expired": handle_cleanup_expired, # cron quotidien
}


async def _process(job: Job, jobs: JobService) -> None:
    handler = REGISTRY.get(job.type)
    if handler is None:
        # Type inconnu : on échoue proprement plutôt que de boucler dessus.
        await jobs.fail(job, RuntimeError(f"handler manquant pour le type '{job.type}'"))
        return
    try:
        await handler(job.payload)
    except Exception as exc:  # noqa: BLE001 — on capture tout pour décider du retry
        await jobs.fail(job, exc)
        return
    await jobs.complete(job)


async def run() -> None:
    configure_logging()
    logger.info("worker_starting", handlers=sorted(REGISTRY))
    factory = get_session_factory()

    while True:
        async with factory() as session:
            jobs = JobService(JobRepository(session))
            job = await jobs.claim()
            if job is None:
                await asyncio.sleep(POLL_INTERVAL)
                continue
            logger.info("job_claimed", job_id=str(job.id), type=job.type)
            await _process(job, jobs)


if __name__ == "__main__":
    asyncio.run(run())
