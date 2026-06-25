"""Accès données mentors — candidatures, profils, invitations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.iam.invitations import Invitation, InvitationStatus
from app.iam.models import Role
from app.mentors.models import MentorApplication, MentorApplicationStatus, MentorProfile


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
