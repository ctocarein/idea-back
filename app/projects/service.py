"""Service back-office projets — curation analyste/admin (transition + assignation, auditée).

Les transitions de `review_status` passent par la machine `REVIEW_TRANSITIONS` (aucun saut
illégal) ; chaque action est tracée via l'audit, atomiquement avec le changement.
"""

from __future__ import annotations

from uuid import UUID

from app.audit.service import AuditService
from app.core.errors import BusinessRuleError, NotFoundError
from app.iam.dependencies import AuthContext
from app.iam.models import Role
from app.iam.repository import UserRepository
from app.projects.models import (
    DiagnosticStatus,
    ReviewStatus,
)
from app.projects.repository import ProjectRepository
from app.projects.schemas import ProjectAdminOut
from app.projects.state_service import ProjectStateService


class ProjectAdminService:
    def __init__(self, repo: ProjectRepository, users: UserRepository, auditor: AuditService) -> None:
        self.repo = repo
        self.users = users
        self.auditor = auditor
        self.states = ProjectStateService(repo, auditor)
        self.session = repo.session

    async def list_projects(
        self,
        *,
        review_status: ReviewStatus | None = None,
        diagnostic_status: DiagnosticStatus | None = None,
        sector: str | None = None,
        assignee_id: UUID | None = None,
    ) -> list[ProjectAdminOut]:
        rows = await self.repo.list_filtered(
            review_status=review_status,
            diagnostic_status=diagnostic_status,
            sector=sector,
            assignee_id=assignee_id,
        )
        return [ProjectAdminOut.model_validate(p) for p in rows]

    async def get_detail(self, project_id: UUID) -> ProjectAdminOut:
        project = await self.repo.get_by_id(project_id)
        if project is None:
            raise NotFoundError("project")
        return ProjectAdminOut.model_validate(project)

    async def transition_review(self, ctx: AuthContext, project_id: UUID, target: ReviewStatus) -> ProjectAdminOut:
        project = await self.repo.get_by_id(project_id)
        if project is None:
            raise NotFoundError("project")
        await self.states.transition_review(project, target, actor_id=ctx.user.id)
        await self.session.commit()
        return ProjectAdminOut.model_validate(project)

    async def assign(self, ctx: AuthContext, project_id: UUID, assignee_id: UUID | None) -> ProjectAdminOut:
        project = await self.repo.get_by_id(project_id)
        if project is None:
            raise NotFoundError("project")
        if assignee_id is not None:
            assignee = await self.users.get_by_id(assignee_id)
            if assignee is None:
                raise NotFoundError("user")
            if assignee.role is Role.FOUNDER:
                raise BusinessRuleError("Un porteur ne peut pas être assigné à la curation.")
        old = project.assignee_id
        await self.repo.set_assignee(project, assignee_id)
        await self.auditor.record(
            actor_id=ctx.user.id,
            action="project.assignee",
            entity="project",
            entity_id=project_id,
            old_value={"assignee_id": str(old) if old else None},
            new_value={"assignee_id": str(assignee_id) if assignee_id else None},
        )
        await self.session.commit()
        return ProjectAdminOut.model_validate(project)
