"""Transitions d'état projet validées et auditées dans la transaction appelante."""

from __future__ import annotations

from uuid import UUID

from app.audit.service import AuditService
from app.core.errors import BusinessRuleError
from app.projects.models import (
    DiagnosticStatus,
    Project,
    ReviewStatus,
    can_transition_diagnostic,
    can_transition_review,
)
from app.projects.repository import ProjectRepository


class ProjectStateService:
    def __init__(self, repo: ProjectRepository, auditor: AuditService) -> None:
        self.repo = repo
        self.auditor = auditor

    async def transition_diagnostic(
        self,
        project: Project,
        target: DiagnosticStatus,
        *,
        actor_id: UUID | None,
    ) -> bool:
        current = project.diagnostic_status
        if current is target:
            return False
        if not can_transition_diagnostic(current, target):
            raise BusinessRuleError(f"Transition diagnostic illégale : {current.value} → {target.value}")
        await self.repo.set_diagnostic_status(project, target)
        await self.auditor.record(
            actor_id=actor_id,
            action="project.diagnostic_status",
            entity="project",
            entity_id=project.id,
            old_value=current,
            new_value=target,
        )
        return True

    async def transition_review(
        self,
        project: Project,
        target: ReviewStatus,
        *,
        actor_id: UUID | None,
    ) -> bool:
        current = project.review_status
        if current is target:
            return False
        if not can_transition_review(current, target):
            raise BusinessRuleError(f"Transition de curation illégale : {current.value} → {target.value}")
        await self.repo.set_review_status(project, target)
        await self.auditor.record(
            actor_id=actor_id,
            action="project.review_status",
            entity="project",
            entity_id=project.id,
            old_value=current,
            new_value=target,
        )
        return True
