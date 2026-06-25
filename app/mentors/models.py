"""Modèles mentors — candidature + profil.

Flux : candidature publique → revue admin → approbation crée un compte (statut INVITED) +
une invitation à token → le mentor active son compte (mot de passe). Le profil porte les
secteurs/bio/honoraires et son activation (marketplace).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MentorApplicationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MentorApplication(Base):
    __tablename__ = "mentor_applications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), index=True)
    sectors: Mapped[list] = mapped_column(JSONB, default=list)  # secteurs d'expertise
    bio: Mapped[str] = mapped_column(Text, default="")
    cv_url: Mapped[str | None] = mapped_column(String(500), default=None)  # lien CV (presigned = refinement)
    status: Mapped[MentorApplicationStatus] = mapped_column(default=MentorApplicationStatus.PENDING, index=True)
    reviewed_by: Mapped[UUID | None] = mapped_column(default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)
    created_user_id: Mapped[UUID | None] = mapped_column(default=None)  # compte créé à l'approbation
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class MentorProfile(Base):
    __tablename__ = "mentor_profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    sectors: Mapped[list] = mapped_column(JSONB, default=list)
    bio: Mapped[str] = mapped_column(Text, default="")
    cv_url: Mapped[str | None] = mapped_column(String(500), default=None)
    hourly_rate: Mapped[float | None] = mapped_column(Numeric(8, 2), default=None)  # honoraires (champ)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)  # visible marketplace
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
