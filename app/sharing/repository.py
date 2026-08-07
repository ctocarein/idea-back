"""Accès données partages."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.sharing.models import ProjectShare


class ShareRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        project_id: UUID,
        owner_id: UUID,
        token_hash: str,
        consent_at: datetime,
        expires_at: datetime,
    ) -> ProjectShare:
        share = ProjectShare(
            project_id=project_id,
            owner_id=owner_id,
            token_hash=token_hash,
            consent_at=consent_at,
            expires_at=expires_at,
        )
        self.session.add(share)
        await self.session.flush()
        return share

    async def get_active_by_hash(self, token_hash: str) -> ProjectShare | None:
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(ProjectShare).where(
                ProjectShare.token_hash == token_hash,
                ProjectShare.is_active.is_(True),
                ProjectShare.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def increment_view(self, token_hash: str) -> None:
        await self.session.execute(
            update(ProjectShare)
            .values(
                view_count=ProjectShare.view_count + 1,
                last_viewed_at=func.now(),
            )
            .where(ProjectShare.token_hash == token_hash)
        )
        await self.session.flush()

    async def list_by_owner(self, owner_id: UUID) -> list[ProjectShare]:
        result = await self.session.execute(
            select(ProjectShare).where(ProjectShare.owner_id == owner_id).order_by(ProjectShare.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_owner_with_title(self, owner_id: UUID) -> list[tuple[ProjectShare, str]]:
        from app.projects.models import Project  # import local pour éviter la circularité

        result = await self.session.execute(
            select(ProjectShare, Project.title)
            .join(Project, ProjectShare.project_id == Project.id)
            .where(ProjectShare.owner_id == owner_id)
            .order_by(ProjectShare.created_at.desc())
        )
        return [(row.ProjectShare, row.title) for row in result.all()]

    async def revoke_for_project(self, project_id: UUID, owner_id: UUID) -> None:
        await self.session.execute(
            update(ProjectShare)
            .values(is_active=False)
            .where(
                ProjectShare.project_id == project_id,
                ProjectShare.owner_id == owner_id,
                ProjectShare.is_active.is_(True),
            )
        )
        await self.session.flush()
