"""Accès données de la file de jobs — enqueue + claim concurrent sûr.

Le claim utilise `FOR UPDATE SKIP LOCKED` : plusieurs workers peuvent tirer des jobs
en parallèle sans se marcher dessus ni se bloquer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
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
        # Les littéraux doivent correspondre aux labels stockés en base : SQLAlchemy
        # persiste le **nom** du membre d'enum (PENDING…), pas sa valeur. On dérive donc
        # les labels de l'enum (`.name`) pour éviter toute dérive de chaîne magique.
        stmt = text(
            f"""
            UPDATE jobs SET status = '{JobStatus.PROCESSING.name}', started_at = now()
            WHERE id = (
                SELECT id FROM jobs
                WHERE status IN ('{JobStatus.PENDING.name}', '{JobStatus.RETRYING.name}')
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

    async def list_filtered(self, status: JobStatus | None = None, *, limit: int = 100) -> list[Job]:
        stmt = select(Job).order_by(Job.created_at.desc()).limit(limit)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def counts_by_status(self) -> dict[str, int]:
        result = await self.session.execute(select(Job.status, func.count()).group_by(Job.status))
        return {status.value: int(count) for status, count in result.all()}

    async def requeue(self, job: Job) -> None:
        # Relance manuelle (admin) : on remet le job en file, compteur et erreurs réinitialisés.
        job.status = JobStatus.PENDING
        job.retry_count = 0
        job.error_message = None
        job.started_at = None
        job.finished_at = None
        job.scheduled_at = datetime.now(UTC)
        await self.session.flush()

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
