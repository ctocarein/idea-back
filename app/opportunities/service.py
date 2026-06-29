"""Service opportunités — éligibilité déterministe + expression d'intérêt.

Lit le dernier bilan READY du projet (score global + axe D11 avancement) et le secteur,
puis évalue chaque opportunité active. Aucun LLM : la décision est reproductible.
"""

from __future__ import annotations

from uuid import UUID

from app.core.errors import NotFoundError
from app.iam.dependencies import AuthContext, guard_owner_access
from app.instrumentation.service import OPPORTUNITY_INTEREST, InstrumentationService
from app.opportunities.eligibility import evaluate_eligibility
from app.opportunities.repository import OpportunityRepository
from app.opportunities.schemas import OpportunityAdminOut, OpportunityIn, OpportunityOut
from app.projects.repository import ProjectRepository
from app.reports.models import ReportStatus
from app.reports.repository import ReportRepository


class OpportunityService:
    def __init__(
        self,
        repo: OpportunityRepository,
        projects: ProjectRepository,
        reports: ReportRepository,
        instrumentation: InstrumentationService,
    ) -> None:
        self.repo = repo
        self.projects = projects
        self.reports = reports
        self.instrumentation = instrumentation
        self.session = repo.session

    async def _project_score(self, project_id: UUID) -> tuple[float, int | None, str | None]:
        # (score global /10, avancement D11 /10, secteur) à partir du dernier bilan READY.
        reports = await self.reports.list_for_project(project_id)
        ready = next((r for r in reports if r.status == ReportStatus.READY), None)
        if ready is None:
            return (0.0, None, None)
        overall = float((ready.comprehension or {}).get("overall") or 0.0)
        axes = (ready.radar_score or {}).get("axes") or {}
        raw_d11 = axes.get("d11")
        maturity = int(raw_d11) if raw_d11 is not None else None
        return (overall, maturity, None)

    async def list_for_project(
        self, ctx: AuthContext, project_id: UUID, *, eligible_only: bool = False
    ) -> list[OpportunityOut]:
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("project")
        guard_owner_access(owner_id=project.owner_id, ctx=ctx)

        overall, maturity, _ = await self._project_score(project_id)
        sector = project.sector

        items: list[OpportunityOut] = []
        for opp in await self.repo.list_active():
            eligible, missing = evaluate_eligibility(
                min_overall=float(opp.min_overall),
                min_maturity=opp.min_maturity,
                opp_sector=opp.sector,
                overall=overall,
                maturity=maturity,
                sector=sector,
            )
            if eligible_only and not eligible:
                continue
            out = OpportunityOut.model_validate(opp)
            out.eligible = eligible
            out.missing = missing
            items.append(out)
        # Éligibles d'abord (orientation : « pour quoi suis-je prêt »).
        items.sort(key=lambda o: not o.eligible)
        return items

    # --- Admin CRUD ----------------------------------------------------------

    async def admin_list_all(self, ctx: AuthContext) -> list[OpportunityAdminOut]:
        rows = await self.repo.list_all()
        return [OpportunityAdminOut.model_validate(o) for o in rows]

    async def admin_create(self, ctx: AuthContext, data: OpportunityIn) -> OpportunityAdminOut:
        opp = await self.repo.create_opportunity(
            title=data.title,
            kind=data.kind,
            description=data.description,
            sector=data.sector,
            min_overall=data.min_overall,
            min_maturity=data.min_maturity,
            deadline=data.deadline,
            is_active=data.is_active,
        )
        await self.session.commit()
        return OpportunityAdminOut.model_validate(opp)

    async def admin_update(self, ctx: AuthContext, opp_id: UUID, data: OpportunityIn) -> OpportunityAdminOut:
        opp = await self.repo.get_by_id(opp_id)
        if opp is None:
            raise NotFoundError("opportunity")
        await self.repo.update_opportunity(
            opp,
            data={
                "title": data.title,
                "kind": data.kind,
                "description": data.description,
                "sector": data.sector,
                "min_overall": data.min_overall,
                "min_maturity": data.min_maturity,
                "deadline": data.deadline,
                "is_active": data.is_active,
            },
        )
        await self.session.commit()
        return OpportunityAdminOut.model_validate(opp)

    async def admin_set_active(self, ctx: AuthContext, opp_id: UUID, *, active: bool) -> OpportunityAdminOut:
        opp = await self.repo.get_by_id(opp_id)
        if opp is None:
            raise NotFoundError("opportunity")
        await self.repo.set_active(opp, active=active)
        await self.session.commit()
        return OpportunityAdminOut.model_validate(opp)

    async def express_interest(self, ctx: AuthContext, opportunity_id: UUID, project_id: UUID) -> None:
        opp = await self.repo.get_by_id(opportunity_id)
        if opp is None:
            raise NotFoundError("opportunity")
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("project")
        guard_owner_access(owner_id=project.owner_id, ctx=ctx)
        await self.instrumentation.emit(
            OPPORTUNITY_INTEREST,
            actor_id=ctx.user.id,
            project_id=project_id,
            props={"opportunity_id": str(opportunity_id), "kind": opp.kind.value},
        )
        await self.session.commit()
