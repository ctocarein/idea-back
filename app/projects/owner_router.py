"""Routes de l'espace projet centré sur le porteur."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.iam.dependencies import AuthContext, get_current_user
from app.project_memory.evaluation_dependencies import get_project_evaluation_service
from app.project_memory.evaluation_schemas import ProjectEvaluationOut
from app.project_memory.evaluation_service import ProjectEvaluationService
from app.project_memory.schemas import FounderMemoryCreateIn, ProjectMemoryItemOut
from app.projects.owner_dependencies import get_project_owner_service
from app.projects.owner_schemas import OwnerProjectOut, ProjectWorkspaceOut
from app.projects.owner_service import ProjectOwnerService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[OwnerProjectOut])
async def list_my_projects(
    ctx: AuthContext = Depends(get_current_user),
    svc: ProjectOwnerService = Depends(get_project_owner_service),
) -> list[OwnerProjectOut]:
    return await svc.list_mine(ctx)


@router.get("/{project_id}/workspace", response_model=ProjectWorkspaceOut)
async def get_project_workspace(
    project_id: UUID,
    ctx: AuthContext = Depends(get_current_user),
    svc: ProjectOwnerService = Depends(get_project_owner_service),
) -> ProjectWorkspaceOut:
    return await svc.get_workspace(ctx, project_id)


@router.get("/{project_id}/evaluation", response_model=ProjectEvaluationOut)
async def get_project_evaluation(
    project_id: UUID,
    ctx: AuthContext = Depends(get_current_user),
    svc: ProjectEvaluationService = Depends(get_project_evaluation_service),
) -> ProjectEvaluationOut:
    return await svc.get_for_owner(ctx, project_id)


@router.get("/{project_id}/memory", response_model=list[ProjectMemoryItemOut])
async def list_project_memory(
    project_id: UUID,
    dimension: str | None = None,
    active_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    ctx: AuthContext = Depends(get_current_user),
    svc: ProjectOwnerService = Depends(get_project_owner_service),
) -> list[ProjectMemoryItemOut]:
    return await svc.list_memory(
        ctx,
        project_id,
        dimension=dimension,
        active_only=active_only,
        limit=limit,
    )


@router.post("/{project_id}/memory", response_model=ProjectMemoryItemOut, status_code=status.HTTP_201_CREATED)
async def add_project_memory(
    project_id: UUID,
    body: FounderMemoryCreateIn,
    ctx: AuthContext = Depends(get_current_user),
    svc: ProjectOwnerService = Depends(get_project_owner_service),
) -> ProjectMemoryItemOut:
    return await svc.add_memory(ctx, project_id, body)
