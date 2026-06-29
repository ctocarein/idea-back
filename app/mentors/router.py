"""Routes mentors — candidature & activation (publiques) + revue (admin)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.iam.dependencies import AuthContext, get_current_user, require
from app.iam.permissions import Permission
from app.mentors.dependencies import get_mentor_service
from app.mentors.models import MentorApplicationStatus
from app.mentors.schemas import (
    AcceptInvitationIn,
    ApproveOut,
    MentorApplicationOut,
    MentorApplyIn,
    MentorProfileMeOut,
    MentorProfileUpdateIn,
    MentorPublicOut,
    MentorRequestDetailOut,
    MentorRequestIn,
    MentorRequestOut,
    SessionPlanIn,
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


@router.get("/mentors/me", response_model=MentorProfileMeOut)
async def get_my_profile(
    ctx: AuthContext = Depends(get_current_user),
    svc: MentorService = Depends(get_mentor_service),
) -> MentorProfileMeOut:
    return await svc.get_my_profile(ctx)


@router.patch("/mentors/me", response_model=MentorProfileMeOut)
async def update_my_profile(
    body: MentorProfileUpdateIn,
    ctx: AuthContext = Depends(get_current_user),
    svc: MentorService = Depends(get_mentor_service),
) -> MentorProfileMeOut:
    return await svc.update_my_profile(ctx, body)


@router.get("/mentors", response_model=list[MentorPublicOut])
async def list_mentors(
    sector: str | None = None,
    ctx: AuthContext = Depends(get_current_user),
    svc: MentorService = Depends(get_mentor_service),
) -> list[MentorPublicOut]:
    # Marketplace découverte (côté porteur) — profils actifs, filtrables par secteur.
    return await svc.list_marketplace(sector)


@router.post("/mentors/{mentor_user_id}/request", response_model=MentorRequestOut, status_code=201)
async def request_mentor(
    mentor_user_id: UUID,
    body: MentorRequestIn,
    ctx: AuthContext = Depends(get_current_user),
    svc: MentorService = Depends(get_mentor_service),
) -> MentorRequestOut:
    # Demande d'accompagnement (booking/paiement = v2).
    return await svc.request_mentor(ctx, mentor_user_id, body)


@router.get("/me/mentor-requests", response_model=list[MentorRequestDetailOut])
async def my_mentor_requests(
    ctx: AuthContext = Depends(get_current_user),
    svc: MentorService = Depends(get_mentor_service),
) -> list[MentorRequestDetailOut]:
    # Porteur : ses demandes envoyées (toutes) avec statut en temps réel.
    return await svc.my_requests(ctx)


@router.get("/mentors/me/requests", response_model=list[MentorRequestDetailOut])
async def mentor_incoming_requests(
    ctx: AuthContext = Depends(get_current_user),
    svc: MentorService = Depends(get_mentor_service),
) -> list[MentorRequestDetailOut]:
    # Mentor : demandes reçues.
    return await svc.mentor_incoming_requests(ctx)


@router.patch("/mentor-requests/{request_id}/accept", response_model=MentorRequestDetailOut)
async def accept_request(
    request_id: UUID,
    ctx: AuthContext = Depends(get_current_user),
    svc: MentorService = Depends(get_mentor_service),
) -> MentorRequestDetailOut:
    return await svc.respond_request(ctx, request_id, accept=True)


@router.patch("/mentor-requests/{request_id}/decline", response_model=MentorRequestDetailOut)
async def decline_request(
    request_id: UUID,
    ctx: AuthContext = Depends(get_current_user),
    svc: MentorService = Depends(get_mentor_service),
) -> MentorRequestDetailOut:
    return await svc.respond_request(ctx, request_id, accept=False)


@router.patch("/mentor-requests/{request_id}/plan-session", response_model=MentorRequestDetailOut)
async def plan_session(
    request_id: UUID,
    body: SessionPlanIn,
    ctx: AuthContext = Depends(get_current_user),
    svc: MentorService = Depends(get_mentor_service),
) -> MentorRequestDetailOut:
    return await svc.plan_session(ctx, request_id, body)


@router.patch("/mentor-requests/{request_id}/complete", response_model=MentorRequestDetailOut)
async def complete_request(
    request_id: UUID,
    ctx: AuthContext = Depends(get_current_user),
    svc: MentorService = Depends(get_mentor_service),
) -> MentorRequestDetailOut:
    return await svc.complete_request(ctx, request_id)


@router.patch("/mentor-requests/{request_id}/cancel", response_model=MentorRequestDetailOut)
async def cancel_request(
    request_id: UUID,
    ctx: AuthContext = Depends(get_current_user),
    svc: MentorService = Depends(get_mentor_service),
) -> MentorRequestDetailOut:
    return await svc.cancel_request(ctx, request_id)


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


@router.post("/admin/mentors/{user_id}/suspend", status_code=204)
async def suspend_mentor(
    user_id: UUID,
    ctx: AuthContext = Depends(require(Permission.USER_MANAGE)),
    svc: MentorService = Depends(get_mentor_service),
) -> None:
    await svc.set_mentor_status(ctx, user_id, suspend=True)


@router.post("/admin/mentors/{user_id}/activate", status_code=204)
async def activate_mentor(
    user_id: UUID,
    ctx: AuthContext = Depends(require(Permission.USER_MANAGE)),
    svc: MentorService = Depends(get_mentor_service),
) -> None:
    await svc.set_mentor_status(ctx, user_id, suspend=False)
