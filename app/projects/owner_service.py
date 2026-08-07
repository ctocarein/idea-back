"""Façade projet du porteur : vue agrégée et mémoire versionnée."""

from __future__ import annotations

from uuid import UUID

from app.core.errors import BusinessRuleError, NotFoundError
from app.documents.models import DocumentStatus
from app.documents.repository import DocumentRepository
from app.iam.dependencies import AuthContext, guard_owner_access
from app.project_memory.domain import ensure_dimension
from app.project_memory.models import EvidenceState, MemoryItemType, ProvenanceType
from app.project_memory.repository import ProjectMemoryRepository
from app.project_memory.schemas import FounderMemoryCreateIn, ProjectMemoryItemOut
from app.projects.models import Project
from app.projects.owner_schemas import (
    OwnerProjectOut,
    ProjectWorkspaceOut,
    WorkspaceDocumentsOut,
    WorkspaceMemoryOut,
    WorkspaceReportOut,
)
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository


class ProjectOwnerService:
    def __init__(
        self,
        projects: ProjectRepository,
        memory: ProjectMemoryRepository,
        reports: ReportRepository,
        documents: DocumentRepository,
    ) -> None:
        self.projects = projects
        self.memory = memory
        self.reports = reports
        self.documents = documents
        self.session = projects.session

    async def _owned_project(self, ctx: AuthContext, project_id: UUID) -> Project:
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("project")
        guard_owner_access(owner_id=project.owner_id, ctx=ctx)
        return project

    async def list_mine(self, ctx: AuthContext) -> list[OwnerProjectOut]:
        projects = await self.projects.list_for_owner(ctx.user.id)
        return [OwnerProjectOut.model_validate(project) for project in projects]

    async def get_workspace(self, ctx: AuthContext, project_id: UUID) -> ProjectWorkspaceOut:
        project = await self._owned_project(ctx, project_id)
        latest_report = await self.reports.get_latest_for_project(project_id)
        documents = await self.documents.list_for_project(project_id)
        counts = await self.memory.counts_for_project(project_id)
        recent = await self.memory.list_for_project(project_id, limit=5)

        report_out = None
        next_actions: list = []
        if latest_report is not None:
            next_actions = list(latest_report.next_actions or [])[:3]
            report_out = WorkspaceReportOut(
                id=latest_report.id,
                status=latest_report.status.value,
                grid_version=latest_report.grid_version,
                radar_score=latest_report.radar_score,
                next_actions=list(latest_report.next_actions or []),
                created_at=latest_report.created_at,
            )

        return ProjectWorkspaceOut(
            project=OwnerProjectOut.model_validate(project),
            latest_report=report_out,
            next_actions=next_actions,
            documents=WorkspaceDocumentsOut(
                total=len(documents),
                confirmed=sum(document.status is DocumentStatus.CONFIRMED for document in documents),
            ),
            memory=WorkspaceMemoryOut(
                total_active=counts.total,
                by_state=counts.by_state,
                by_dimension=counts.by_dimension,
                recent=[ProjectMemoryItemOut.model_validate(item) for item in recent],
            ),
        )

    async def list_memory(
        self,
        ctx: AuthContext,
        project_id: UUID,
        *,
        dimension: str | None,
        active_only: bool,
        limit: int,
    ) -> list[ProjectMemoryItemOut]:
        await self._owned_project(ctx, project_id)
        normalized = ensure_dimension(dimension) if dimension else None
        rows = await self.memory.list_for_project(
            project_id,
            dimension=normalized,
            active_only=active_only,
            limit=limit,
        )
        return [ProjectMemoryItemOut.model_validate(item) for item in rows]

    async def add_memory(
        self,
        ctx: AuthContext,
        project_id: UUID,
        body: FounderMemoryCreateIn,
    ) -> ProjectMemoryItemOut:
        await self._owned_project(ctx, project_id)
        dimension = ensure_dimension(body.dimension)
        deduplication_key = f"founder:{body.deduplication_key}" if body.deduplication_key else None
        if deduplication_key:
            existing = await self.memory.get_by_deduplication_key(project_id, deduplication_key)
            if existing is not None:
                return ProjectMemoryItemOut.model_validate(existing)

        superseded = None
        if body.supersedes_id is not None:
            superseded = await self.memory.get_by_id(body.supersedes_id)
            if superseded is None or superseded.project_id != project_id:
                raise NotFoundError("memory_item")
            if not superseded.is_active:
                raise BusinessRuleError("Cette information a déjà été remplacée.")
            if superseded.dimension != dimension:
                raise BusinessRuleError("Une information ne peut remplacer qu'une version de la même dimension.")

        item = await self.memory.create(
            project_id=project_id,
            dimension=dimension,
            item_type=MemoryItemType(body.item_type),
            evidence_state=EvidenceState.DECLARED,
            statement=body.statement.strip(),
            provenance_type=ProvenanceType.USER_ANSWER,
            created_by_id=ctx.user.id,
            deduplication_key=deduplication_key,
            supersedes_id=body.supersedes_id,
            occurred_at=body.occurred_at,
            expires_at=body.expires_at,
        )
        if superseded is not None:
            await self.memory.deactivate(superseded)
        await self.session.commit()
        return ProjectMemoryItemOut.model_validate(item)
