"""Assemblage du service mentors."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.core.database import get_session
from app.iam.repository import UserRepository
from app.mentors.repository import MentorRepository
from app.mentors.service import MentorService


def get_mentor_service(session: AsyncSession = Depends(get_session)) -> MentorService:
    return MentorService(MentorRepository(session), UserRepository(session), AuditService(session))
