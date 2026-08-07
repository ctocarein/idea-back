"""Contrats d'idempotence et de corrélation des jobs."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.jobs.models import Job
from app.jobs.service import JobService


def test_job_model_contains_recovery_metadata() -> None:
    columns = set(Job.__table__.columns.keys())
    assert {"idempotency_key", "correlation_id", "project_id", "locked_at", "heartbeat_at"} <= columns


@pytest.mark.asyncio
async def test_enqueue_forwards_business_context() -> None:
    expected = object()
    repo = SimpleNamespace(session=object(), enqueue=AsyncMock(return_value=expected))
    service = JobService(repo)
    correlation_id = uuid4()
    project_id = uuid4()

    result = await service.enqueue(
        job_type="run_diagnostic",
        payload={"diagnostic_id": str(correlation_id)},
        idempotency_key=f"run_diagnostic:{correlation_id}",
        correlation_id=correlation_id,
        project_id=project_id,
    )

    assert result is expected
    repo.enqueue.assert_awaited_once_with(
        job_type="run_diagnostic",
        payload={"diagnostic_id": str(correlation_id)},
        priority=100,
        idempotency_key=f"run_diagnostic:{correlation_id}",
        correlation_id=correlation_id,
        project_id=project_id,
    )
