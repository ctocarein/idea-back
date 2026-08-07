"""Accès données de la file de jobs — enqueue + claim concurrent sûr.

Le claim utilise `FOR UPDATE SKIP LOCKED` : plusieurs workers peuvent tirer des jobs
en parallèle sans se marcher dessus ni se bloquer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
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
        idempotency_key: str | None = None,
        correlation_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> Job:
        if idempotency_key is not None:
            existing = await self.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing
        job = Job(
            type=job_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid4(),
            project_id=project_id,
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
            UPDATE jobs SET
                status = '{JobStatus.PROCESSING.name}',
                started_at = now(),
                locked_at = now(),
                heartbeat_at = now()
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

    async def get_by_idempotency_key(self, key: str) -> Job | None:
        result = await self.session.execute(select(Job).where(Job.idempotency_key == key))
        return result.scalar_one_or_none()

    async def heartbeat(self, job_id: UUID) -> None:
        await self.session.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.PROCESSING)
            .values(heartbeat_at=func.now(), locked_at=func.now())
        )

    async def recover_stale(self, *, stale_before: datetime) -> list[Job]:
        # Verrouille uniquement les jobs abandonnés. Plusieurs workers peuvent
        # lancer ce nettoyage en parallèle sans récupérer deux fois la même ligne.
        result = await self.session.execute(
            select(Job)
            .where(
                Job.status == JobStatus.PROCESSING,
                func.coalesce(Job.heartbeat_at, Job.locked_at) < stale_before,
            )
            .with_for_update(skip_locked=True)
        )
        terminal: list[Job] = []
        for job in result.scalars():
            error = "Lease worker expirée : traitement interrompu avant acquittement."
            if job.retry_count < job.max_retries:
                await self.mark_retry(job, error=error, next_run=datetime.now(UTC))
            else:
                await self.mark_failed(job, error=error)
                terminal.append(job)
        return terminal

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
        job.locked_at = None
        job.heartbeat_at = None
        job.finished_at = None
        job.scheduled_at = datetime.now(UTC)
        await self.session.flush()

    async def mark_completed(self, job: Job) -> None:
        job.status = JobStatus.COMPLETED
        job.finished_at = datetime.now(UTC)
        job.locked_at = None
        job.heartbeat_at = None
        await self.session.flush()

    async def mark_retry(self, job: Job, *, error: str, next_run: datetime) -> None:
        job.status = JobStatus.RETRYING
        job.retry_count += 1
        job.error_message = error
        job.scheduled_at = next_run
        job.locked_at = None
        job.heartbeat_at = None
        await self.session.flush()

    async def mark_failed(self, job: Job, *, error: str) -> None:
        job.status = JobStatus.FAILED
        job.error_message = error
        job.finished_at = datetime.now(UTC)
        job.locked_at = None
        job.heartbeat_at = None
        await self.session.flush()
