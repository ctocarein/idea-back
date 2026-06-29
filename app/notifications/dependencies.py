"""Assemblage du service notifications."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.notifications.repository import NotificationRepository
from app.notifications.service import NotificationService


def get_notification_service(session: AsyncSession = Depends(get_session)) -> NotificationService:
    return NotificationService(NotificationRepository(session))
