"""Service reports — lecture du bilan avec garde de propriété.

Le porteur ne voit QUE ses bilans (permission REPORT_READ_OWN + propriété du projet) ;
l'admin voit tout (PROJECT_READ_ANY). « Avoir la permission ne suffit pas » : on combine
permission ET appartenance (cf. archi §5.4).
"""

from __future__ import annotations

from uuid import UUID

from app.core.errors import ConflictError, NotFoundError
from app.core.storage import get_storage
from app.iam.dependencies import AuthContext, guard_owner_access
from app.instrumentation.service import ACTION_STARTED, BILAN_VIEWED, InstrumentationService
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository
from app.reports.schemas import ReportDetailOut, ReportOut


class ReportService:
    def __init__(
        self,
        reports: ReportRepository,
        projects: ProjectRepository,
        instrumentation: InstrumentationService | None = None,
    ) -> None:
        self.reports = reports
        self.projects = projects
        self.instrumentation = instrumentation
        self.session = reports.session

    async def list_mine(self, ctx: AuthContext) -> list[ReportOut]:
        rows = await self.reports.list_for_owner(ctx.user.id)
        return [ReportOut.model_validate(r) for r in rows]

    async def get_detail(self, report_id: UUID, ctx: AuthContext) -> ReportDetailOut:
        report = await self.reports.get_by_id(report_id)
        if report is None:
            raise NotFoundError("report")
        project = await self.projects.get_by_id(report.project_id)
        if project is None:
            raise NotFoundError("project")
        # Permission + propriété (admin passe via PROJECT_READ_ANY).
        guard_owner_access(owner_id=project.owner_id, ctx=ctx)
        # Funnel : on capte la consultation du bilan (entrée du maillon bilan → action),
        # mais SEULEMENT celle du porteur. Le funnel compte des acteurs distincts : un admin
        # ou un analyste qui ouvre un bilan pour le relire gonflerait le premier étage et
        # écraserait le taux de conversion — la métrique nord mesurerait notre propre activité.
        if self.instrumentation is not None and project.owner_id == ctx.user.id:
            await self.instrumentation.emit(
                BILAN_VIEWED,
                actor_id=ctx.user.id,
                project_id=report.project_id,
                props={"status": report.status.value},
            )
            await self.session.commit()
        return ReportDetailOut.model_validate(report)

    async def start_action(self, report_id: UUID, ctx: AuthContext, action_key: str) -> None:
        # Le porteur démarre une prochaine action (sortie du maillon) → event mesurable,
        # même avant que la feature cible (Academy/pitch) résolve le lien.
        report = await self.reports.get_by_id(report_id)
        if report is None:
            raise NotFoundError("report")
        project = await self.projects.get_by_id(report.project_id)
        if project is None:
            raise NotFoundError("project")
        guard_owner_access(owner_id=project.owner_id, ctx=ctx)
        if self.instrumentation is not None:
            await self.instrumentation.emit(
                ACTION_STARTED,
                actor_id=ctx.user.id,
                project_id=report.project_id,
                props={"action_key": action_key},
            )
            await self.session.commit()

    async def get_html(self, report_id: UUID, ctx: AuthContext) -> str:
        from datetime import UTC, datetime

        from app.reports.pdf import render_bilan_html
        from app.scoring.constants import (
            AXES,
            GRID_VERSION_ACTIVE,
            MATURITY_LEVELS,
            PILLARS,
            SCALE_MAX,
        )

        report = await self.reports.get_by_id(report_id)
        if report is None:
            raise NotFoundError("report")
        project = await self.projects.get_by_id(report.project_id)
        if project is None:
            raise NotFoundError("project")
        guard_owner_access(owner_id=project.owner_id, ctx=ctx)

        radar = report.radar_score or {}
        comprehension = report.comprehension or {}

        # Le global est LU, jamais réagrégé ici (SPEC_SCORING_INTEGRITY C3) : `radar_score`
        # le porte depuis la correction, `comprehension` pour les bilans antérieurs.
        overall = radar.get("overall")
        if overall is None:
            overall = comprehension.get("overall", 0)
        # Absent des bilans d'avant C2 → on ne prétend pas que le secteur est calibré.
        calibrated = radar.get("sectorCalibrated")

        return render_bilan_html(
            project_title=project.title,
            category=project.sector or "",
            grid_pillars=PILLARS,
            grid_axes=AXES,
            scores=radar.get("axes", {}),
            pillar_scores=radar.get("pillars") or comprehension.get("pillars", {}),
            overall=int(overall or 0),
            scale_max=SCALE_MAX,
            sector_calibrated=bool(calibrated) if calibrated is not None else True,
            maturity_levels=MATURITY_LEVELS,
            grid_version=radar.get("gridVersion", GRID_VERSION_ACTIVE),
            generated_at=datetime.now(UTC).strftime("%d/%m/%Y"),
            report=report.insights,
            next_actions=report.next_actions or [],
        )

    async def get_pdf_url(self, report_id: UUID, ctx: AuthContext) -> str:
        report = await self.reports.get_by_id(report_id)
        if report is None:
            raise NotFoundError("report")
        project = await self.projects.get_by_id(report.project_id)
        if project is None:
            raise NotFoundError("project")
        guard_owner_access(owner_id=project.owner_id, ctx=ctx)
        if report.pdf_document_id is None:
            raise ConflictError("PDF en préparation.")
        storage = get_storage()
        if storage is None:
            raise NotFoundError("Stockage indisponible.")
        return await storage.apresigned_get(f"bilans/{report.id}.pdf")
