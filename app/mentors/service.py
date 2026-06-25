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
from app.mentors.schemas import ApproveOut, MentorApplicationOut, MentorApplyIn

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
