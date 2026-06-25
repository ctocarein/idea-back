"""Routes mentors — candidature & activation (publiques) + revue (admin)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission
from app.mentors.dependencies import get_mentor_service
from app.mentors.models import MentorApplicationStatus
from app.mentors.schemas import (
    AcceptInvitationIn,
    ApproveOut,
    MentorApplicationOut,
    MentorApplyIn,
)
from app.mentors.service import MentorService

router = APIRouter(tags=["mentors"])


@router.post("/mentors/apply", response_model=MentorApplicationOut, status_code=201)
async def apply(
    body: MentorApplyIn,
    svc: MentorService = Depends(get_mentor_service),
) -> MentorApplicationOut:
    # Candidature publique (le mentor n'a pas encore de compte).
    return await svc.apply(body)


@router.post("/mentors/accept-invitation", status_code=status.HTTP_204_NO_CONTENT)
async def accept_invitation(
    body: AcceptInvitationIn,
    svc: MentorService = Depends(get_mentor_service),
) -> None:
    # Activation : pose le mot de passe et active le compte (token usage unique).
    await svc.accept_invitation(body.token, body.password)


@router.get("/admin/mentor-applications", response_model=list[MentorApplicationOut])
async def list_applications(
    status: MentorApplicationStatus | None = None,
    ctx: AuthContext = Depends(require(Permission.MENTOR_APPROVE)),
    svc: MentorService = Depends(get_mentor_service),
) -> list[MentorApplicationOut]:
    return await svc.list_applications(status)


@router.post("/admin/mentor-applications/{application_id}/approve", response_model=ApproveOut)
async def approve(
    application_id: UUID,
    ctx: AuthContext = Depends(require(Permission.MENTOR_APPROVE)),
    svc: MentorService = Depends(get_mentor_service),
) -> ApproveOut:
    # Crée le compte mentor (INVITED) + invitation à token.
    return await svc.approve(ctx, application_id)


@router.post("/admin/mentor-applications/{application_id}/reject", response_model=MentorApplicationOut)
async def reject(
    application_id: UUID,
    ctx: AuthContext = Depends(require(Permission.MENTOR_APPROVE)),
    svc: MentorService = Depends(get_mentor_service),
) -> MentorApplicationOut:
    return await svc.reject(ctx, application_id)
