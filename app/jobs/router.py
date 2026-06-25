"""Routes de supervision des jobs (admin) — liste, compteurs, relance."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.core.database import get_session
from app.core.errors import NotFoundError
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.jobs.models import JobStatus
from app.jobs.repository import JobRepository
from app.jobs.schemas import JobOut

router = APIRouter(prefix="/admin/jobs", tags=["admin-jobs"])


@router.get("", response_model=list[JobOut])
async def list_jobs(
    status: JobStatus | None = None,
    ctx: AuthContext = Depends(require(Permission.JOBS_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> list[JobOut]:
    rows = await JobRepository(session).list_filtered(status)
    return [JobOut.model_validate(j) for j in rows]


@router.get("/stats", response_model=dict[str, int])
async def job_stats(
    ctx: AuthContext = Depends(require(Permission.JOBS_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    return await JobRepository(session).counts_by_status()


@router.post("/{job_id}/retry", response_model=JobOut)
async def retry_job(
    job_id: UUID,
    ctx: AuthContext = Depends(require(Permission.JOBS_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> JobOut:
    repo = JobRepository(session)
    job = await repo.get_by_id(job_id)
    if job is None:
        raise NotFoundError("job")
    await repo.requeue(job)
    await AuditService(session).record(actor_id=ctx.user.id, action="job.retried", entity="job", entity_id=job.id)
    await session.commit()
    return JobOut.model_validate(job)
