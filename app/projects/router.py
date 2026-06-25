"""Routes back-office projets (admin / analyste) — liste, détail, curation, assignation."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.audit.dependencies import get_audit_repo
from app.audit.repository import AuditRepository
from app.audit.schemas import AuditLogOut
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.projects.dependencies import get_project_admin_service
from app.projects.models import DiagnosticStatus, ReviewStatus
from app.projects.schemas import AssigneeIn, ProjectAdminOut, ReviewTransitionIn
from app.projects.service import ProjectAdminService

router = APIRouter(prefix="/admin/projects", tags=["admin-projects"])


@router.get("", response_model=list[ProjectAdminOut])
async def list_projects(
    review_status: ReviewStatus | None = None,
    diagnostic_status: DiagnosticStatus | None = None,
    sector: str | None = None,
    assignee_id: UUID | None = None,
    ctx: AuthContext = Depends(require(Permission.PROJECT_READ_ANY)),
    svc: ProjectAdminService = Depends(get_project_admin_service),
) -> list[ProjectAdminOut]:
    return await svc.list_projects(
        review_status=review_status,
        diagnostic_status=diagnostic_status,
        sector=sector,
        assignee_id=assignee_id,
    )


@router.get("/{project_id}", response_model=ProjectAdminOut)
async def get_project(
    project_id: UUID,
    ctx: AuthContext = Depends(require(Permission.PROJECT_READ_ANY)),
    svc: ProjectAdminService = Depends(get_project_admin_service),
) -> ProjectAdminOut:
    return await svc.get_detail(project_id)


@router.patch("/{project_id}/review-status", response_model=ProjectAdminOut)
async def transition_review(
    project_id: UUID,
    body: ReviewTransitionIn,
    ctx: AuthContext = Depends(require(Permission.PROJECT_READ_ANY)),
    svc: ProjectAdminService = Depends(get_project_admin_service),
) -> ProjectAdminOut:
    # Curation : new_diagnostic → in_review → qualified/needs_work/rejected → excellence (machine).
    return await svc.transition_review(ctx, project_id, body.target)


@router.patch("/{project_id}/assignee", response_model=ProjectAdminOut)
async def assign_project(
    project_id: UUID,
    body: AssigneeIn,
    ctx: AuthContext = Depends(require(Permission.USER_MANAGE)),
    svc: ProjectAdminService = Depends(get_project_admin_service),
) -> ProjectAdminOut:
    # Assignation à un analyste/mentor (admin uniquement).
    return await svc.assign(ctx, project_id, body.assignee_id)


@router.get("/{project_id}/timeline", response_model=list[AuditLogOut])
async def project_timeline(
    project_id: UUID,
    ctx: AuthContext = Depends(require(Permission.AUDIT_READ)),
    audit: AuditRepository = Depends(get_audit_repo),
) -> list[AuditLogOut]:
    # Journal d'audit du projet (transitions, assignations…).
    rows = await audit.list_for_entity("project", project_id)
    return [AuditLogOut.model_validate(a) for a in rows]
