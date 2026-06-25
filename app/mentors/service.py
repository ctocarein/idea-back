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
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import hash_password
from app.iam.dependencies import AuthContext
from app.iam.invitations import InvitationStatus
from app.iam.models import AccountStatus, Role
from app.iam.repository import UserRepository
from app.mentors.models import MentorApplicationStatus
from app.mentors.repository import MentorRepository
from app.mentors.schemas import (
    ApproveOut,
    MentorApplicationOut,
    MentorApplyIn,
    MentorProfileMeOut,
    MentorProfileUpdateIn,
    MentorPublicOut,
    MentorRequestIn,
    MentorRequestOut,
)

INVITATION_TTL_DAYS = 7


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class MentorService:
    def __init__(self, repo: MentorRepository, users: UserRepository, auditor: AuditService) -> None:
        self.repo = repo
        self.users = users
        self.auditor = auditor
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
