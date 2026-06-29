"""DTO mentors — candidature, revue, activation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MentorApplyIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    sectors: list[str] = Field(default_factory=list)
    bio: str = Field(default="", max_length=4000)
    cv_url: str | None = Field(default=None, max_length=500)


class MentorApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str
    sectors: list
    bio: str
    cv_url: str | None
    status: str
    created_at: datetime


class ApproveOut(BaseModel):
    user_id: UUID
    # Token d'invitation (en prod : envoyé par email ; renvoyé ici pour l'admin/tests).
    invitation_token: str


class AcceptInvitationIn(BaseModel):
    token: str = Field(min_length=10)
    password: str = Field(min_length=8, max_length=200)


# --- Profil & marketplace ---


class MentorProfileMeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    sectors: list
    bio: str
    cv_url: str | None
    hourly_rate: float | None
    is_active: bool


class MentorProfileUpdateIn(BaseModel):
    sectors: list[str] | None = None
    bio: str | None = Field(default=None, max_length=4000)
    cv_url: str | None = Field(default=None, max_length=500)
    hourly_rate: float | None = Field(default=None, ge=0)
    is_active: bool | None = None  # le mentor peut se rendre indisponible


class MentorPublicOut(BaseModel):
    # Carte marketplace (côté porteur).
    user_id: UUID
    full_name: str
    sectors: list
    bio: str
    hourly_rate: float | None


class MentorRequestIn(BaseModel):
    project_id: UUID | None = None
    message: str = Field(default="", max_length=2000)


class MentorRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mentor_user_id: UUID
    project_id: UUID | None
    status: str


class MentorRequestDetailOut(BaseModel):
    id: UUID
    status: str
    message: str
    mentor_user_id: UUID
    mentor_name: str
    founder_id: UUID
    founder_name: str
    project_id: UUID | None
    session_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RespondRequestIn(BaseModel):
    action: str  # "accept" | "decline"


class SessionPlanIn(BaseModel):
    session_at: datetime
