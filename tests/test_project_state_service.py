"""Transitions projet centralisées, idempotentes et auditées."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.errors import BusinessRuleError
from app.projects.models import DiagnosticStatus, ReviewStatus
from app.projects.state_service import ProjectStateService


@pytest.mark.asyncio
async def test_diagnostic_transition_is_persisted_and_audited() -> None:
    project = SimpleNamespace(id=uuid4(), diagnostic_status=DiagnosticStatus.DRAFT)
    repo = SimpleNamespace(set_diagnostic_status=AsyncMock())
    repo.set_diagnostic_status.side_effect = lambda item, target: setattr(item, "diagnostic_status", target)
    auditor = SimpleNamespace(record=AsyncMock())
    service = ProjectStateService(repo, auditor)

    changed = await service.transition_diagnostic(
        project,
        DiagnosticStatus.DIAGNOSTIC_IN_PROGRESS,
        actor_id=uuid4(),
    )

    assert changed is True
    assert project.diagnostic_status is DiagnosticStatus.DIAGNOSTIC_IN_PROGRESS
    auditor.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_same_transition_is_an_idempotent_noop() -> None:
    project = SimpleNamespace(id=uuid4(), review_status=ReviewStatus.IN_REVIEW)
    repo = SimpleNamespace(set_review_status=AsyncMock())
    auditor = SimpleNamespace(record=AsyncMock())
    service = ProjectStateService(repo, auditor)

    changed = await service.transition_review(project, ReviewStatus.IN_REVIEW, actor_id=None)

    assert changed is False
    repo.set_review_status.assert_not_awaited()
    auditor.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_illegal_transition_is_rejected_before_write() -> None:
    project = SimpleNamespace(id=uuid4(), diagnostic_status=DiagnosticStatus.DRAFT)
    repo = SimpleNamespace(set_diagnostic_status=AsyncMock())
    auditor = SimpleNamespace(record=AsyncMock())
    service = ProjectStateService(repo, auditor)

    with pytest.raises(BusinessRuleError):
        await service.transition_diagnostic(project, DiagnosticStatus.BILAN_READY, actor_id=None)

    repo.set_diagnostic_status.assert_not_awaited()
    auditor.record.assert_not_awaited()
