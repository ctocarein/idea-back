"""Routes notifications — liste, lecture individuelle, tout marquer comme lu."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.iam.dependencies import AuthContext, get_current_user
from app.notifications.dependencies import get_notification_service
from app.notifications.schemas import NotificationOut
from app.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    ctx: AuthContext = Depends(get_current_user),
    svc: NotificationService = Depends(get_notification_service),
) -> list[NotificationOut]:
    return await svc.list_for_user(ctx)


@router.patch("/{notif_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notif_id: UUID,
    ctx: AuthContext = Depends(get_current_user),
    svc: NotificationService = Depends(get_notification_service),
) -> NotificationOut:
    return await svc.mark_read(ctx, notif_id)


@router.post(
    "/mark-all-read",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def mark_all_notifications_read(
    ctx: AuthContext = Depends(get_current_user),
    svc: NotificationService = Depends(get_notification_service),
) -> dict:
    return await svc.mark_all_read(ctx)
