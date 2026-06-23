"""Accès données de la file de jobs — enqueue + claim concurrent sûr.

Le claim utilise `FOR UPDATE SKIP LOCKED` : plusieurs workers peuvent tirer des jobs
en parallèle sans se marcher dessus ni se bloquer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.models import Job, JobStatus


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        priority: int = 100,
        scheduled_at: datetime | None = None,
        max_retries: int = 3,
    ) -> Job:
        job = Job(
            type=job_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries,
        )
        if scheduled_at is not None:
            job.scheduled_at = scheduled_at
        self.session.add(job)
        await self.session.flush()
        return job

    async def claim_one(self) -> Job | None:
        # Atomique : sélectionne le prochain job éligible et le passe à 'processing'.
        # SKIP LOCKED → les lignes verrouillées par un autre worker sont ignorées.
        stmt = text(
            """
            UPDATE jobs SET status = 'processing', started_at = now()
            WHERE id = (
                SELECT id FROM jobs
                WHERE status IN ('pending', 'retrying')
                  AND scheduled_at <= now()
                ORDER BY priority ASC, scheduled_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id
            """
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        job = await self.session.get(Job, row[0])
        return job

    async def get_by_id(self, job_id: UUID) -> Job | None:
        return await self.session.get(Job, job_id)

    async def mark_completed(self, job: Job) -> None:
        job.status = JobStatus.COMPLETED
        job.finished_at = datetime.now(UTC)
        await self.session.flush()

    async def mark_retry(self, job: Job, *, error: str, next_run: datetime) -> None:
        job.status = JobStatus.RETRYING
        job.retry_count += 1
        job.error_message = error
        job.scheduled_at = next_run
        await self.session.flush()

    async def mark_failed(self, job: Job, *, error: str) -> None:
        job.status = JobStatus.FAILED
        job.error_message = error
        job.finished_at = datetime.now(UTC)
        await self.session.flush()
