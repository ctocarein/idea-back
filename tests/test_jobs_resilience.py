"""Contrats d'idempotence et de corrélation des jobs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
        # Transmis même absent : un job non daté est immédiatement éligible au claim.
        scheduled_at=None,
        idempotency_key=f"run_diagnostic:{correlation_id}",
        correlation_id=correlation_id,
        project_id=project_id,
    )


async def test_enqueue_forwards_a_future_schedule() -> None:
    """Un job DIFFÉRÉ n'est qu'un `enqueue` daté — la boucle de claim filtre déjà sur
    `scheduled_at <= now()`. C'est ce qui permet un rappel à J+7 sans planificateur."""
    repo = SimpleNamespace(session=object(), enqueue=AsyncMock(return_value=object()))
    due = datetime.now(UTC) + timedelta(days=7)

    await JobService(repo).enqueue(job_type="action_reminder", payload={}, scheduled_at=due)

    assert repo.enqueue.await_args.kwargs["scheduled_at"] == due
