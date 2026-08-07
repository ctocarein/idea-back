"""Accès données mentors — candidatures, profils, invitations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.iam.invitations import Invitation, InvitationStatus
from app.iam.models import Role, User
from app.mentors.models import (
    MentorApplication,
    MentorApplicationStatus,
    MentorProfile,
    MentorRequest,
)


class MentorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Candidatures ---

    async def create_application(
        self, *, full_name: str, email: str, sectors: list[str], bio: str, cv_url: str | None
    ) -> MentorApplication:
        app = MentorApplication(full_name=full_name, email=email, sectors=sectors, bio=bio, cv_url=cv_url)
        self.session.add(app)
        await self.session.flush()
        return app

    async def get_application(self, application_id: UUID) -> MentorApplication | None:
        return await self.session.get(MentorApplication, application_id)

    async def list_applications(self, status: MentorApplicationStatus | None = None) -> list[MentorApplication]:
        stmt = select(MentorApplication).order_by(MentorApplication.created_at.desc())
        if status is not None:
            stmt = stmt.where(MentorApplication.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    # --- Profils ---

    async def create_profile(self, *, user_id: UUID, sectors: list[str], bio: str, cv_url: str | None) -> MentorProfile:
        profile = MentorProfile(user_id=user_id, sectors=sectors, bio=bio, cv_url=cv_url)
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_profile_by_user(self, user_id: UUID) -> MentorProfile | None:
        result = await self.session.execute(select(MentorProfile).where(MentorProfile.user_id == user_id))
        return result.scalar_one_or_none()

    async def list_active_profiles(self, sector: str | None = None) -> list[tuple[MentorProfile, str]]:
        # Marketplace : profils actifs + nom du mentor (join users).
        stmt = (
            select(MentorProfile, User.full_name)
            .join(User, User.id == MentorProfile.user_id)
            .where(MentorProfile.is_active.is_(True))
            .order_by(MentorProfile.created_at.desc())
        )
        if sector is not None:
            stmt = stmt.where(MentorProfile.sectors.contains([sector]))
        result = await self.session.execute(stmt)
        return [(p, name) for p, name in result.all()]

    async def create_request(
        self, *, founder_id: UUID, mentor_user_id: UUID, project_id: UUID | None, message: str
    ) -> MentorRequest:
        req = MentorRequest(
            founder_id=founder_id,
            mentor_user_id=mentor_user_id,
            project_id=project_id,
            message=message,
        )
        self.session.add(req)
        await self.session.flush()
        return req

    async def get_request(self, request_id: UUID) -> MentorRequest | None:
        return await self.session.get(MentorRequest, request_id)

    async def list_by_founder(self, founder_id: UUID) -> list[tuple[MentorRequest, str]]:
        MentorUser = aliased(User)
        result = await self.session.execute(
            select(MentorRequest, MentorUser.full_name)
            .join(MentorUser, MentorUser.id == MentorRequest.mentor_user_id)
            .where(MentorRequest.founder_id == founder_id)
            .order_by(MentorRequest.created_at.desc())
        )
        return [(req, name) for req, name in result.all()]

    async def list_by_mentor(self, mentor_user_id: UUID) -> list[tuple[MentorRequest, str]]:
        FounderUser = aliased(User)
        result = await self.session.execute(
            select(MentorRequest, FounderUser.full_name)
            .join(FounderUser, FounderUser.id == MentorRequest.founder_id)
            .where(MentorRequest.mentor_user_id == mentor_user_id)
            .order_by(MentorRequest.created_at.desc())
        )
        return [(req, name) for req, name in result.all()]

    async def transition_request(self, req: MentorRequest, *, status: str, session_at: datetime | None = None) -> None:
        req.status = status
        if session_at is not None:
            req.session_at = session_at
        await self.session.flush()

    # --- Invitations ---

    async def create_invitation(
        self, *, email: str, token_hash: str, invited_by: UUID, expires_at: datetime
    ) -> Invitation:
        inv = Invitation(
            email=email,
            role=Role.MENTOR,
            token_hash=token_hash,
            invited_by=invited_by,
            expires_at=expires_at,
        )
        self.session.add(inv)
        await self.session.flush()
        return inv

    async def get_invitation_by_hash(self, token_hash: str) -> Invitation | None:
        result = await self.session.execute(select(Invitation).where(Invitation.token_hash == token_hash))
        return result.scalar_one_or_none()

    async def mark_invitation_accepted(self, inv: Invitation) -> None:
        inv.status = InvitationStatus.ACCEPTED
        await self.session.flush()
