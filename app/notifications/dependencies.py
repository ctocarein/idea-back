"""Assemblage du service notifications."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.iam.repository import UserRepository
from app.notifications.repository import NotificationRepository
from app.notifications.service import NotificationService, UnsubscribeService


def get_notification_service(session: AsyncSession = Depends(get_session)) -> NotificationService:
    return NotificationService(NotificationRepository(session))


def get_unsubscribe_service(session: AsyncSession = Depends(get_session)) -> UnsubscribeService:
    return UnsubscribeService(UserRepository(session))
