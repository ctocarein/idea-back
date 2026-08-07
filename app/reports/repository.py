"""Accès données reports."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.models import Project
from app.reports.models import Report, ReportStatus


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_pending(self, *, project_id: UUID, diagnostic_id: UUID | None = None) -> Report:
        report = Report(
            project_id=project_id,
            diagnostic_id=diagnostic_id,
            status=ReportStatus.PENDING,
        )
        self.session.add(report)
        await self.session.flush()
        return report

    async def get_by_id(self, report_id: UUID) -> Report | None:
        return await self.session.get(Report, report_id)

    async def list_for_project(self, project_id: UUID) -> list[Report]:
        result = await self.session.execute(
            select(Report).where(Report.project_id == project_id).order_by(Report.created_at.desc())
        )
        return list(result.scalars())

    async def get_latest_for_project(self, project_id: UUID) -> Report | None:
        result = await self.session.execute(
            select(Report).where(Report.project_id == project_id).order_by(Report.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_owner(self, owner_id: UUID) -> list[Report]:
        # Bilans du porteur courant (jointure sur la propriété du projet).
        result = await self.session.execute(
            select(Report)
            .join(Project, Report.project_id == Project.id)
            .where(Project.owner_id == owner_id)
            .order_by(Report.created_at.desc())
        )
        return list(result.scalars())

    async def mark_scored(
        self,
        report: Report,
        *,
        grid_version: str,
        radar_score: dict,
        comprehension: dict,
        next_actions: list | None,
    ) -> None:
        # Phase 1 du bilan : le Radar (score + compréhension) est prêt et exposé TOUT DE
        # SUITE. Le statut reste PENDING (rapport LLM + PDF suivent) ; le front affiche le
        # Radar dès que `radar_score` est présent, sans attendre `READY`.
        report.grid_version = grid_version
        report.radar_score = radar_score
        report.comprehension = comprehension
        report.next_actions = next_actions
        await self.session.flush()

    async def mark_ready(
        self,
        report: Report,
        *,
        grid_version: str,
        radar_score: dict,
        comprehension: dict,
        insights: dict | None,
        next_actions: list | None,
        pdf_document_id: UUID | None,
    ) -> None:
        report.status = ReportStatus.READY
        report.grid_version = grid_version
        report.radar_score = radar_score
        report.comprehension = comprehension
        report.insights = insights
        report.next_actions = next_actions
        report.pdf_document_id = pdf_document_id
        await self.session.flush()

    async def mark_failed(self, report: Report) -> None:
        # Échec définitif du scoring (job épuisé) : sort le bilan de l'attente pour que
        # le porteur voie un état terminal plutôt qu'un spinner infini.
        report.status = ReportStatus.FAILED
        await self.session.flush()
