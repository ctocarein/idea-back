"""Accès données notifications."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import Notification


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: UUID,
        type: str,
        payload: dict | None = None,
    ) -> Notification:
        notif = Notification(user_id=user_id, type=type, payload=payload or {})
        self.session.add(notif)
        await self.session.flush()
        return notif

    async def list_for_user(self, user_id: UUID, *, limit: int = 50) -> list[Notification]:
        # Non lues d'abord, puis par date décroissante.
        result = await self.session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.read_at.nulls_first(), Notification.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def get_by_id(self, notif_id: UUID) -> Notification | None:
        return await self.session.get(Notification, notif_id)

    async def mark_read(self, notif: Notification) -> None:
        if notif.read_at is None:
            notif.read_at = datetime.now(UTC)
            await self.session.flush()

    async def mark_all_read(self, user_id: UUID) -> int:
        result = await self.session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(UTC))
        )
        return result.rowcount  # type: ignore[return-value]
