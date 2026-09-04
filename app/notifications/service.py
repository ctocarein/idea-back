"""Service notifications — liste, lecture, création."""

from __future__ import annotations

from uuid import UUID

from jwt import PyJWTError

from app.core.errors import BusinessRuleError, NotFoundError
from app.core.security import decode_unsubscribe_token
from app.iam.dependencies import AuthContext, guard_owner_access
from app.iam.repository import UserRepository
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


class UnsubscribeService:
    """Désabonnement des rappels — SANS authentification, par token signé.

    Le lien est cliqué depuis une boîte mail : exiger une session le rendrait inutilisable
    pour qui n'est pas déjà connecté, et un désabonnement qui demande un effort n'est pas
    un désabonnement — c'est un signalement en spam.

    Ne touche QUE les rappels : les emails transactionnels (vérification d'adresse)
    continuent de partir.
    """

    def __init__(self, users: UserRepository) -> None:
        self.users = users
        self.session = users.session

    async def unsubscribe(self, token: str) -> None:
        try:
            user_id = decode_unsubscribe_token(token)
        except (PyJWTError, ValueError) as exc:
            raise BusinessRuleError("Lien de désabonnement invalide.") from exc
        user = await self.users.get_by_id(user_id)
        if user is None:
            # Compte supprimé : l'objectif du porteur est déjà atteint, on ne divulgue rien.
            return
        user.reminders_opt_out = True
        await self.session.commit()
