"""Lectures du journal d'audit (timeline projet, back-office)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_entity(self, entity: str, entity_id: UUID, *, limit: int = 100) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.entity == entity, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def list_filtered(
        self,
        *,
        actor_id: UUID | None = None,
        action: str | None = None,
        entity: str | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if actor_id is not None:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if entity is not None:
            stmt = stmt.where(AuditLog.entity == entity)
        result = await self.session.execute(stmt)
        return list(result.scalars())
