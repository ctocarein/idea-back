"""Accès données diagnostics."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.diagnostics.models import Diagnostic, EntryMode


class DiagnosticRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        project_id: UUID,
        owner_id: UUID,
        mode: EntryMode,
        description: str | None = None,
        answers: dict[str, str] | None = None,
        funding_need: int | None = None,
        document_id: UUID | None = None,
    ) -> Diagnostic:
        diagnostic = Diagnostic(
            project_id=project_id,
            owner_id=owner_id,
            mode=mode,
            description=description,
            answers=answers,
            funding_need=funding_need,
            document_id=document_id,
        )
        self.session.add(diagnostic)
        await self.session.flush()
        return diagnostic

    async def get_by_id(self, diagnostic_id: UUID) -> Diagnostic | None:
        return await self.session.get(Diagnostic, diagnostic_id)

    async def get_latest_for_owner(self, owner_id: UUID) -> Diagnostic | None:
        result = await self.session.execute(
            select(Diagnostic).where(Diagnostic.owner_id == owner_id).order_by(Diagnostic.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()
