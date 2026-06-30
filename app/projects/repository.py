"""Accès données projets — création + lectures + écriture de statut."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.models import (
    Archetype,
    DiagnosticStatus,
    Project,
    ProjectStage,
    ReviewStatus,
)


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, project_id: UUID) -> Project | None:
        return await self.session.get(Project, project_id)

    async def list_for_owner(self, owner_id: UUID) -> list[Project]:
        result = await self.session.execute(
            select(Project).where(Project.owner_id == owner_id).order_by(Project.created_at.desc())
        )
        return list(result.scalars())

    async def list_filtered(
        self,
        *,
        review_status: ReviewStatus | None = None,
        diagnostic_status: DiagnosticStatus | None = None,
        sector: str | None = None,
        assignee_id: UUID | None = None,
    ) -> list[Project]:
        # Back-office admin/analyste : liste filtrable de TOUS les projets.
        stmt = select(Project).order_by(Project.created_at.desc())
        if review_status is not None:
            stmt = stmt.where(Project.review_status == review_status)
        if diagnostic_status is not None:
            stmt = stmt.where(Project.diagnostic_status == diagnostic_status)
        if sector is not None:
            stmt = stmt.where(Project.sector == sector)
        if assignee_id is not None:
            stmt = stmt.where(Project.assignee_id == assignee_id)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def set_assignee(self, project: Project, assignee_id: UUID | None) -> None:
        project.assignee_id = assignee_id
        await self.session.flush()

    async def create(
        self,
        *,
        owner_id: UUID,
        title: str,
        sector: str,
        archetype: Archetype = Archetype.FIELD,
        stage: ProjectStage = ProjectStage.IDEA,
        diagnostic_status: DiagnosticStatus = DiagnosticStatus.DRAFT,
        review_status: ReviewStatus = ReviewStatus.NEW_DIAGNOSTIC,
    ) -> Project:
        project = Project(
            owner_id=owner_id,
            title=title,
            sector=sector,
            archetype=archetype,
            stage=stage,
            diagnostic_status=diagnostic_status,
            review_status=review_status,
        )
        self.session.add(project)
        await self.session.flush()
        return project

    async def set_diagnostic_status(self, project: Project, status: DiagnosticStatus) -> None:
        project.diagnostic_status = status
        await self.session.flush()

    async def set_review_status(self, project: Project, status: ReviewStatus) -> None:
        project.review_status = status
        await self.session.flush()

    async def set_visibility(self, project: Project, is_public: bool) -> None:
        project.is_public = is_public
        await self.session.flush()

    async def get_latest_for_owner(self, owner_id: UUID) -> Project | None:
        result = await self.session.execute(
            select(Project)
            .where(Project.owner_id == owner_id)
            .order_by(Project.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
