"""Assemblage du repo d'audit (lecture)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditRepository
from app.core.database import get_session


def get_audit_repo(session: AsyncSession = Depends(get_session)) -> AuditRepository:
    return AuditRepository(session)
