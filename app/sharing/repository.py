"""Accès données partages."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.sharing.models import ProjectShare


class ShareRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, project_id: UUID, owner_id: UUID, token_hash: str, consent_at: datetime) -> ProjectShare:
        share = ProjectShare(project_id=project_id, owner_id=owner_id, token_hash=token_hash, consent_at=consent_at)
        self.session.add(share)
        await self.session.flush()
        return share

    async def get_active_by_hash(self, token_hash: str) -> ProjectShare | None:
        result = await self.session.execute(
            select(ProjectShare).where(ProjectShare.token_hash == token_hash, ProjectShare.is_active.is_(True))
        )
        return result.scalar_one_or_none()

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
