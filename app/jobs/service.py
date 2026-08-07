"""Service de la file de jobs — orchestration du cycle de vie.

  pending ─claim─> processing ─┬─ succès ─> completed
                               ├─ échec (retries restants) ─> retrying ─(backoff)─> pending
                               └─ échec (retries épuisés)  ─> failed ─> alerte admin

Backoff : 1 min → 5 min → 15 min, max_retries = 3.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.jobs.models import Job
from app.jobs.repository import JobRepository

logger = get_logger("jobs")

# Délais de backoff par tentative (en minutes), index = retry_count courant.
_BACKOFF_MINUTES = [1, 5, 15]
JOB_LEASE_SECONDS = 30 * 60


class JobService:
    def __init__(self, repo: JobRepository) -> None:
        self.repo = repo
        self.session = repo.session

    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        priority: int = 100,
        idempotency_key: str | None = None,
        correlation_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> Job:
        # Appelé DANS la transaction du service métier (ex. lancer un diagnostic).
        return await self.repo.enqueue(
            job_type=job_type,
            payload=payload,
            priority=priority,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            project_id=project_id,
        )

    async def recover_stale(self) -> list[Job]:
        stale_before = datetime.now(UTC) - timedelta(seconds=JOB_LEASE_SECONDS)
        async with self.session.begin():
            return await self.repo.recover_stale(stale_before=stale_before)

    async def heartbeat(self, job_id: UUID) -> None:
        async with self.session.begin():
            await self.repo.heartbeat(job_id)

    async def claim(self) -> Job | None:
        async with self.session.begin():
            return await self.repo.claim_one()

    async def complete(self, job: Job) -> None:
        async with self.session.begin():
            await self.repo.mark_completed(job)

    async def fail(self, job: Job, exc: Exception) -> bool:
        # Décide retry (backoff) ou échec définitif selon les tentatives restantes.
        # Renvoie True si l'échec est DÉFINITIF (retries épuisés) — le worker peut alors
        # déclencher un nettoyage propre à ce type de job (ex. sortir le bilan de l'attente).
        error = f"{type(exc).__name__}: {exc}"
        async with self.session.begin():
            if job.retry_count < job.max_retries:
                delay = _BACKOFF_MINUTES[min(job.retry_count, len(_BACKOFF_MINUTES) - 1)]
                next_run = datetime.now(UTC) + timedelta(minutes=delay)
                await self.repo.mark_retry(job, error=error, next_run=next_run)
                logger.warning("job_retrying", job_id=str(job.id), type=job.type, delay_min=delay)
                return False
            await self.repo.mark_failed(job, error=error)
            logger.error("job_failed", job_id=str(job.id), type=job.type, error=error)
            return True
