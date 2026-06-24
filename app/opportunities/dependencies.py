"""Assemblage du service opportunités."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.instrumentation.service import InstrumentationService
from app.opportunities.repository import OpportunityRepository
from app.opportunities.service import OpportunityService
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository


def get_opportunity_service(session: AsyncSession = Depends(get_session)) -> OpportunityService:
    return OpportunityService(
        OpportunityRepository(session),
        ProjectRepository(session),
        ReportRepository(session),
        InstrumentationService(session),
    )
