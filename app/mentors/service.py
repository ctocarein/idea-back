"""Service mentors — onboarding (candidature → approbation admin → activation).

Garde-fous : token d'invitation jamais stocké en clair (hash), usage unique, expiration.
L'approbation crée le compte (statut INVITED) ; l'activation pose le mot de passe.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.audit.service import AuditService
from app.core.errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.iam.dependencies import AuthContext
from app.iam.invitations import InvitationStatus
from app.iam.models import AccountStatus, Role
from app.iam.repository import UserRepository
from app.mentors.models import FOUNDER_TRANSITIONS, MENTOR_TRANSITIONS, MentorApplicationStatus, MentorRequestStatus
from app.mentors.repository import MentorRepository
from app.mentors.schemas import (
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
from app.projects.repository import ProjectRepository

INVITATION_TTL_DAYS = 7


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class MentorService:
    def __init__(self, repo: MentorRepository, users: UserRepository, auditor: AuditService, projects: ProjectRepository | None = None) -> None:  # noqa: E501
        self.repo = repo
        self.users = users
        self.auditor = auditor
        self.projects = projects
        self.session = repo.session

    async def apply(self, data: MentorApplyIn) -> MentorApplicationOut:
        app = await self.repo.create_application(
            full_name=data.full_name,
            email=str(data.email),
            sectors=data.sectors,
            bio=data.bio,
            cv_url=data.cv_url,
        )
        await self.session.commit()
        return MentorApplicationOut.model_validate(app)

    async def list_applications(self, status: MentorApplicationStatus | None = None) -> list[MentorApplicationOut]:
        rows = await self.repo.list_applications(status)
        return [MentorApplicationOut.model_validate(a) for a in rows]

    async def approve(self, ctx: AuthContext, application_id: UUID) -> ApproveOut:
        app = await self.repo.get_application(application_id)
        if app is None:
            raise NotFoundError("mentor_application")
        if app.status is not MentorApplicationStatus.PENDING:
            raise BusinessRuleError("Candidature déjà traitée.")
        if await self.users.get_by_email(app.email) is not None:
            raise ConflictError("Un compte existe déjà pour cet email.")

        # Compte mentor en attente d'activation + profil + invitation à token.
        user = await self.users.create(
            email=app.email,
            password_hash=hash_password(secrets.token_urlsafe(16)),  # placeholder, remplacé à l'activation
            full_name=app.full_name,
            role=Role.MENTOR,
            status=AccountStatus.INVITED,
        )
        await self.repo.create_profile(user_id=user.id, sectors=app.sectors, bio=app.bio, cv_url=app.cv_url)
        token = secrets.token_urlsafe(32)
        await self.repo.create_invitation(
            email=app.email,
            token_hash=_hash_token(token),
            invited_by=ctx.user.id,
            expires_at=datetime.now(UTC) + timedelta(days=INVITATION_TTL_DAYS),
        )
        app.status = MentorApplicationStatus.APPROVED
        app.reviewed_by = ctx.user.id
        app.reviewed_at = datetime.now(UTC)
        app.created_user_id = user.id
        await self.session.flush()
        await self.auditor.record(
            actor_id=ctx.user.id,
            action="mentor.approved",
            entity="mentor_application",
            entity_id=app.id,
            new_value={"email": app.email, "user_id": str(user.id)},
        )
        await self.session.commit()
        return ApproveOut(user_id=user.id, invitation_token=token)

    async def reject(self, ctx: AuthContext, application_id: UUID) -> MentorApplicationOut:
        app = await self.repo.get_application(application_id)
        if app is None:
            raise NotFoundError("mentor_application")
        if app.status is not MentorApplicationStatus.PENDING:
            raise BusinessRuleError("Candidature déjà traitée.")
        app.status = MentorApplicationStatus.REJECTED
        app.reviewed_by = ctx.user.id
        app.reviewed_at = datetime.now(UTC)
        await self.session.flush()
        await self.auditor.record(
            actor_id=ctx.user.id,
            action="mentor.rejected",
            entity="mentor_application",
            entity_id=app.id,
        )
        await self.session.commit()
        return MentorApplicationOut.model_validate(app)

    async def accept_invitation(self, token: str, password: str) -> None:
        inv = await self.repo.get_invitation_by_hash(_hash_token(token))
        if inv is None:
            raise NotFoundError("invitation")
        if inv.status is not InvitationStatus.PENDING:
            raise BusinessRuleError("Invitation déjà utilisée ou révoquée.")
        if inv.expires_at < datetime.now(UTC):
            raise BusinessRuleError("Invitation expirée.")
        user = await self.users.get_by_email(inv.email)
        if user is None:
            raise NotFoundError("user")
        user.password_hash = hash_password(password)
        user.status = AccountStatus.ACTIVE
        await self.repo.mark_invitation_accepted(inv)
        await self.auditor.record(actor_id=user.id, action="invitation.accepted", entity="invitation", entity_id=inv.id)
        await self.session.commit()

    # --- Profil (MENTOR-02) ---

    async def get_my_profile(self, ctx: AuthContext) -> MentorProfileMeOut:
        profile = await self.repo.get_profile_by_user(ctx.user.id)
        if profile is None:
            raise NotFoundError("mentor_profile")
        return MentorProfileMeOut.model_validate(profile)

    async def update_my_profile(self, ctx: AuthContext, data: MentorProfileUpdateIn) -> MentorProfileMeOut:
        profile = await self.repo.get_profile_by_user(ctx.user.id)
        if profile is None:
            raise NotFoundError("mentor_profile")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)
        await self.session.commit()
        return MentorProfileMeOut.model_validate(profile)

    # --- Marketplace (MENTOR-03) ---

    async def list_marketplace(self, sector: str | None = None) -> list[MentorPublicOut]:
        rows = await self.repo.list_active_profiles(sector)
        return [
            MentorPublicOut(
                user_id=p.user_id,
                full_name=name,
                sectors=p.sectors,
                bio=p.bio,
                hourly_rate=float(p.hourly_rate) if p.hourly_rate is not None else None,
            )
            for p, name in rows
        ]

    async def request_mentor(self, ctx: AuthContext, mentor_user_id: UUID, data: MentorRequestIn) -> MentorRequestOut:
        profile = await self.repo.get_profile_by_user(mentor_user_id)
        if profile is None or not profile.is_active:
            raise NotFoundError("mentor")
        # SEC-07 : vérifier que le projet associé appartient bien au demandeur.
        if data.project_id is not None and self.projects is not None:
            project = await self.projects.get_by_id(data.project_id)
            if project is None or project.owner_id != ctx.user.id:
                raise ForbiddenError("Ce projet ne vous appartient pas.")
        req = await self.repo.create_request(
            founder_id=ctx.user.id,
            mentor_user_id=mentor_user_id,
            project_id=data.project_id,
            message=data.message,
        )
        await self.auditor.record(
            actor_id=ctx.user.id,
            action="mentor.requested",
            entity="mentor_request",
            entity_id=req.id,
            new_value={"mentor_user_id": str(mentor_user_id)},
        )
        await self.session.commit()
        return MentorRequestOut.model_validate(req)

    # --- Transitions MentorRequest (V1-07) ---

    def _to_detail(self, req, other_name: str, *, other_is_mentor: bool) -> MentorRequestDetailOut:
        return MentorRequestDetailOut(
            id=req.id,
            status=req.status,
            message=req.message,
            mentor_user_id=req.mentor_user_id,
            mentor_name=other_name if other_is_mentor else "–",
            founder_id=req.founder_id,
            founder_name=other_name if not other_is_mentor else "–",
            project_id=req.project_id,
            session_at=req.session_at,
            created_at=req.created_at,
            updated_at=req.updated_at,
        )

    async def my_requests(self, ctx: AuthContext) -> list[MentorRequestDetailOut]:
        # Porteur : ses demandes → other_name est le mentor.
        rows = await self.repo.list_by_founder(ctx.user.id)
        return [self._to_detail(req, name, other_is_mentor=True) for req, name in rows]

    async def mentor_incoming_requests(self, ctx: AuthContext) -> list[MentorRequestDetailOut]:
        # Mentor : demandes reçues → other_name est le porteur.
        rows = await self.repo.list_by_mentor(ctx.user.id)
        return [self._to_detail(req, name, other_is_mentor=False) for req, name in rows]

    async def respond_request(self, ctx: AuthContext, request_id: UUID, *, accept: bool) -> MentorRequestDetailOut:
        req = await self.repo.get_request(request_id)
        if req is None:
            raise NotFoundError("mentor_request")
        if req.mentor_user_id != ctx.user.id:
            raise ForbiddenError()
        target = MentorRequestStatus.ACCEPTED if accept else MentorRequestStatus.DECLINED
        if target not in MENTOR_TRANSITIONS.get(req.status, set()):
            raise BusinessRuleError(f"Transition {req.status} → {target} non autorisée.")
        await self.repo.transition_request(req, status=target)
        await self.auditor.record(
            actor_id=ctx.user.id,
            action=f"mentor_request.{target}",
            entity="mentor_request",
            entity_id=req.id,
        )
        await self.session.commit()
        # Recharger le nom du porteur pour le DTO.
        rows = await self.repo.list_by_mentor(ctx.user.id)
        for r, name in rows:
            if r.id == req.id:
                return self._to_detail(r, name, other_is_mentor=False)
        return self._to_detail(req, "–", other_is_mentor=False)

    async def plan_session(self, ctx: AuthContext, request_id: UUID, data: SessionPlanIn) -> MentorRequestDetailOut:
        req = await self.repo.get_request(request_id)
        if req is None:
            raise NotFoundError("mentor_request")
        if req.mentor_user_id != ctx.user.id:
            raise ForbiddenError()
        target = MentorRequestStatus.SESSION_PLANNED
        if target not in MENTOR_TRANSITIONS.get(req.status, set()):
            raise BusinessRuleError(f"Transition {req.status} → {target} non autorisée.")
        await self.repo.transition_request(req, status=target, session_at=data.session_at)
        await self.auditor.record(
            actor_id=ctx.user.id,
            action="mentor_request.session_planned",
            entity="mentor_request",
            entity_id=req.id,
            new_value={"session_at": str(data.session_at)},
        )
        await self.session.commit()
        rows = await self.repo.list_by_mentor(ctx.user.id)
        for r, name in rows:
            if r.id == req.id:
                return self._to_detail(r, name, other_is_mentor=False)
        return self._to_detail(req, "–", other_is_mentor=False)

    async def complete_request(self, ctx: AuthContext, request_id: UUID) -> MentorRequestDetailOut:
        req = await self.repo.get_request(request_id)
        if req is None:
            raise NotFoundError("mentor_request")
        if req.mentor_user_id != ctx.user.id:
            raise ForbiddenError()
        target = MentorRequestStatus.DONE
        if target not in MENTOR_TRANSITIONS.get(req.status, set()):
            raise BusinessRuleError(f"Transition {req.status} → {target} non autorisée.")
        await self.repo.transition_request(req, status=target)
        await self.auditor.record(
            actor_id=ctx.user.id,
            action="mentor_request.done",
            entity="mentor_request",
            entity_id=req.id,
        )
        await self.session.commit()
        rows = await self.repo.list_by_mentor(ctx.user.id)
        for r, name in rows:
            if r.id == req.id:
                return self._to_detail(r, name, other_is_mentor=False)
        return self._to_detail(req, "–", other_is_mentor=False)

    async def cancel_request(self, ctx: AuthContext, request_id: UUID) -> MentorRequestDetailOut:
        req = await self.repo.get_request(request_id)
        if req is None:
            raise NotFoundError("mentor_request")
        if req.founder_id != ctx.user.id:
            raise ForbiddenError()
        target = MentorRequestStatus.CANCELLED
        if target not in FOUNDER_TRANSITIONS.get(req.status, set()):
            raise BusinessRuleError(f"Annulation impossible en statut {req.status}.")
        await self.repo.transition_request(req, status=target)
        await self.auditor.record(
            actor_id=ctx.user.id,
            action="mentor_request.cancelled",
            entity="mentor_request",
            entity_id=req.id,
        )
        await self.session.commit()
        rows = await self.repo.list_by_founder(ctx.user.id)
        for r, name in rows:
            if r.id == req.id:
                return self._to_detail(r, name, other_is_mentor=True)
        return self._to_detail(req, "–", other_is_mentor=True)

    # --- Curation admin (ADMIN-02) ---

    async def set_mentor_status(self, ctx: AuthContext, user_id: UUID, *, suspend: bool) -> None:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("user")
        if user.role is not Role.MENTOR:
            raise BusinessRuleError("Cet utilisateur n'est pas un mentor.")
        user.status = AccountStatus.SUSPENDED if suspend else AccountStatus.ACTIVE
        profile = await self.repo.get_profile_by_user(user_id)
        if profile is not None:
            profile.is_active = not suspend  # retiré de la marketplace si suspendu
        await self.auditor.record(
            actor_id=ctx.user.id,
            action="mentor.suspended" if suspend else "mentor.activated",
            entity="user",
            entity_id=user_id,
        )
        await self.session.commit()
