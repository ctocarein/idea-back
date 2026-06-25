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
