"""Service notifications — liste, lecture, création."""

from __future__ import annotations

from uuid import UUID

from app.core.errors import NotFoundError
from app.iam.dependencies import AuthContext, guard_owner_access
from app.notifications.models import Notification
from app.notifications.repository import NotificationRepository
from app.notifications.schemas import NotificationOut


class NotificationService:
    def __init__(self, repo: NotificationRepository) -> None:
        self.repo = repo
        self.session = repo.session

    async def list_for_user(self, ctx: AuthContext) -> list[NotificationOut]:
        rows = await self.repo.list_for_user(ctx.user.id)
        return [NotificationOut.model_validate(n) for n in rows]

    async def mark_read(self, ctx: AuthContext, notif_id: UUID) -> NotificationOut:
        notif = await self.repo.get_by_id(notif_id)
        if notif is None:
            raise NotFoundError("notification")
        guard_owner_access(owner_id=notif.user_id, ctx=ctx)
        await self.repo.mark_read(notif)
        await self.session.commit()
        return NotificationOut.model_validate(notif)

    async def mark_all_read(self, ctx: AuthContext) -> dict:
        updated = await self.repo.mark_all_read(ctx.user.id)
        await self.session.commit()
        return {"updated": updated}

    async def create(
        self,
        *,
        user_id: UUID,
        type: str,
        payload: dict | None = None,
    ) -> Notification:
        """Crée une notification (appelé depuis les handlers worker / services)."""
        return await self.repo.create(user_id=user_id, type=type, payload=payload)
